"""v4.0 Population Observatory.

Turns a chronological series of already-parsed, read-only save states into an
evidence ledger.  It reports observations and deltas; it never predicts trophy
scores, harvest outcomes, or future RNG.
"""
from collections import defaultdict

import extract
import knowledge

YEAR_TURN_RATIO = 0.5


def _reserve(state):
    return state.get("reserve") or (state.get("db_info") or {}).get("reserve")


def _pool(animals):
    """Observed male-fitness pools keyed by species x approximate habitat."""
    out = {}
    for a in animals:
        if a.get("gender") != "M" or a.get("fitness") is None:
            continue
        key = (a.get("species"), a.get("habitat") or "未知")
        g = out.setdefault(key, {"values": [], "animals": 0, "herds": set()})
        g["values"].append(a["fitness"])
        g["animals"] += 1
        g["herds"].add(a.get("herd_index"))
    for g in out.values():
        g["average"] = sum(g["values"]) / len(g["values"])
        g["high80"] = sum(x >= .8 for x in g["values"])
        g["low40"] = sum(x < .4 for x in g["values"])
        g["herds"] = len(g["herds"])
    return out


def _transition(old, new, year_index):
    d = extract.diff(old["animals"], new["animals"])
    old_by = {a["key"]: a for a in old["animals"]}
    persisting = [a for a in new["animals"] if a["key"] in old_by]
    aged = sum((a.get("age") or 0) > (old_by[a["key"]].get("age") or 0) for a in persisting)
    year_turn = bool(persisting) and aged / len(persisting) >= YEAR_TURN_RATIO
    if year_turn:
        year_index += 1
    before, after = _pool(old["animals"]), _pool(new["animals"])
    removed_by, spawned_by = defaultdict(list), defaultdict(list)
    for a in d["removed"]:
        removed_by[(a.get("species"), a.get("habitat") or "未知")].append(a)
    for a in d["added"]:
        spawned_by[(a.get("species"), a.get("habitat") or "未知")].append(a)
    rows = []
    for key in sorted(set(before) | set(after) | set(removed_by) | set(spawned_by)):
        b, a = before.get(key), after.get(key)
        removed, spawned = removed_by[key], spawned_by[key]
        removed_known = [x for x in removed if x.get("gender") == "M" and x.get("fitness") is not None]
        spawned_known = [x for x in spawned if x.get("gender") == "M" and x.get("fitness") is not None]
        bavg = b.get("average") if b else None
        rows.append({
            "species": key[0], "species_zh": next((x.get("species_zh") for x in
                                                   (removed + spawned + new["animals"])
                                                   if x.get("species") == key[0]), ""),
            "habitat": key[1],
            "before_males": len(b["values"]) if b else 0,
            "after_males": len(a["values"]) if a else 0,
            "before_avg": round(bavg, 5) if bavg is not None else None,
            "after_avg": round(a["average"], 5) if a else None,
            "avg_delta": round(a["average"] - bavg, 5) if a and bavg is not None else None,
            "removed": len(removed), "removed_known_males": len(removed_known),
            "removed_below_avg": sum(x["fitness"] < bavg for x in removed_known)
                                 if bavg is not None else None,
            "spawned": len(spawned), "spawned_known_males": len(spawned_known),
            "spawned_avg": round(sum(x["fitness"] for x in spawned_known) / len(spawned_known), 5)
                           if spawned_known else None,
        })
    return ({
        "from": old["mtime"], "to": new["mtime"], "from_sha1": old["sha1"], "to_sha1": new["sha1"],
        "year_turn": year_turn, "year_index": year_index, "persisting": len(persisting), "aged": aged,
        "removed": len(d["removed"]), "spawned": len(d["added"]), "habitats": rows,
    }, year_index, d)


def analyse(states):
    """Build the observatory report from full scan states, oldest to newest."""
    unique = {}
    for s in states:
        unique[s["sha1"]] = s
    states = sorted(unique.values(), key=lambda s: s["mtime"])
    if not states:
        return {"states": 0, "transitions": [], "scorecards": [], "cohorts": [], "trend": []}

    ledger, transitions, year_index = {}, [], 0
    trend = []
    for si, s in enumerate(states):
        if si:
            tr, year_index, _ = _transition(states[si - 1], s, year_index)
            transitions.append(tr)
        pools = _pool(s["animals"])
        for (species, habitat), g in pools.items():
            trend.append({"state_index": si, "time": s["mtime"], "year_index": year_index,
                          "species": species, "habitat": habitat, "males": len(g["values"]),
                          "herds": g["herds"], "average": round(g["average"], 5),
                          "fitness_band": knowledge.fitness_band(g["average"]),
                          "high80": g["high80"], "low40": g["low40"]})
        for a in s["animals"]:
            item = ledger.setdefault(a["key"], {
                "key": a["key"], "id": a.get("id"), "species": a.get("species"),
                "species_zh": a.get("species_zh"), "gender": a.get("gender"),
                "variant": a.get("variant") or "", "variant_zh": a.get("variant_zh") or "",
                "first_seen": s["mtime"], "last_seen": s["mtime"], "first_state": si,
                "last_state": si, "observations": 0, "ages": [], "herds": [], "habitats": [],
                "fitness_first": a.get("fitness"), "fitness_last": a.get("fitness"),
            })
            item["last_seen"], item["last_state"] = s["mtime"], si
            item["observations"] += 1
            if a.get("age") is not None:
                item["ages"].append(a["age"])
            item["herds"].append(a.get("herd_id"))
            item["habitats"].append(a.get("habitat") or "未知")
            item["fitness_last"] = a.get("fitness")
            item["age_stage"] = a.get("age_stage")
            item["age_limit_status"] = a.get("age_limit_status")
            item["area"] = a.get("area")
            item["habitat"] = a.get("habitat")
            item["herd_id"] = a.get("herd_id")

    current_keys = {a["key"] for a in states[-1]["animals"]}
    cohorts = []
    for x in ledger.values():
        ages = x.pop("ages")
        herds, habitats = x.pop("herds"), x.pop("habitats")
        x["age_first"] = ages[0] if ages else None
        x["age_last"] = ages[-1] if ages else None
        x["age_gain"] = ages[-1] - ages[0] if ages else None
        x["herd_changes"] = sum(a != b for a, b in zip(herds, herds[1:]))
        x["habitat_changes"] = sum(a != b for a, b in zip(habitats, habitats[1:]))
        x["status"] = "present" if x["key"] in current_keys else "gone"
        x["cohort"] = "baseline" if x["first_state"] == 0 else f"transition-{x['first_state']}"
        cohorts.append(x)

    agg = {}
    for tr in transitions:
        for h in tr["habitats"]:
            key = (h["species"], h["habitat"])
            g = agg.setdefault(key, {
                "species": h["species"], "species_zh": h["species_zh"], "habitat": h["habitat"],
                "transitions": 0, "year_turns": 0, "removed": 0, "spawned": 0,
                "removed_known_males": 0, "removed_below_avg": 0, "judged_removed": 0,
                "spawned_fitness": [], "deltas": [],
            })
            g["transitions"] += 1
            g["year_turns"] += int(tr["year_turn"])
            g["removed"] += h["removed"]
            g["spawned"] += h["spawned"]
            g["removed_known_males"] += h["removed_known_males"]
            if h["removed_below_avg"] is not None:
                g["removed_below_avg"] += h["removed_below_avg"]
                g["judged_removed"] += h["removed_known_males"]
            if h["spawned_avg"] is not None:
                g["spawned_fitness"].append(h["spawned_avg"])
            if h["avg_delta"] is not None:
                g["deltas"].append(h["avg_delta"])
    first_pool, last_pool = _pool(states[0]["animals"]), _pool(states[-1]["animals"])
    scorecards = []
    for key in sorted(set(first_pool) | set(last_pool) | set(agg)):
        g = agg.get(key, {"species": key[0], "species_zh": "", "habitat": key[1],
                          "transitions": 0, "year_turns": 0, "removed": 0, "spawned": 0,
                          "removed_known_males": 0, "removed_below_avg": 0,
                          "judged_removed": 0, "spawned_fitness": [], "deltas": []})
        f, l = first_pool.get(key), last_pool.get(key)
        first_avg, last_avg = (f or {}).get("average"), (l or {}).get("average")
        scorecards.append({
            **{k: v for k, v in g.items() if k not in ("spawned_fitness", "deltas")},
            "first_avg": round(first_avg, 5) if first_avg is not None else None,
            "last_avg": round(last_avg, 5) if last_avg is not None else None,
            "net_delta": round(last_avg - first_avg, 5)
                         if first_avg is not None and last_avg is not None else None,
            "current_males": len(l["values"]) if l else 0,
            "removed_below_rate": round(g["removed_below_avg"] / g["judged_removed"], 4)
                                  if g["judged_removed"] else None,
            "spawned_avg": round(sum(g["spawned_fitness"]) / len(g["spawned_fitness"]), 5)
                           if g["spawned_fitness"] else None,
            "confidence": ("multi-year" if g["year_turns"] >= 2 else
                           "one-year" if g["year_turns"] == 1 else
                           "snapshot-only"),
        })

    latest = states[-1]["animals"]
    watch = [a for a in latest if a.get("variant") or a.get("age_limit_status") or
             (a.get("gender") == "M" and a.get("fitness") is not None and a["fitness"] >= .8)]
    # years_to_limit == 0.0 means "already at the age limit": it is a real value, not a missing one.
    watch.sort(key=lambda a: (not bool(a.get("variant")),
                              a["years_to_limit"] if a.get("years_to_limit") is not None else 999,
                              -(a.get("fitness") or -1)))
    return {
        "read_only_source": True, "reserve": _reserve(states[-1]), "states": len(states),
        "first_time": states[0]["mtime"], "last_time": states[-1]["mtime"],
        "year_turns": sum(t["year_turn"] for t in transitions),
        "transition_count": len(transitions), "transitions": transitions,
        "scorecards": scorecards, "trend": trend,
        "cohorts": sorted(cohorts, key=lambda x: (-x["last_seen"], x["species"] or "", x["id"] or "")),
        "cohort_count": len(cohorts), "present": len(current_keys),
        "gone": sum(x["status"] == "gone" for x in cohorts),
        "watchlist": watch[:500],
        "method_note": ("年度更替以持續個體至少 50% 年齡增加推定；平均值只使用存檔中有 Fitness 的公獸。"
                        "結果是快照觀察，不是遊戲 RNG 或因果模型。"),
    }