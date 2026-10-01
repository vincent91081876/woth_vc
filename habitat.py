"""v3.0 Habitat Genetics Lab & Need-Zone Navigator (offline, read-only).

Need-zone / territory / area-label data: data/need_zones.json, derived from
codeaid/woth-toolbox (GPL-3.0) and converted to Unreal world centimetres.
Habitat assignment is an approximation (nearest labelled area of the reserve),
never the game's own habitat polygon.
"""
import json
import math
import os
import statistics

import knowledge

HERE = os.path.dirname(os.path.abspath(__file__))
ZONE_FILE = os.path.join(HERE, "data", "need_zones.json")
ACTIVITIES = ("Drink", "Feed", "Sleep")
MATCH_HIGH_M = 300.0
MATCH_MAX_M = 1500.0
_data = None


def data():
    global _data
    if _data is None:
        try:
            with open(ZONE_FILE, encoding="utf-8") as f:
                _data = json.load(f)
        except OSError:
            _data = {"reserves": {}}
    return _data


def reserve_data(reserve):
    return (data().get("reserves") or {}).get(reserve)


def meta():
    d = data()
    return {"source": d.get("source"), "license": d.get("license"), "source_commit": d.get("source_commit"),
            "calibration": d.get("calibration"),
            "reserves": {k: {"territories": len(v["territories"]), "areas": len(v["areas"]),
                             "zones": sum(len(t[a]) for t in v["territories"] for a in ACTIVITIES)}
                         for k, v in (d.get("reserves") or {}).items()}}


def _dist_m(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by) / 100.0


def nearest_area(reserve, x, y):
    rd = reserve_data(reserve)
    if not rd or not rd["areas"] or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return min(rd["areas"], key=lambda a: (a["x"] - x) ** 2 + (a["y"] - y) ** 2)


def slug_for(latin, species):
    info, conf = knowledge.lookup(latin, species)
    return (info["slug"] if info else None), conf


def nearest_zone(territory, activity, x, y):
    zones = (territory or {}).get(activity) or []
    if not zones or not isinstance(x, (int, float)):
        return None
    z = min(zones, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    return {"x": z[0], "y": z[1], "dist_m": round(_dist_m(x, y, z[0], z[1]), 1), "activity": activity}


def annotate(animals, herds, reserve):
    """Attach territory match, approximate habitat and zone counts. Mutates in place."""
    rd = reserve_data(reserve)
    by_slug = {}
    for t in (rd or {}).get("territories", []):
        by_slug.setdefault(t["slug"], []).append(t)
    for h in herds:
        slug, _ = slug_for(h.get("latin"), h.get("species"))
        h["slug"] = slug
        h["territory_id"] = None
        h["territory_dist_m"] = None
        h["territory_match"] = "no-data" if not rd else "unmatched"
        h["zone_counts"] = None
        area = nearest_area(reserve, h.get("x"), h.get("y"))
        h["area"] = area["area"] if area else None
        h["area_zh"] = area["area_zh"] if area else None
        h["habitat"] = area["habitat"] if area else None
        h["habitat_zh"] = area["habitat_zh"] if area else None
        cands = by_slug.get(slug) or []
        if cands and isinstance(h.get("x"), (int, float)):
            t = min(cands, key=lambda t: (t["x"] - h["x"]) ** 2 + (t["y"] - h["y"]) ** 2)
            d = _dist_m(h["x"], h["y"], t["x"], t["y"])
            h["territory_dist_m"] = round(d, 1)
            if d <= MATCH_MAX_M:
                h["territory_id"] = t["id"]
                h["territory_match"] = "high" if d <= MATCH_HIGH_M else "medium"
                h["zone_counts"] = {a: len(t[a]) for a in ACTIVITIES}
    idx = {h["index"]: h for h in herds}
    for a in animals:
        h = idx.get(a.get("herd_index"))
        src = h if h and h.get("habitat") else nearest_area(reserve, a.get("x"), a.get("y"))
        a["habitat"] = src.get("habitat") if src else None
        a["habitat_zh"] = src.get("habitat_zh") if src else None
        a["area"] = src.get("area") if src else None
        a["territory_id"] = h.get("territory_id") if h else None
    return match_summary(herds, reserve)


def match_summary(herds, reserve):
    rd = reserve_data(reserve)
    dists = [h["territory_dist_m"] for h in herds if h.get("territory_dist_m") is not None]
    matched = [h for h in herds if h.get("territory_id")]
    return {"available": bool(rd), "reserve": reserve, "herds": len(herds), "matched": len(matched),
            "high": sum(h.get("territory_match") == "high" for h in herds),
            "match_rate": round(len(matched) / len(herds), 4) if herds else None,
            "median_dist_m": round(statistics.median(dists), 1) if dists else None,
            "territories": len(rd["territories"]) if rd else 0}


def territory(reserve, tid):
    rd = reserve_data(reserve)
    return next((t for t in (rd or {}).get("territories", []) if t["id"] == tid), None)


def habitat_report(animals, low=0.5):
    """Observed gene-pool statistics per species x approximate habitat (known males only)."""
    groups = {}
    for a in animals:
        key = (a["species"], a.get("habitat") or "未知")
        g = groups.setdefault(key, {"species": a["species"], "species_zh": a.get("species_zh", ""),
                                    "habitat": key[1], "habitat_zh": a.get("habitat_zh") or "未知",
                                    "animals": 0, "herds": set(), "fit": [], "rare": 0})
        g["animals"] += 1
        g["herds"].add(a.get("herd_index"))
        g["rare"] += int(bool(a.get("variant")))
        if a.get("gender") == "M" and a.get("fitness") is not None:
            g["fit"].append(a["fitness"])
    out = []
    for g in groups.values():
        fit = g.pop("fit")
        g["herds"] = len(g["herds"])
        g["males_known"] = len(fit)
        g["avg_fitness"] = round(sum(fit) / len(fit), 5) if fit else None
        g["below_avg"] = sum(f < g["avg_fitness"] for f in fit) if fit else 0
        g["low"] = sum(f <= low for f in fit)
        g["band"] = knowledge.fitness_band(g["avg_fitness"])
        out.append(g)
    return sorted(out, key=lambda g: (g["species"], g["habitat"]))


def simulate_cull(animals, species, habitat, limit=5, mature_only=True, spread=True, max_fitness=None):
    """What-if: remove up to `limit` below-average known males; return old/new observed average.

    This recomputes an average only. It does not predict the game's spawn roll.
    """
    pool = [a for a in animals if a["species"] == species and (a.get("habitat") or "未知") == habitat
            and a.get("gender") == "M" and a.get("fitness") is not None]
    if not pool:
        return {"n": 0, "before": None, "after": None, "removed": [], "herds_touched": 0, "herds_total": 0}
    avg = sum(a["fitness"] for a in pool) / len(pool)
    elig = [a for a in pool if a["fitness"] < avg and (max_fitness is None or a["fitness"] <= max_fitness)
            and (not mature_only or a.get("age_stage") == "Mature")]
    elig.sort(key=lambda a: a["fitness"])
    chosen = []
    if spread:
        by = {}
        for a in elig:
            by.setdefault(a.get("herd_index"), []).append(a)
        queues = sorted(by.values(), key=lambda q: q[0]["fitness"])
        while len(chosen) < limit and any(queues):
            for q in queues:
                if q and len(chosen) < limit:
                    chosen.append(q.pop(0))
    else:
        chosen = elig[:limit]
    rest = [a["fitness"] for a in pool if a not in chosen]
    after = sum(rest) / len(rest) if rest else None
    return {"n": len(pool), "before": round(avg, 5), "after": round(after, 5) if after is not None else None,
            "delta": round(after - avg, 5) if after is not None else None,
            "eligible": len(elig), "removed": [a.get("id") for a in chosen],
            "herds_touched": len({a.get("herd_index") for a in chosen}),
            "herds_total": len({a.get("herd_index") for a in pool})}
