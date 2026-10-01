"""v4.0 straight-line expedition planner for observed WOTH animals.

Routes are world-coordinate planning aids.  They do not account for roads,
terrain, private-land access, wind, hunting pressure, or animal movement.
"""
import math

import habitat as habitat_data


def _dist(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"]) / 100.0


def _two_opt(route, start):
    """Small open-path 2-opt pass; deterministic and fast for <=50 stops."""
    def length(seq):
        cur, total = start, 0.0
        for x in seq:
            total += _dist(cur, x)
            cur = x
        return total
    best, best_len = list(route), length(route)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best) + 1):
                cand = best[:i] + list(reversed(best[i:j])) + best[j:]
                n = length(cand)
                if n + .01 < best_len:
                    best, best_len, improved = cand, n, True
                    improved = True
        route = best
    return best


def plan(animals, herds, reserve, species=None, habitat=None, limit=12,
         mature_only=True, max_fitness=None, exclude_rare=True, activity="Drink",
         start_x=None, start_y=None, ids=None):
    limit = max(1, min(50, int(limit or 12)))
    ids = {str(x) for x in (ids or [])}
    pool = [a for a in animals if (not species or a.get("species") == species)
            and (not habitat or (a.get("habitat") or "未知") == habitat)]
    known = [a for a in pool if a.get("gender") == "M" and a.get("fitness") is not None]
    avg_by = {}
    for a in known:
        key = (a["species"], a.get("habitat") or "未知")
        avg_by.setdefault(key, []).append(a["fitness"])
    avg_by = {k: sum(v) / len(v) for k, v in avg_by.items()}
    if ids:
        candidates = [a for a in pool if str(a.get("id")) in ids]
    else:
        candidates = [a for a in known
                      if a["fitness"] < avg_by[(a["species"], a.get("habitat") or "未知")]
                      and (not mature_only or a.get("age_stage") == "Mature")
                      and (max_fitness is None or a["fitness"] <= max_fitness)
                      and (not exclude_rare or not a.get("variant"))]
    # Females (and animals without a Fitness value) carry fitness=None: sort them last instead of crashing.
    candidates.sort(key=lambda a: (a["fitness"] if a.get("fitness") is not None else 1, a.get("id", "")))
    # One stop per herd first, matching the official advice to spread management.
    chosen, used = [], set()
    for a in candidates:
        if a.get("herd_index") not in used:
            chosen.append(a)
            used.add(a.get("herd_index"))
            if len(chosen) >= limit:
                break
    if len(chosen) < limit:
        for a in candidates:
            if a not in chosen:
                chosen.append(a)
                if len(chosen) >= limit:
                    break
    herd_by = {h["index"]: h for h in herds}
    stops = []
    for a in chosen:
        h = herd_by.get(a.get("herd_index")) or {}
        t = habitat_data.territory(reserve, h.get("territory_id"))
        zone = habitat_data.nearest_zone(t, activity, a.get("x"), a.get("y")) if t else None
        x, y = ((zone["x"], zone["y"]) if zone else
                (h.get("x"), h.get("y")) if h.get("x") is not None else
                (a.get("x"), a.get("y")))
        if x is None or y is None:
            continue
        stops.append({
            "x": x, "y": y, "animal_x": a.get("x"), "animal_y": a.get("y"),
            "id": a.get("id"), "species": a.get("species"), "species_zh": a.get("species_zh"),
            "gender": a.get("gender"), "age": a.get("age"), "age_stage": a.get("age_stage"),
            "fitness": a.get("fitness"), "variant": a.get("variant") or "",
            "herd_id": a.get("herd_id"), "herd_index": a.get("herd_index"),
            "habitat": a.get("habitat"), "habitat_zh": a.get("habitat_zh"),
            "area": a.get("area"), "territory_id": h.get("territory_id"),
            "activity": activity, "zone_dist_from_animal_m": zone.get("dist_m") if zone else None,
            "point_kind": f"{activity} need zone" if zone else "herd/animal position",
            "pool_average": round(avg_by.get((a["species"], a.get("habitat") or "未知"), 0), 5),
        })
    if not stops:
        return {"reserve": reserve, "stops": [], "eligible": len(candidates),
                "straight_line_km": 0, "caveat": _caveat()}
    if start_x is None or start_y is None:
        start = {"x": sum(x["x"] for x in stops) / len(stops),
                 "y": sum(x["y"] for x in stops) / len(stops), "kind": "candidate centroid"}
    else:
        start = {"x": float(start_x), "y": float(start_y), "kind": "user coordinate"}
    left, ordered, cur = list(stops), [], start
    while left:
        nxt = min(left, key=lambda x: _dist(cur, x))
        ordered.append(nxt)
        left.remove(nxt)
        cur = nxt
    ordered = _two_opt(ordered, start)
    cur, total = start, 0.0
    for i, stop in enumerate(ordered, 1):
        leg = _dist(cur, stop)
        total += leg
        stop["order"] = i
        stop["leg_m"] = round(leg, 1)
        stop["cumulative_m"] = round(total, 1)
        cur = stop
    return {
        "reserve": reserve, "start": start, "eligible": len(candidates), "stops": ordered,
        "straight_line_km": round(total / 1000, 2),
        "filters": {"species": species, "habitat": habitat, "limit": limit,
                    "mature_only": mature_only, "max_fitness": max_fitness,
                    "exclude_rare": exclude_rare, "activity": activity, "manual_ids": sorted(ids)},
        "caveat": _caveat(),
    }


def _caveat():
    return ("直線順序只使用存檔／需求區世界座標，不含道路、地形、風向、私人土地、"
            "狩獵壓力或動物移動；候選是觀察輔助，不是獵殺指令。")