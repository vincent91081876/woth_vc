"""v4 read-only player-state extraction."""
import math
import re
import struct

import woth_db

PLAYER_RE = re.compile(r"(player|hunter|character|pawn|avatar)", re.I)
POSITION_RE = re.compile(r"(location|position|transform|translation|coordinates?|coords|world)", re.I)

MAP_CODES = {
    "Nez Perce Valley": ("Idaho_01", "Idaho"),
    "Transylvania": ("Transylvania_01", "Transylvania"),
    "Aurora Shores": ("Alaska_01", "Alaska"),
    "Tikamoon Plains": ("Africa_01", "Africa"),
    "Matariki Park": ("NewZealand_01", "NewZealand"),
    "Lintukoto Reserve": ("Finland_01", "Finland"),
    "Elkcrest Island": ("KodiakIsland_01", "KodiakIsland", "Elkcrest"),
}


def _vector(value):
    if not isinstance(value, dict):
        return None
    low = {str(k).lower(): k for k in value}
    if not all(k in low for k in ("x", "y", "z")):
        return None
    xyz = [value[low[k]] for k in ("x", "y", "z")]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and abs(v) < 1e8 for v in xyz):
        return None
    return tuple(float(v) for v in xyz)


def _walk(value, path=()):
    vec = _vector(value)
    if vec is not None:
        yield path, vec
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, path + (str(key),))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _walk(child, path + (f"[{i}]",))


def _bounds(reserve, cfg):
    return (cfg.get("maps") or {}).get(reserve) or {}


def _inside(x, y, reserve, cfg):
    b = _bounds(reserve, cfg)
    return bool(b) and b["x_min"] <= x <= b["x_max"] and b["y_min"] <= y <= b["y_max"]


def current_map_evidence(raw, props_end, reserve):
    """Return a map-code observation from the Database name table."""
    try:
        names, table_at = woth_db.read_name_table(raw, props_end)
        db = raw[:table_at]
    except Exception:
        return None
    expected = MAP_CODES.get(reserve, ())
    found = []
    for code in expected:
        hits = [(h, s) for h, s in names.items() if s == code and h in db]
        if hits:
            found.append({"code": code, "occurrences": sum(db.count(h) for h, _ in hits)})
    if not found:
        return None
    return {"reserve": reserve, "codes": found, "source": "WOTH Database name table"}


# The player's last saved world position sits in a fixed-shape record near the
# end of the Database body (about 3.6 KB before the name table). It was found by
# comparing saves where the player walked ~400 m and matching the in-game map
# arrow; the map-hash "state trailer" below is a parked vehicle, not the player.
_PLAYER_PREFIX = bytes.fromhex("0108000000010000000000000000020000000102000000")
_PLAYER_SUFFIX = bytes.fromhex("01000000000202000000")


def _database_player_position(raw, props_end, reserve, cfg):
    """Read the player's last saved XYZ (Unreal cm) from the Database tail record."""
    try:
        _names, table_at = woth_db.read_name_table(raw, props_end)
        db = raw[:table_at]
    except Exception:
        return None
    found, start = {}, 0
    while True:
        p = db.find(_PLAYER_PREFIX, start)
        if p < 0:
            break
        start = p + 1
        head = p + len(_PLAYER_PREFIX)
        q = head + 12
        if q + 12 + len(_PLAYER_SUFFIX) > len(db):
            continue
        if db[q + 12:q + 12 + len(_PLAYER_SUFFIX)] != _PLAYER_SUFFIX:
            continue
        x, y, z = struct.unpack_from("<3f", db, q)
        if not all(math.isfinite(v) and abs(v) < 1e8 for v in (x, y, z)):
            continue
        if not _inside(x, y, reserve, cfg):
            continue
        found[(x, y, z)] = {"offset": q, "x": x, "y": y, "z": z,
                            "aux": struct.unpack_from("<3f", db, head)}
    return next(iter(found.values())) if len(found) == 1 else None


def _database_vehicle_transform(raw, props_end, reserve, cfg):
    """Read the map-hash state trailer (a parked vehicle, NOT the player).

    A current-map hash anchors a fixed state trailer: rotation at +53, XYZ at
    +65, followed by AnimalGroupPawn at +102. Every structural and bounds
    check must pass and the candidate must be unique.
    """
    try:
        names, table_at = woth_db.read_name_table(raw, props_end)
        db = raw[:table_at]
    except Exception:
        return None
    group_hashes = {
        h for h, name in names.items()
        if name == "/Script/WayOfTheHunter.AnimalGroupPawn"
    }
    found = []
    for code in MAP_CODES.get(reserve, ()):
        for map_hash, name in names.items():
            if name != code:
                continue
            start = 0
            while True:
                p = db.find(map_hash, start)
                if p < 0:
                    break
                start = p + 1
                if p + 110 > len(db) or db[p + 102:p + 110] not in group_hashes:
                    continue
                try:
                    rotation = struct.unpack_from("<3f", db, p + 53)
                    x, y, z = struct.unpack_from("<3f", db, p + 65)
                except struct.error:
                    continue
                if not all(math.isfinite(v) and abs(v) < 1e8
                           for v in (*rotation, x, y, z)):
                    continue
                if not _inside(x, y, reserve, cfg):
                    continue
                found.append({"code": code, "offset": p, "rotation": rotation,
                              "x": x, "y": y, "z": z})
    return found[0] if len(found) == 1 else None


def inspect(props, raw, props_end, reserve, cfg, is_database=False):
    candidates = []
    for path, (x, y, z) in _walk(props):
        label = "/".join(path)
        player = bool(PLAYER_RE.search(label))
        position = bool(POSITION_RE.search(label))
        if not (player and position):
            continue
        inside = _inside(x, y, reserve, cfg)
        candidates.append({
            "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
            "path": label, "inside_bounds": inside,
            "confidence": "exact" if inside else "candidate",
            "reason": ("語意明確的玩家位置 Vector，且位於目前地圖範圍內"
                       if inside else "語意像玩家位置，但座標不在目前地圖範圍內"),
        })
    exact = next((c for c in candidates if c["confidence"] == "exact"), None)
    map_evidence = current_map_evidence(raw, props_end, reserve) if is_database else None
    database_exact = (_database_player_position(raw, props_end, reserve, cfg)
                      if is_database else None)
    vehicle = _database_vehicle_transform(raw, props_end, reserve, cfg) if is_database else None
    vehicle_info = ({"x": round(vehicle["x"], 3), "y": round(vehicle["y"], 3),
                     "z": round(vehicle["z"], 3), "note": "位置在玩家移動時不變，推測為停放的載具；非玩家位置"}
                    if vehicle else None)
    if database_exact:
        return {
            "available": True, "confidence": "exact",
            "source": "WOTH Database player-position record (tail of database)",
            "reserve": reserve,
            "position": {k: round(database_exact[k], 3) for k in ("x", "y", "z")},
            "path": "Database/PlayerPosition",
            "inside_bounds": True, "current_map": map_evidence,
            "candidates": candidates, "vehicle": vehicle_info,
            "verification": "moved-save-diff+in-game-map/code-version-84",
            "note": ("這是存檔最後寫入的位置，不是遊戲仍執行時的即時 GPS。"
                     "欄位以走動前／後存檔及遊戲內地圖箭頭交叉驗證。"),
        }
    if exact:
        return {
            "available": True, "confidence": "exact", "source": "tagged GVAS Vector",
            "reserve": reserve, "position": {k: exact[k] for k in ("x", "y", "z")},
            "path": exact["path"], "inside_bounds": True, "current_map": map_evidence,
            "candidates": candidates,
            "note": "這是存檔最後寫入的位置，不是遊戲仍執行時的即時 GPS。",
        }
    return {
        "available": False, "confidence": "unavailable", "source": None,
        "reserve": reserve, "position": None, "path": None, "inside_bounds": None,
        "current_map": map_evidence, "candidates": candidates, "vehicle": vehicle_info,
        "note": ("目前格式沒有通過驗證的玩家座標。已確認目前地圖，但不會把匿名 float "
                 "三元組或地圖中心冒充玩家位置。"),
    }
