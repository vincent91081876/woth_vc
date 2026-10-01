#!/usr/bin/env python3
"""WOTH Animal Population Scanner - read-only population viewer for Way of the Hunter.

Usage:
  python woth_scanner.py                 # start local web UI (opens browser)
  python woth_scanner.py --scan FILE     # print population summary
  python woth_scanner.py --dump FILE     # dump the full parsed save as JSON
  python woth_scanner.py --list          # list detected save files
"""
import argparse
import collections
import glob
import hashlib
import http.server
import json
import math
import os
import sys
import threading
import time
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gvas  # noqa: E402
import extract  # noqa: E402
import knowledge  # noqa: E402
import woth_db  # noqa: E402
import habitat  # noqa: E402
import journal  # noqa: E402
import woth2  # noqa: E402
import player_state  # noqa: E402
import observatory  # noqa: E402
import route_planner  # noqa: E402
import methodology  # noqa: E402

VERSION = "4.0.8"
SNAP_DIR = os.path.join(HERE, "snapshots")
WEB_DIR = os.path.join(HERE, "web")
_vault_cache = {"signature": None, "value": None}


# ---------------------------------------------------------------- discovery
def save_dirs(cfg):
    dirs = list(cfg.get("save_dirs") or [])
    if os.environ.get("WOTH_SAVE_DIR"):
        dirs.insert(0, os.environ["WOTH_SAVE_DIR"])
    la = os.environ.get("LOCALAPPDATA")
    if la:
        dirs.append(os.path.join(la, "WayOfTheHunter", "Saved", "SaveGames"))
    home = os.path.expanduser("~")
    for steam in (".steam/steam", ".local/share/Steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
        dirs.append(os.path.join(home, steam, "steamapps/compatdata/1288320/pfx/drive_c/users/steamuser/AppData/Local/WayOfTheHunter/Saved/SaveGames"))
    out = []
    for d in dirs:
        if d and os.path.isdir(d) and d not in out:
            out.append(d)
    return out


def list_saves(cfg):
    res = []
    for d in save_dirs(cfg):
        for p in glob.glob(os.path.join(d, "**", "*.sav"), recursive=True):
            st = os.stat(p)
            res.append({"path": p, "name": os.path.relpath(p, d), "dir": d,
                        "size": st.st_size, "mtime": st.st_mtime})
    res.sort(key=lambda x: -x["mtime"])
    return res


def result_reserve(res):
    reserve = (res.get("db_info") or {}).get("reserve")
    if reserve:
        return reserve
    maps = res.get("maps") or []
    return maps[0] if len(maps) == 1 else None


def vault_entry(res, source, path, cfg):
    """Compact, non-sensitive last-known state for one reserve."""
    animals = res["animals"]
    known = [a for a in animals if a.get("gender") == "M" and a.get("fitness") is not None]
    by_species = {}
    for a in animals:
        s = by_species.setdefault(a["species"], {
            "species": a["species"], "species_zh": a.get("species_zh", ""),
            "slug": a.get("knowledge_slug"),
            "total": 0, "male_known": 0, "fitness_sum": 0.0,
            "high80": 0, "low50": 0, "rare": 0,
        })
        s["total"] += 1
        s["rare"] += int(bool(a.get("variant")))
        if a.get("gender") == "M" and a.get("fitness") is not None:
            f = a["fitness"]
            s["male_known"] += 1
            s["fitness_sum"] += f
            s["high80"] += int(f >= .80)
            s["low50"] += int(f <= .50)
    for s in by_species.values():
        s["avg_fitness"] = round(s.pop("fitness_sum") / s["male_known"], 5) if s["male_known"] else None
    return {
        "reserve": result_reserve(res), "source": source, "path": path,
        "time": res["mtime"], "name": res["name"], "sha1": res["sha1"],
        "total": len(animals), "herds": len(res["herds"]), "species_count": len(by_species),
        "male_known": len(known),
        "avg_fitness": round(sum(a["fitness"] for a in known) / len(known), 5) if known else None,
        "high80": sum(a["fitness"] >= .80 for a in known),
        "low50": sum(a["fitness"] <= .50 for a in known),
        "rare": sum(bool(a.get("variant")) for a in animals),
        "health": health_report(res, cfg)["status"],
        "species": sorted(by_species.values(), key=lambda x: x["species"]),
    }


def merge_vault_entries(entries, reserve_names):
    latest = {}
    for e in entries:
        reserve = e.get("reserve")
        if reserve in reserve_names and (reserve not in latest or e["time"] > latest[reserve]["time"]):
            latest[reserve] = e
    rows = [{"reserve": name, "available": name in latest, **(latest.get(name) or {})}
            for name in reserve_names]
    return {"coverage": len(latest), "total_reserves": len(reserve_names), "reserves": rows}


def reserve_vault(cfg):
    """Read current saves and retained snapshots; never creates or modifies them."""
    reserve_names = [k for k in (cfg.get("maps") or {}) if not k.startswith("_")]
    candidates = [(x["path"], "current") for x in list_saves(cfg)]
    snapshots = sorted(glob.glob(os.path.join(SNAP_DIR, "*", "*.sav")),
                       key=os.path.getmtime, reverse=True)
    candidates += [(p, "snapshot") for p in snapshots[:1000]]
    signature = tuple((p, source, os.path.getmtime(p), os.path.getsize(p))
                      for p, source in candidates if os.path.isfile(p))
    if signature == _vault_cache["signature"] and _vault_cache["value"] is not None:
        return _vault_cache["value"]
    entries, errors, seen = [], [], set()
    for path, source in candidates:
        try:
            res = scan(path, cfg, snapshot=False)
            if res["sha1"] in seen:
                continue
            seen.add(res["sha1"])
            e = vault_entry(res, source, path, cfg)
            if e["reserve"]:
                entries.append(e)
        except Exception as exc:
            errors.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
    out = merge_vault_entries(entries, reserve_names)
    out["scanned_files"] = len(candidates)
    out["unique_states"] = len(seen)
    out["error_count"] = len(errors)
    out["errors"] = errors[:20]
    out["generated_at"] = time.time()
    _vault_cache["signature"], _vault_cache["value"] = signature, out
    return out


# ---------------------------------------------------------------- scanning
_cache = {}
_lock = threading.Lock()


def _in_snapshot_dir(path):
    """True when `path` is inside the tool's own snapshots folder (not merely a similarly named one)."""
    root = os.path.normcase(os.path.realpath(SNAP_DIR))
    return os.path.normcase(os.path.realpath(path)).startswith(root + os.sep)


def scan(path, cfg=None, snapshot=True, force=False):
    cfg = cfg or extract.load_config()
    st = os.stat(path)
    ck = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    is_snapshot_file = _in_snapshot_dir(path)
    with _lock:
        hit = None if force else _cache.get(ck)
    # A result cached by a snapshot=False caller (the Reserve Vault reads every save that way) has no
    # backup or journal entry yet, so it must not be handed to a caller that asked for a snapshot.
    if hit is not None and (not snapshot or "snapshot" in hit or is_snapshot_file):
        return hit
    with open(path, "rb") as f:  # READ ONLY
        data = f.read()
    t0 = time.time()
    g = gvas.Gvas(data)
    db_info = None
    if woth_db.is_database_save(g):
        animals, herds, db_info = woth_db.parse(g.raw, len(g.raw) - g.trailing)
    else:
        animals, herds = extract.extract(g.props, cfg, os.path.basename(path))
    for animal in animals:
        knowledge.annotate(animal)
    reserve = (db_info or {}).get("reserve")
    if not reserve:
        maps_found = sorted({a["map"] for a in animals if a.get("map")})
        reserve = maps_found[0] if len(maps_found) == 1 else None
    zone_match = habitat.annotate(animals, herds, reserve)
    ps = player_state.inspect(g.props, g.raw, len(g.raw) - g.trailing, reserve, cfg,
                              is_database=bool(db_info))
    res = {
        "path": path, "name": os.path.basename(path), "mtime": st.st_mtime,
        "mtime_ns": st.st_mtime_ns, "size": st.st_size,
        "sha1": hashlib.sha1(data).hexdigest(), "header": g.header, "compression": g.compression,
        "warnings": g.warnings[:200], "warning_count": len(g.warnings),
        "animals": animals, "herds": herds, "summary": extract.summarize(animals, herds),
        "species_info": knowledge.public_info_for(animals),
        "maps": sorted({a["map"] for a in animals if a["map"]}),
        "parse_ms": int((time.time() - t0) * 1000),
        "format": db_info["format"] if db_info else "GVAS properties", "db_info": db_info,
        "reserve": reserve, "zone_match": zone_match, "habitat_report": habitat.habitat_report(animals),
        "player_state": ps,
        "_tree": {"header_props": g.props, "database": db_info} if db_info else g.props,
    }
    if snapshot and not is_snapshot_file:
        res["journal_new_events"] = journal_from_previous(path, res, cfg)
        res["snapshot"] = take_snapshot(path, data, st.st_mtime, cfg.get("max_snapshots", 100))
    with _lock:
        _cache.clear() if len(_cache) > 8 else None
        _cache[ck] = res
    return res


def take_snapshot(path, data, mtime, max_snapshots=100):
    d = os.path.join(SNAP_DIR, hashlib.md5(os.path.abspath(path).encode()).hexdigest()[:8] + "_" +
                     os.path.splitext(os.path.basename(path))[0])
    os.makedirs(d, exist_ok=True)
    digest = hashlib.sha1(data).hexdigest()
    existing = sorted(glob.glob(os.path.join(d, "*.sav")), reverse=True)
    # New-format filenames make de-duplication free. Check a few legacy files
    # by content so upgrading does not immediately duplicate the latest save.
    if any(os.path.basename(p).endswith(f"-{digest[:10]}.sav") for p in existing):
        return next(p for p in existing if os.path.basename(p).endswith(f"-{digest[:10]}.sav"))
    for p in existing[:3]:
        if "-" + digest[:10] not in os.path.basename(p):
            with open(p, "rb") as f:
                if hashlib.sha1(f.read()).hexdigest() == digest:
                    return p
    name = time.strftime("%Y%m%d-%H%M%S", time.localtime(mtime)) + f"-{digest[:10]}.sav"
    dst = os.path.join(d, name)
    if not os.path.exists(dst):
        with open(dst, "wb") as f:
            f.write(data)
        os.utime(dst, (mtime, mtime))
    keep = max(2, min(1000, int(max_snapshots or 100)))
    for old in sorted(glob.glob(os.path.join(d, "*.sav")), key=os.path.getmtime)[:-keep]:
        try:
            os.remove(old)
        except OSError:
            pass
    return dst


def journal_from_previous(path, res, cfg):
    """Record the transition latest-snapshot -> current save in the tool-owned journal."""
    try:
        snaps = sorted(list_snapshots(path), key=os.path.getmtime)
        if not snaps:
            return 0
        prev = scan(snaps[-1], cfg, snapshot=False)
        return journal.record(prev, res) if prev["sha1"] != res["sha1"] else 0
    except Exception:
        return 0


def rebuild_journal(cfg):
    """Replay every retained snapshot series (oldest -> newest) into the journal."""
    added, pairs, errors = 0, 0, 0
    for d in sorted(glob.glob(os.path.join(SNAP_DIR, "*"))):
        files = sorted(glob.glob(os.path.join(d, "*.sav")), key=os.path.getmtime)
        prev = None
        for p in files:
            try:
                cur = scan(p, cfg, snapshot=False)
            except Exception:
                errors += 1
                continue
            if prev is not None and prev["sha1"] != cur["sha1"]:
                pairs += 1
                added += journal.record(prev, cur)
            prev = cur
    for s in list_saves(cfg):
        try:
            cur = scan(s["path"], cfg, snapshot=False)
            added += journal_from_previous(s["path"], cur, cfg)
        except Exception:
            errors += 1
    return {"pairs": pairs, "new_events": added, "errors": errors}


def list_snapshots(path):
    d = os.path.join(SNAP_DIR, hashlib.md5(os.path.abspath(path).encode()).hexdigest()[:8] + "_" +
                     os.path.splitext(os.path.basename(path))[0])
    return sorted(glob.glob(os.path.join(d, "*.sav")), reverse=True)


def history_point(res):
    species = {}
    for a in res["animals"]:
        s = species.setdefault(a["species"], {"species": a["species"], "species_zh": a["species_zh"],
                                              "total": 0, "male": 0, "female": 0, "rare": 0,
                                              "fitness_sum": 0.0, "fitness_n": 0, "high": 0, "low": 0})
        s["total"] += 1
        if a["gender"] == "M":
            s["male"] += 1
        elif a["gender"] == "F":
            s["female"] += 1
        if a.get("variant"):
            s["rare"] += 1
        if a.get("fitness") is not None:
            f = a["fitness"]
            s["fitness_sum"] += f
            s["fitness_n"] += 1
            s["high"] += int(f >= .90)
            s["low"] += int(f <= .50)
    for s in species.values():
        s["avg_fitness"] = round(s.pop("fitness_sum") / s["fitness_n"], 5) if s["fitness_n"] else None
        s.pop("fitness_n")
    return {"time": res["mtime"], "name": res["name"], "path": res["path"], "sha1": res["sha1"],
            "reserve": (res.get("db_info") or {}).get("reserve"), "total": len(res["animals"]),
            "herds": len(res["herds"]), "rare": sum(s["rare"] for s in species.values()),
            "species": sorted(species.values(), key=lambda s: s["species"])}


def health_report(res, cfg, previous=None):
    animals = res["animals"]
    ids = [a["id"] for a in animals]
    duplicate_ids = sum(n - 1 for n in collections.Counter(ids).values() if n > 1)
    unknown = sum(1 for a in animals if not a.get("species") or a["species"] in ("未知", a.get("latin")))
    orphan = sum(1 for a in animals if a.get("herd_index", -1) < 0)
    invalid = sum(1 for a in animals if not all(isinstance(a.get(k), (int, float)) and
                  math.isfinite(a[k]) for k in ("x", "y", "z")))
    outside = 0
    reserve = (res.get("db_info") or {}).get("reserve")
    cal = (cfg.get("maps") or {}).get(reserve, {})
    if cal:
        outside = sum(1 for a in animals if isinstance(a.get("x"), (int, float)) and
                      (a["x"] < cal["x_min"] or a["x"] > cal["x_max"] or
                       a["y"] < cal["y_min"] or a["y"] > cal["y_max"]))
    checks = [
        {"key": "parse", "label": "解析警告", "value": res["warning_count"],
         "status": "ok" if not res["warning_count"] else "warn"},
        {"key": "ids", "label": "重複動物 ID", "value": duplicate_ids,
         "status": "ok" if not duplicate_ids else "error"},
        {"key": "unknown", "label": "未知物種", "value": unknown,
         "status": "ok" if not unknown else "warn"},
        {"key": "orphan", "label": "無法對應獸群", "value": orphan,
         "status": "ok" if orphan <= max(5, len(animals) * .02) else "warn"},
        {"key": "coords", "label": "無效座標", "value": invalid,
         "status": "ok" if not invalid else "error"},
        {"key": "bounds", "label": "超出地圖範圍", "value": outside,
         "status": "ok" if not outside else "warn"},
    ]
    changes = []
    if previous and previous["sha1"] != res["sha1"]:
        old_total = previous["total"]
        delta = len(animals) - old_total
        ratio = abs(delta) / max(1, old_total)
        if ratio >= .20:
            changes.append(f"總族群變化 {delta:+d}（{ratio:.1%}）")
        old = {s["species"]: s["total"] for s in previous["species"]}
        now = collections.Counter(a["species"] for a in animals)
        for sp in sorted(set(old) | set(now)):
            if old.get(sp, 0) and abs(now.get(sp, 0) - old[sp]) / old[sp] >= .30:
                changes.append(f"{sp} {now.get(sp, 0)-old[sp]:+d}")
    zm = res.get("zone_match") or {}
    if zm.get("available") and zm.get("herds"):
        med = zm.get("median_dist_m")
        rate = zm.get("match_rate") or 0
        checks.append({"key": "zones", "label": "需求區領域對應",
                       "value": f"{rate:.0%} 對應；中位距離 {med if med is not None else '—'} m",
                       "status": "ok" if rate >= .6 and (med or 0) <= 600 else "warn"})
    ps = res.get("player_state") or {}
    checks.append({
        "key": "player", "label": "玩家位置",
        "value": ("已驗證 exact" if ps.get("available") else
                  "只確認目前地圖；座標未驗證" if ps.get("current_map") else "此格式沒有可驗證座標"),
        "status": "ok" if ps.get("available") else "warn",
    })
    checks.append({"key": "change", "label": "大幅族群變動", "value": "；".join(changes) if changes else "無",
                   "status": "warn" if changes else "ok"})
    return {"status": "error" if any(c["status"] == "error" for c in checks) else
            "warn" if any(c["status"] == "warn" for c in checks) else "ok",
            "checks": checks, "read_only": True, "source_sha1": res["sha1"]}


def history(path, cfg):
    current = scan(path, cfg, snapshot=False)
    files = list_snapshots(path)
    limit = max(2, min(100, int(cfg.get("max_snapshots", 100))))
    candidates = sorted(files, key=os.path.getmtime)[-limit:]
    points, seen = [], set()
    for p in candidates:
        try:
            r = scan(p, cfg, snapshot=False)
            if r["sha1"] not in seen:
                points.append(history_point(r))
                seen.add(r["sha1"])
        except Exception:
            continue
    if current["sha1"] not in seen:
        points.append(history_point(current))
    points.sort(key=lambda x: x["time"])
    previous = next((p for p in reversed(points[:-1]) if p["sha1"] != current["sha1"]), None)
    return {"points": points, "health": health_report(current, cfg, previous),
            "max_snapshots": limit, "snapshot_count": len(files)}


def observatory_report(path, cfg):
    """Analyse retained states for one source; does not create snapshots."""
    files = sorted(list_snapshots(path), key=os.path.getmtime)
    limit = max(2, min(1000, int(cfg.get("max_snapshots", 100))))
    states, errors, seen = [], [], set()
    for p in files[-limit:] + ([path] if os.path.isfile(path) else []):
        try:
            s = scan(p, cfg, snapshot=False)
            if s["sha1"] not in seen:
                states.append(s)
                seen.add(s["sha1"])
        except Exception as exc:
            errors.append({"path": p, "error": f"{type(exc).__name__}: {exc}"})
    report = observatory.analyse(states)
    report["source_path"] = path
    report["source_sha1"] = states[-1]["sha1"] if states else None
    report["errors"] = errors[:20]
    report["error_count"] = len(errors)
    return report


def route_report(path, cfg, q):
    res = scan(path, cfg, snapshot=False)
    start_mode = q.get("start", "player")
    sx = sy = None
    if start_mode == "player" and (res.get("player_state") or {}).get("available"):
        pos = res["player_state"]["position"]
        sx, sy = pos["x"], pos["y"]
    elif start_mode == "manual":
        sx, sy = float(q["x"]), float(q["y"])
    maxfit = q.get("max_fitness")
    out = route_planner.plan(
        res["animals"], res["herds"], res["reserve"],
        species=q.get("species") or None, habitat=q.get("habitat") or None,
        limit=int(q.get("limit", 12)),
        mature_only=q.get("mature", "1") not in ("0", "false", "False"),
        max_fitness=float(maxfit) if maxfit not in (None, "") else None,
        exclude_rare=q.get("exclude_rare", "1") not in ("0", "false", "False"),
        activity=q.get("activity", "Drink"), start_x=sx, start_y=sy,
        ids=[x for x in q.get("ids", "").split(",") if x],
    )
    out["start_mode_requested"] = start_mode
    out["source_sha1"] = res["sha1"]
    out["player_state"] = res.get("player_state")
    return out


def public(res):
    return {k: v for k, v in res.items() if not k.startswith("_")}


def trim_tree(node, depth=0, max_list=100):
    if depth > 40:
        return "…"
    if isinstance(node, dict):
        return {k: trim_tree(v, depth + 1, max_list) for k, v in node.items()}
    if isinstance(node, list):
        out = [trim_tree(v, depth + 1, max_list) for v in node[:max_list]]
        if len(node) > max_list:
            out.append(f"… 還有 {len(node) - max_list} 筆")
        return out
    if isinstance(node, str) and len(node) > 300:
        return node[:300] + "…"
    return node


# ---------------------------------------------------------------- HTTP
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # The browser closed, refreshed or cancelled the request.
            return

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if not u.path.startswith("/api/"):
            return super().do_GET()
        try:
            cfg = extract.load_config()
            p = q.get("path")
            if p is not None and not os.path.isfile(p):
                return self._json({"error": f"找不到檔案: {p}"}, 404)
            if u.path == "/api/info":
                return self._json({"version": VERSION, "dirs": save_dirs(cfg),
                                   "poll_seconds": cfg.get("poll_seconds", 3),
                                   "max_snapshots": cfg.get("max_snapshots", 100),
                                   "zones": habitat.meta(),
                                   "maps": {k: v for k, v in cfg.get("maps", {}).items() if not k.startswith("_")}})
            if u.path == "/api/saves":
                return self._json(list_saves(cfg))
            if u.path == "/api/vault":
                return self._json(reserve_vault(cfg))
            if u.path == "/api/zones":
                rd = habitat.reserve_data(q.get("reserve", ""))
                return self._json({"reserve": q.get("reserve"), "available": bool(rd), **(rd or {}),
                                   **{k: v for k, v in habitat.meta().items() if k != "reserves"}})
            if u.path == "/api/journal":
                return self._json(journal.summary(q.get("reserve") or None, int(q.get("limit", 1000))))
            if u.path == "/api/journal/rebuild":
                return self._json({**rebuild_journal(cfg), **journal.summary(q.get("reserve") or None, 50)})
            if u.path == "/api/woth2":
                return self._json(woth2.scan())
            if u.path == "/api/player-state":
                return self._json(scan(p, cfg, snapshot=False)["player_state"])
            if u.path == "/api/observatory":
                return self._json(observatory_report(p, cfg))
            if u.path == "/api/route":
                return self._json(route_report(p, cfg, q))
            if u.path == "/api/methodology":
                return self._json(methodology.report())
            if u.path == "/api/catalog":
                return self._json(knowledge.catalog())
            if u.path == "/api/scan":
                return self._json(public(scan(p, cfg)))
            if u.path == "/api/live":
                st = os.stat(p)
                since = float(q.get("since", 0))
                client_sha1 = q.get("sha1", "")
                if since >= st.st_mtime and client_sha1:
                    with open(p, "rb") as f:
                        current_sha1 = hashlib.sha1(f.read()).hexdigest()
                    if current_sha1 == client_sha1:
                        return self._json({"changed": False, "mtime": st.st_mtime,
                                           "mtime_ns": st.st_mtime_ns})
                elif since >= st.st_mtime:
                    return self._json({"changed": False, "mtime": st.st_mtime,
                                       "mtime_ns": st.st_mtime_ns})
                return self._json({"changed": True,
                                   **public(scan(p, cfg, force=True))})
            if u.path == "/api/snapshots":
                return self._json([{"path": s, "name": os.path.basename(s), "mtime": os.path.getmtime(s)}
                                   for s in list_snapshots(p)])
            if u.path == "/api/history":
                return self._json(history(p, cfg))
            if u.path == "/api/diff":
                a = scan(q["a"], cfg, snapshot=False)
                b = scan(q["b"], cfg, snapshot=False)
                return self._json(extract.diff(a["animals"], b["animals"]))
            if u.path == "/api/tree":
                return self._json(trim_tree(scan(p, cfg)["_tree"], max_list=int(q.get("max", 100))))
            if u.path == "/api/export.csv":
                body = extract.to_csv(scan(p, cfg)["animals"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="woth_population.csv"')
                self.end_headers()
                self.wfile.write(body)
                return
            return self._json({"error": "unknown endpoint"}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def serve(port, open_browser=True):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"WOTH Animal Population Scanner v{VERSION}\n介面網址: {url}\n按 Ctrl+C 結束。")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------- CLI
def cli_scan(path):
    r = scan(path, snapshot=False)
    h = r["header"]
    print(f"檔案: {path}\n引擎: UE {h.get('engine')}  類別: {h.get('class')}  壓縮: {r['compression']}")
    if r.get("db_info"):
        print(f"格式: {r['db_info']['format']}  保護區: {r['db_info']['reserve']}")
    print(f"獸群: {len(r['herds'])}  動物: {len(r['animals'])}  警告: {r['warning_count']}  ({r['parse_ms']} ms)")
    zm = r.get("zone_match") or {}
    if zm.get("available"):
        print(f"需求區領域對應: {zm['matched']}/{zm['herds']} 群，中位距離 {zm['median_dist_m']} m")
    print()
    print(f"{'物種':<24}{'中文':<10}{'總數':>6}{'公':>5}{'母':>5}{'獸群':>6}{'稀有':>5}{'最高分':>8}{'最高Fitness':>12}")
    for s in r["summary"]:
        ms = "" if s["max_score"] is None else f"{s['max_score']:.1f}"
        mf = "" if s.get("max_fitness") is None else f"{s['max_fitness']:.3f}"
        print(f"{s['species']:<24}{s['species_zh']:<10}{s['total']:>6}{s['male']:>5}{s['female']:>5}{s['herds']:>6}{s.get('rare', 0):>5}{ms:>8}{mf:>12}")
    if not r["animals"]:
        print("未辨識到動物資料。請用 --dump 匯出結構，找出欄位名稱後修改 config.json。")
    for w in r["warnings"][:10]:
        print("警告:", w)


def main():
    ap = argparse.ArgumentParser(description="Way of the Hunter Animal Population Scanner (read-only)")
    ap.add_argument("--scan", metavar="FILE")
    ap.add_argument("--dump", metavar="FILE")
    ap.add_argument("--out", metavar="JSON")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--journal", action="store_true", help="rebuild and print the hunt journal summary")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if a.list:
        for s in list_saves(extract.load_config()):
            print(time.strftime("%Y-%m-%d %H:%M", time.localtime(s["mtime"])), f"{s['size']:>10}", s["path"])
        return
    if a.scan:
        return cli_scan(a.scan)
    if a.journal:
        cfg = extract.load_config()
        r = rebuild_journal(cfg)
        j = journal.summary()
        print(f"日誌：新增 {r['new_events']} 筆事件，{j['transitions']} 次存檔變化，{j['year_turns']} 次年度更替")
        for s in j["species"]:
            print(f"{s['reserve']:<20}{s['species']:<24} 期間消失 {s['removed_period']:>4}  年度消失 {s['removed_year']:>4}  新生成 {s['spawned']:>4}")
        return
    if a.dump:
        g = gvas.load(a.dump)
        txt = json.dumps({"header": g.header, "compression": g.compression, "warnings": g.warnings,
                          "props": g.props}, ensure_ascii=False, indent=1, default=str)
        if a.out:
            with open(a.out, "w", encoding="utf-8") as f:
                f.write(txt)
            print("已輸出:", a.out)
        else:
            print(txt)
        return
    serve(a.port, not a.no_browser)


if __name__ == "__main__":
    main()
