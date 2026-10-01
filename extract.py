"""Heuristic extraction of animals/herds from a parsed GVAS tree."""
import csv
import io
import json
import os
import re

from species import SPECIES, MAPS

HERE = os.path.dirname(os.path.abspath(__file__))
BP_SUFFIX = re.compile(r"_\d+_[0-9A-Fa-f]{32}$")


def load_config():
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["_re"] = {k: re.compile(v, re.I) for k, v in cfg["fields"].items()}
    return cfg


def clean_key(k):
    k = k.split("#")[0]
    k = BP_SUFFIX.sub("", k)
    return re.sub(r"[^A-Za-z0-9]", "", k)


def _alnum(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def normalize_species(v):
    """'/Game/Animals/BP_RedDeer_C' / 'ESpecies::RedDeer' / 'red_deer' -> (en, zh, tier)."""
    if v is None:
        return None
    s = str(v)
    s = s.split("::")[-1].split(".")[-1].split("/")[-1]
    s = re.sub(r"^(BP_|B_|E|DA_|ABP_)", "", s)
    s = re.sub(r"(_C|_Data|_Def)$", "", s)
    k = _alnum(s)
    if not k:
        return None
    if k in SPECIES:
        return SPECIES[k]
    best = None
    for key, val in SPECIES.items():  # longest contained key wins
        if key in k and (best is None or len(key) > len(best[0])):
            best = (key, val)
    if best and len(best[0]) >= 3:
        return best[1]
    pretty = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s).replace("_", " ").strip()
    return (pretty, pretty, None)


def detect_map(text):
    k = _alnum(text)
    for key, name in MAPS.items():
        if key in k:
            return name
    return None


# -------------------------------------------------------------- field access
def _categorize(d, cfg, depth=1):
    """Return {category: (key, value)} for a struct dict (look one level deeper too)."""
    found = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        ck = clean_key(k)
        for cat, rx in cfg["_re"].items():
            if cat not in found and rx.search(ck):
                if cat == "species" and isinstance(v, (dict, list)):
                    continue
                found[cat] = (k, v)
                break
        else:
            if depth > 0 and isinstance(v, dict) and "_map" not in v:
                for cat, kv in _categorize(v, cfg, depth - 1).items():
                    found.setdefault(cat, kv)
    return found


ANIMAL_CATS = {"species", "gender", "age", "weight", "score", "fitness", "position"}


def _num(v):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(\.\d+)?", v)
        return float(m.group()) if m else None
    return None


def _position(v):
    if isinstance(v, dict):
        if "X" in v and "Y" in v and isinstance(v.get("X"), (int, float)):
            return v.get("X"), v.get("Y"), v.get("Z", 0.0)
        for k in ("Translation", "Location", "Position"):
            for kk in v:
                if clean_key(kk).lower() == k.lower():
                    return _position(v[kk])
    return None


def _gender(k, v, cfg):
    ck = clean_key(k).lower()
    if isinstance(v, bool):
        male = v if "female" not in ck else not v
        return "M" if male else "F"
    if isinstance(v, (int, float)):
        return cfg["gender_int_map"].get(str(int(v)), "?")
    s = str(v).lower()
    s = s.split("::")[-1]
    if "female" in s or s in ("f", "doe", "cow", "hen", "sow"):
        return "F"
    if "male" in s or s in ("m", "buck", "bull", "stag", "boar"):
        return "M"
    return "?"


def _scalar(v):
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    return json.dumps(v, ensure_ascii=False)[:80]


# -------------------------------------------------------------- tree walk
def _iter_lists(node, path, ancestors):
    """Yield (list, path, ancestors) for every list of dicts in the tree."""
    if isinstance(node, dict):
        if "_map" in node:
            vals = [e["value"] for e in node["_map"]]
            if vals and all(isinstance(x, dict) for x in vals):
                yield vals, path, ancestors, [e["key"] for e in node["_map"]]
            for e in node["_map"]:
                yield from _iter_lists(e["value"], path + [str(e["key"])], ancestors + [node])
            return
        for k, v in node.items():
            yield from _iter_lists(v, path + [k], ancestors + [node])
    elif isinstance(node, list):
        if node and all(isinstance(x, dict) for x in node):
            yield node, path, ancestors, None
        for i, v in enumerate(node):
            yield from _iter_lists(v, path + [str(i)], ancestors + [node])


def _is_animal_list(lst, cfg):
    if len(lst) < cfg.get("min_list_size", 1):
        return False
    sample = lst[:50]
    hits = 0
    for d in sample:
        cats = set(_categorize(d, cfg)) & ANIMAL_CATS
        # must have at least 2 animal attributes and at least one of the strong ones
        if len(cats) >= 2 and cats & {"gender", "weight", "score", "fitness", "age"}:
            hits += 1
    return hits >= max(1, len(sample) * 0.6)


def extract(tree, cfg=None, source_name=""):
    cfg = cfg or load_config()
    candidates = []
    for lst, path, anc, keys in _iter_lists(tree, [], []):
        if _is_animal_list(lst, cfg):
            candidates.append((lst, path, anc, keys))
    # innermost only: drop lists whose path is a prefix of another candidate
    paths = ["/".join(c[1]) + "/" for c in candidates]
    inner = [c for c, p in zip(candidates, paths)
             if not any(q != p and q.startswith(p) for q in paths)]

    animals, herds = [], []
    default_map = detect_map(source_name) or None
    for hi, (lst, path, anc, keys) in enumerate(inner):
        # herd context = nearest ancestor dict that is not the list container
        ctx = {}
        for a in reversed(anc):
            if isinstance(a, dict) and "_map" not in a:
                ctx = a
                break
        hc = _categorize(ctx, cfg, depth=0) if ctx else {}
        path_str = "/".join(path)
        herd_species = None
        if "species" in hc:
            herd_species = normalize_species(hc["species"][1])
        if not herd_species:
            for seg in reversed(path):
                sp = normalize_species(seg)
                if sp and sp[2] is not None:
                    herd_species = sp
                    break
        herd_id = str(_scalar(hc["herd_id"][1])) if "herd_id" in hc else (
            str(_scalar(hc["id"][1])) if "id" in hc else f"H{hi + 1}")
        hpos = _position(hc["position"][1]) if "position" in hc else None
        map_name = detect_map(path_str)
        if not map_name:
            for a in reversed(anc):
                if isinstance(a, dict):
                    for v in a.values():
                        if isinstance(v, str) and len(v) < 200 and detect_map(v):
                            map_name = detect_map(v)
                            break
                if map_name:
                    break
        map_name = map_name or default_map
        herd_animals = []
        for ai, d in enumerate(lst):
            c = _categorize(d, cfg)
            sp = normalize_species(c["species"][1]) if "species" in c else None
            if (not sp or sp[2] is None) and herd_species:
                sp = herd_species if not sp else sp
            if not sp and keys is not None:
                sp = normalize_species(keys[ai])
            pos = _position(c["position"][1]) if "position" in c else None
            dead = None
            if "dead" in c:
                k, v = c["dead"]
                dead = bool(v)
                if "alive" in clean_key(k).lower():
                    dead = not dead
            age = c.get("age", (None, None))[1]
            if isinstance(age, str) and _num(age) is None:
                age_num = None
            else:
                age_num = _num(age)
            a = {
                "species": sp[0] if sp else "未知",
                "species_zh": sp[1] if sp else "未知",
                "tier": sp[2] if sp else None,
                "gender": _gender(*c["gender"], cfg) if "gender" in c else "?",
                "age": age_num,
                "age_label": str(age).split("::")[-1] if age is not None else "",
                "weight": _num(c["weight"][1]) if "weight" in c else None,
                "score": _num(c["score"][1]) if "score" in c else None,
                "fitness": _num(c["fitness"][1]) if "fitness" in c else None,
                "x": pos[0] if pos else (hpos[0] if hpos else None),
                "y": pos[1] if pos else (hpos[1] if hpos else None),
                "z": pos[2] if pos else (hpos[2] if hpos else None),
                "id": str(_scalar(c["id"][1])) if "id" in c else "",
                "dead": dead,
                "herd_id": herd_id,
                "herd_index": hi,
                "map": map_name,
                "path": f"{path_str}/{ai}",
                "fields": {clean_key(k): _scalar(v) for k, v in d.items() if not k.startswith("_")},
            }
            herd_animals.append(a)
        animals.extend(herd_animals)
        hs = herd_species or (normalize_species(herd_animals[0]["species"]) if herd_animals else None)
        xs = [a["x"] for a in herd_animals if a["x"] is not None]
        ys = [a["y"] for a in herd_animals if a["y"] is not None]
        herds.append({
            "id": herd_id, "index": hi, "path": path_str, "map": map_name,
            "species": hs[0] if hs else "未知", "species_zh": hs[1] if hs else "未知",
            "size": len(herd_animals),
            "alive": sum(1 for a in herd_animals if not a["dead"]),
            "x": hpos[0] if hpos else (sum(xs) / len(xs) if xs else None),
            "y": hpos[1] if hpos else (sum(ys) / len(ys) if ys else None),
        })
    for a in animals:
        a["key"] = identity(a, cfg)
    rate(animals, cfg)
    return animals, herds


def identity(a, cfg):
    if a.get("id"):
        return "id:" + a["id"]
    parts = []
    for f in cfg["identity_fields"]:
        if f == "id":
            continue
        v = a.get(f)
        if isinstance(v, float):
            v = round(v, 4)
        parts.append(str(v))
    return "|".join(parts)


def rate(animals, cfg):
    th = cfg.get("star_thresholds", {})
    by = {}
    for a in animals:
        if a["score"] is not None:
            by.setdefault(a["species"], []).append(a["score"])
    for v in by.values():
        v.sort()
    for a in animals:
        a["stars"] = None
        a["percentile"] = None
        s = a["score"]
        if s is None:
            continue
        t = th.get(a["species"])
        if isinstance(t, list):
            a["stars"] = sum(1 for x in t if s >= x)
        vals = by[a["species"]]
        below = sum(1 for x in vals if x < s)
        a["percentile"] = round(100.0 * below / max(1, len(vals) - 1), 1) if len(vals) > 1 else 100.0


def summarize(animals, herds):
    out = {}
    for a in animals:
        s = out.setdefault(a["species"], {
            "species": a["species"], "species_zh": a["species_zh"], "tier": a["tier"],
            "total": 0, "alive": 0, "male": 0, "female": 0, "unknown_sex": 0,
            "max_score": None, "avg_score": None, "_scores": [], "herds": set(), "ages": {},
            "max_fitness": None, "rare": 0})
        if a.get("fitness") is not None:
            s["max_fitness"] = max(s["max_fitness"] or 0, a["fitness"])
        if a.get("variant"):
            s["rare"] += 1
        s["total"] += 1
        if not a["dead"]:
            s["alive"] += 1
        s[{"M": "male", "F": "female"}.get(a["gender"], "unknown_sex")] += 1
        if a["score"] is not None:
            s["_scores"].append(a["score"])
        s["herds"].add(a["herd_index"])
        lab = a["age_label"] or "?"
        s["ages"][lab] = s["ages"].get(lab, 0) + 1
    res = []
    for s in out.values():
        sc = s.pop("_scores")
        if sc:
            s["max_score"] = max(sc)
            s["avg_score"] = round(sum(sc) / len(sc), 2)
        s["herds"] = len(s["herds"])
        if len(s["ages"]) > 12:  # numeric ages -> no breakdown
            s["ages"] = {}
        res.append(s)
    res.sort(key=lambda s: (-s["total"], s["species"]))
    return res


def diff(old, new):
    ok = {a["key"]: a for a in old}
    nk = {a["key"]: a for a in new}
    added = [a for k, a in nk.items() if k not in ok]
    removed = [a for k, a in ok.items() if k not in nk]
    died = [a for k, a in nk.items() if k in ok and a["dead"] and not ok[k]["dead"]]
    changed = []
    for k, a in nk.items():
        if k not in ok:
            continue
        b = ok[k]
        age_delta = (a.get("age") or 0) - (b.get("age") or 0)
        herd_changed = a.get("herd_id") != b.get("herd_id")
        fitness_changed = (a.get("fitness") is not None and b.get("fitness") is not None and
                           abs(a["fitness"] - b["fitness"]) > .0001)
        moved_m = None
        if all(isinstance(x.get(q), (int, float)) for x in (a, b) for q in ("x", "y", "z")):
            moved_m = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2 +
                       (a["z"] - b["z"]) ** 2) ** .5 / 100.0
        if age_delta or herd_changed or fitness_changed or (moved_m is not None and moved_m >= 100):
            changed.append({"animal": a, "before": b, "age_delta": age_delta,
                            "herd_changed": herd_changed, "fitness_changed": fitness_changed,
                            "moved_m": round(moved_m, 1) if moved_m is not None else None})
    return {"added": added, "removed": removed + died,
            "changed": changed,
            "added_keys": [a["key"] for a in added],
            "removed_keys": [a["key"] for a in removed + died]}


CSV_COLS = ["species", "species_zh", "gender", "age", "age_stage", "age_stage_zh",
            "stage_weight_range", "knowledge_confidence", "age_label", "weight", "score", "stars",
            "percentile", "fitness", "fitness_band", "herd_id", "map", "habitat", "area", "territory_id",
            "age_limit", "years_to_limit", "x", "y", "z", "id", "dead", "path"]


def to_csv(animals):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLS)
    for a in animals:
        w.writerow([a.get(c, "") for c in CSV_COLS])
    return "\ufeff" + buf.getvalue()
