"""v3.0 Hunt Journal: persistent, tool-owned log of population transitions.

Built only from read-only scans of the game save and of the tool's own snapshots.
A "removed" event means an animal ID disappeared between two save states. It can
be a harvest, a natural death or year turnover; the journal never claims which.
"""
import json
import os
import threading
import time

import extract

HERE = os.path.dirname(os.path.abspath(__file__))
JOURNAL_DIR = os.path.join(HERE, "journal")
YEAR_TURN_RATIO = 0.5
_lock = threading.Lock()


def _path():
    return os.path.join(JOURNAL_DIR, "journal.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            j = json.load(f)
            if j.get("version") == 1:
                return j
    except (OSError, ValueError):
        pass
    return {"version": 1, "events": {}, "transitions": {}}


def save(j):
    os.makedirs(JOURNAL_DIR, exist_ok=True)
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(j, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, _path())


def _reserve(res):
    r = (res.get("db_info") or {}).get("reserve")
    if r:
        return r
    maps = res.get("maps") or []
    return maps[0] if len(maps) == 1 else None


def _habitat_avgs(animals):
    acc = {}
    for a in animals:
        if a.get("gender") == "M" and a.get("fitness") is not None:
            k = (a["species"], a.get("habitat") or "未知")
            s = acc.setdefault(k, [0.0, 0])
            s[0] += a["fitness"]
            s[1] += 1
    return {k: v[0] / v[1] for k, v in acc.items()}


def _event(a, kind, reserve, t_before, t_after, year_turn, avgs):
    avg = avgs.get((a["species"], a.get("habitat") or "未知"))
    f = a.get("fitness") if a.get("gender") == "M" else None
    return {"type": kind, "reserve": reserve, "id": a.get("id"), "species": a.get("species"),
            "species_zh": a.get("species_zh"), "slug": a.get("knowledge_slug"), "gender": a.get("gender"),
            "age": a.get("age"), "age_stage": a.get("age_stage"), "fitness": f,
            "variant": a.get("variant") or "", "herd_id": a.get("herd_id"), "habitat": a.get("habitat"),
            "area": a.get("area"), "x": a.get("x"), "y": a.get("y"),
            "seen_before": t_before, "detected": t_after, "year_turn": year_turn,
            "habitat_avg": round(avg, 5) if avg is not None else None,
            "below_avg": (f < avg) if (f is not None and avg is not None) else None}


def analyse(old, new):
    """Pure function: describe the transition old -> new (no I/O)."""
    reserve = _reserve(new)
    if not reserve or reserve != _reserve(old) or old["sha1"] == new["sha1"]:
        return None
    d = extract.diff(old["animals"], new["animals"])
    old_keys = {a["key"] for a in old["animals"]}
    persisting = sum(1 for a in new["animals"] if a["key"] in old_keys)
    aged = sum(1 for c in d["changed"] if (c.get("age_delta") or 0) > 0)
    year_turn = bool(persisting) and aged / persisting >= YEAR_TURN_RATIO
    avgs = _habitat_avgs(old["animals"])
    t0, t1 = old["mtime"], new["mtime"]
    events = [_event(a, "removed", reserve, t0, t1, year_turn, avgs) for a in d["removed"]]
    events += [_event(a, "spawned", reserve, t0, t1, year_turn, avgs) for a in d["added"]]
    return {"key": f"{old['sha1'][:12]}>{new['sha1'][:12]}", "reserve": reserve, "from": t0, "to": t1,
            "year_turn": year_turn, "persisting": persisting, "aged": aged,
            "removed": len(d["removed"]), "spawned": len(d["added"]), "events": events}


def record(old, new):
    """Merge one transition into the journal. Idempotent; returns number of new events."""
    tr = analyse(old, new)
    if not tr:
        return 0
    with _lock:
        j = load()
        if tr["key"] in j["transitions"]:
            return 0
        added = 0
        for e in tr["events"]:
            k = f"{e['reserve']}:{e['id']}:{e['type']}"
            if k not in j["events"]:
                j["events"][k] = e
                added += 1
        j["transitions"][tr["key"]] = {k: v for k, v in tr.items() if k != "events"}
        save(j)
        return added


def summary(reserve=None, limit=1000):
    j = load()
    ev = [e for e in j["events"].values() if not reserve or e["reserve"] == reserve]
    trs = [t for t in j["transitions"].values() if not reserve or t["reserve"] == reserve]
    sp = {}
    for e in ev:
        s = sp.setdefault((e["reserve"], e["species"]), {
            "reserve": e["reserve"], "species": e["species"], "species_zh": e.get("species_zh"),
            "removed_period": 0, "removed_year": 0, "spawned": 0, "rare_removed": 0,
            "_rf": [], "_ha": [], "below": 0, "judged": 0})
        if e["type"] == "spawned":
            s["spawned"] += 1
            continue
        s["removed_year" if e["year_turn"] else "removed_period"] += 1
        s["rare_removed"] += int(bool(e.get("variant")))
        if not e["year_turn"] and e.get("fitness") is not None:
            s["_rf"].append(e["fitness"])
            if e.get("habitat_avg") is not None:
                s["_ha"].append(e["habitat_avg"])
            if e.get("below_avg") is not None:
                s["judged"] += 1
                s["below"] += int(e["below_avg"])
    rows = []
    for s in sp.values():
        rf, ha = s.pop("_rf"), s.pop("_ha")
        s["avg_removed_fitness"] = round(sum(rf) / len(rf), 5) if rf else None
        s["avg_habitat_at_time"] = round(sum(ha) / len(ha), 5) if ha else None
        s["below_avg_rate"] = round(s["below"] / s["judged"], 4) if s["judged"] else None
        rows.append(s)
    judged = sum(r["judged"] for r in rows)
    below = sum(r["below"] for r in rows)
    ev.sort(key=lambda e: (-(e["detected"] or 0), e["species"] or ""))
    return {"read_only_source": True, "reserve": reserve,
            "transitions": len(trs), "year_turns": sum(t["year_turn"] for t in trs),
            "removed_period": sum(r["removed_period"] for r in rows),
            "removed_year": sum(r["removed_year"] for r in rows),
            "spawned": sum(r["spawned"] for r in rows),
            "management_judged": judged, "management_below_avg": below,
            "management_rate": round(below / judged, 4) if judged else None,
            "species": sorted(rows, key=lambda r: (r["reserve"], -(r["removed_period"] + r["removed_year"]), r["species"])),
            "timeline": sorted(trs, key=lambda t: t["to"]),
            "events": ev[:limit], "event_count": len(ev), "generated_at": time.time()}


def reset():
    with _lock:
        if os.path.exists(_path()):
            os.remove(_path())
