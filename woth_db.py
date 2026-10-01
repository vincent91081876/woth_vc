"""Parser for Way of the Hunter's custom 'Database' save (SaveData.sav).

Layout reverse-engineered from a real save (DatabaseSaveHeader, m_databaseCodeVersion 84):
  [GVAS header + 2 tagged props] [u32 0][u32 dbSize][binary database][name table]
  name table: u32 count, then {u64 nameHash, u32 len, UTF-16 chars}
Animal record (starts with the u64 hash of its Blueprint class, e.g. BP_CervusCanadensis_M_C):
  +0  u64 classHash   +8  u32 0   +12 u64 hash(common)
  +20 u32 age         +24 f32 fitness (males; 0 for females)
  +28 u8  sex (1=M, 2=F)          +29 u32 animal id (unique)
  +33 f32[3] position X,Y,Z (cm)  +45 f32[3] rotation
Herd record (starts with the hash of AIC_*AnimalGroup_<Latin>_C):
  +20 GUID[16]  +36 f32[3] position
"""
import math
import re
import struct

LATIN = {
    # Nez Perce Valley
    "OdocoileusHemionus": ("Mule Deer", "騾鹿", "Nez Perce Valley"),
    "OdocoileusVirginianus": ("Whitetail Deer", "白尾鹿", "Nez Perce Valley"),
    "CervusCanadensis": ("Rocky Mountain Elk", "洛磯山馬鹿", "Nez Perce Valley"),
    "AlcesAmericanus": ("Moose", "駝鹿", "Nez Perce Valley"),
    "OvisCanadensis": ("Bighorn Sheep", "大角羊", "Nez Perce Valley"),
    "OreamnosAmericanus": ("Mountain Goat", "雪羊", "Nez Perce Valley"),
    "UrsusAmericanus": ("American Black Bear", "美洲黑熊", "Nez Perce Valley"),
    "PumaConcolor": ("Cougar", "美洲獅", "Nez Perce Valley"),
    "CanisLupus": ("Gray Wolf", "灰狼", "Nez Perce Valley"),
    "CanisLatrans": ("Coyote", "郊狼", "Nez Perce Valley"),
    "VulpesVulpes": ("Red Fox", "赤狐", None),
    "TaxideaTaxus": ("American Badger", "美洲獾", "Nez Perce Valley"),
    "LepusAmericanus": ("Snowshoe Hare", "雪鞋兔", None),
    "PhasianusColchicus": ("Pheasant", "雉雞", None),
    "MeleagrisGallopavo": ("Eastern Wild Turkey", "東部野火雞", "Nez Perce Valley"),
    # Elkcrest Island. Keep this more-specific prefix after/beside the base
    # Gallopavo entry; species_of() deliberately chooses the longest match.
    "MeleagrisGallopavoMerriami": ("Merriam's Wild Turkey", "梅里亞姆野火雞", "Elkcrest Island"),
    "AnasPlatyrhynchos": ("Wild Duck", "綠頭鴨", None),
    "AythyaAffinis": ("Lesser Scaup", "小潛鴨", None),
    "AnserRossii": ("Ross's Goose", "羅氏雁", None),
    "AntilocapraAmericana": ("Pronghorn", "叉角羚", "Nez Perce Valley"),
    # Transylvania
    "CervusElaphus": ("Red Deer", "赤鹿", "Transylvania"),
    "CapreolusCapreolus": ("Roe Deer", "狍", "Transylvania"),
    "DamaDama": ("Fallow Deer", "黇鹿", None),
    "SusScrofa": ("Wild Boar", "野豬", None),
    "RupicapraRupicapra": ("Chamois", "岩羚羊", None),
    "OvisOrientalis": ("Mouflon", "歐洲盤羊", "Transylvania"),
    "OvisAries": ("Mouflon", "歐洲盤羊", "Transylvania"),
    "OvisGmelini": ("Mouflon", "歐洲盤羊", "Transylvania"),
    "UrsusArctos": ("Brown Bear", "棕熊", None),
    "LynxLynx": ("Eurasian Lynx", "歐亞猞猁", None),
    "CanisAureus": ("Golden Jackal", "金豺", "Transylvania"),
    "MelesMeles": ("Eurasian Badger", "歐亞獾", "Transylvania"),
    "LepusEuropaeus": ("European Hare", "歐洲野兔", None),
    "OryctolagusCuniculus": ("European Rabbit", "歐洲兔", None),
    "AnserAnser": ("Greylag Goose", "灰雁", None),
    # Aurora Shores (Alaska)
    "AlcesAlcesGigas": ("Alaska Moose", "阿拉斯加駝鹿", "Aurora Shores"),
    "AlcesAmericanusGigas": ("Alaska Moose", "阿拉斯加駝鹿", "Aurora Shores"),
    "RangiferTarandusGroenlandicus": ("Barren-Ground Caribou", "荒原馴鹿", "Aurora Shores"),
    "CervusCanadensisRoosevelti": ("Roosevelt Elk", "羅斯福馬鹿", None),
    "TaurotragusOryx": ("Common Eland", "大羚羊", "Tikamoon Plains"),
    "OvisMusimon": ("Mouflon", "歐洲盤羊", "Transylvania"),
    "RangiferTarandusGranti": ("Barren-Ground Caribou", "荒原馴鹿", "Aurora Shores"),
    "RangiferTarandus": ("Reindeer", "馴鹿", None),
    "BisonBison": ("Wood Bison", "森林野牛", "Aurora Shores"),
    "UrsusArctosMiddendorffi": ("Kodiak Bear", "科迪亞克棕熊", "Aurora Shores"),
    "OdocoileusHemionusSitkensis": ("Sitka Deer", "錫特卡鹿", "Aurora Shores"),
    "OvisDalli": ("Dall Sheep", "白大角羊", "Aurora Shores"),
    "OvibosMoschatus": ("Muskox", "麝牛", "Aurora Shores"),
    "VulpesLagopus": ("Arctic Fox", "北極狐", "Aurora Shores"),
    "AlopexLagopus": ("Arctic Fox", "北極狐", "Aurora Shores"),
    "GuloGulo": ("Wolverine", "狼獾", None),
    "MelanittaPerspicillata": ("Surf Scoter", "斑頭海番鴨", "Aurora Shores"),
    "BrantaCanadensis": ("Canada Goose", "加拿大雁", None),
    # Tikamoon Plains (Africa)
    "ConnochaetesTaurinus": ("Blue Wildebeest", "藍角馬", "Tikamoon Plains"),
    "ConnochaetesGnou": ("Black Wildebeest", "黑角馬", "Tikamoon Plains"),
    "OryxGazella": ("Gemsbok", "南非劍羚", "Tikamoon Plains"),
    "AntidorcasMarsupialis": ("Springbok", "跳羚", "Tikamoon Plains"),
    "AepycerosMelampus": ("Impala", "黑斑羚", "Tikamoon Plains"),
    "TragelaphusStrepsiceros": ("Greater Kudu", "大扭角林羚", "Tikamoon Plains"),
    "SyncerusCaffer": ("Cape Buffalo", "非洲水牛", "Tikamoon Plains"),
    "PantheraLeo": ("Lion", "獅子", "Tikamoon Plains"),
    "PantheraPardus": ("Leopard", "花豹", "Tikamoon Plains"),
    "CrocutaCrocuta": ("Spotted Hyena", "斑鬣狗", "Tikamoon Plains"),
    "PhacochoerusAfricanus": ("Warthog", "疣豬", "Tikamoon Plains"),
    "DamaliscusPygargus": ("Blesbok", "白臉牛羚", "Tikamoon Plains"),
    "EquusQuagga": ("Plains Zebra", "平原斑馬", "Tikamoon Plains"),
    "CanisMesomelas": ("Black-backed Jackal", "黑背胡狼", "Tikamoon Plains"),
    "LupulellaMesomelas": ("Black-backed Jackal", "黑背胡狼", "Tikamoon Plains"),
    "MellivoraCapensis": ("Honey Badger", "蜜獾", "Tikamoon Plains"),
    "AlopochenAegyptiaca": ("Egyptian Goose", "埃及雁", "Tikamoon Plains"),
    "NumidaMeleagris": ("Helmeted Guineafowl", "珠雞", "Tikamoon Plains"),
    # Matariki Park (New Zealand)
    "RusaUnicolor": ("Sambar Deer", "水鹿", "Matariki Park"),
    "CervusUnicolor": ("Sambar Deer", "水鹿", "Matariki Park"),
    "CervusNippon": ("Sika Deer", "梅花鹿", "Matariki Park"),
    "HemitragusJemlahicus": ("Himalayan Tahr", "喜馬拉雅塔爾羊", "Matariki Park"),
    "RusaTimorensis": ("Rusa Deer", "爪哇鹿", "Matariki Park"),
    "CapraHircus": ("Feral Goat", "野山羊", "Matariki Park"),
    # Lintukoto Reserve (Finland)
    "RangiferTarandusFennicus": ("Finnish Forest Reindeer", "芬蘭森林馴鹿", "Lintukoto Reserve"),
    "AlcesAlces": ("Eurasian Elk (Moose)", "歐亞駝鹿", None),
    "TetraoUrogallus": ("Capercaillie", "松雞", "Lintukoto Reserve"),
    "LyrurusTetrix": ("Black Grouse", "黑琴雞", "Lintukoto Reserve"),
    "LepusTimidus": ("Mountain Hare", "雪兔", "Lintukoto Reserve"),
    "NyctereutesProcyonoides": ("Raccoon Dog", "貉", "Lintukoto Reserve"),
}

CLASS_RE = re.compile(r"/BP_([A-Za-z]+?)_([MF])(?:_([A-Za-z0-9]+))?\.")
GROUP_RE = re.compile(r"AIC_\w*?Anim\w*?Group_([A-Za-z]+?)(?:_\w+)?_C$")
VARIANT_ZH = {"Albino": "白化", "Melanistic": "黑化", "Leucistic": "白變", "Piebald": "花斑", "Hollywood": "傳奇"}


def species_of(latin):
    best = None
    for k, v in LATIN.items():
        if latin.startswith(k) and (best is None or len(k) > len(best[0])):
            best = (k, v)
    if best:
        return best[1]
    pretty = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", latin)
    return (pretty, pretty, None)


def is_database_save(g):
    return "DatabaseSaveHeader" in g.header.get("class", "") or g.trailing > 100000


def read_name_table(raw, start):
    """Find the trailing name table (hash -> string) by parsing to exact EOF."""
    db_size = struct.unpack_from("<I", raw, start + 4)[0]
    guess = start + 8 + db_size
    for p in list(range(guess - 8, guess + 16)):
        try:
            n = struct.unpack_from("<I", raw, p)[0]
            if not 0 < n < 200000:
                continue
            q = p + 4
            tab = {}
            for _ in range(n):
                h = raw[q:q + 8]
                ln = struct.unpack_from("<I", raw, q + 8)[0]
                if ln > 4096:
                    raise ValueError
                tab[h] = raw[q + 12:q + 12 + ln * 2].decode("utf-16-le")
                q += 12 + ln * 2
            if q == len(raw):
                return tab, p
        except (struct.error, ValueError, UnicodeDecodeError):
            continue
    return {}, len(raw)


def _finite(*xs):
    return all(math.isfinite(x) and abs(x) < 1e8 for x in xs)


def parse(raw, props_end):
    """Return (animals, herds, info) from the decompressed save bytes."""
    names, table_at = read_name_table(raw, props_end)
    db = raw[:table_at]
    classes, groups = {}, {}
    for h, s in names.items():
        m = CLASS_RE.search(s)
        if m and "/Animals/" in s and "/Tracks/" not in s:
            classes[h] = (m.group(1), m.group(2), m.group(3) or "", s)
            continue
        m = GROUP_RE.search(s.split(".")[-1])
        if m and "/Animals/" in s:
            groups[h] = (m.group(1), s)
    events = []  # (offset, kind, data)
    for h, (latin, sex, variant, path) in classes.items():
        start = 0
        while True:
            p = db.find(h, start)
            if p < 0:
                break
            start = p + 1
            if p + 57 > len(db) or db[p + 8:p + 12] != b"\0\0\0\0":
                continue
            age, fit, sx, aid = struct.unpack_from("<IfBI", db, p + 20)
            x, y, z, rp, ry, rr = struct.unpack_from("<6f", db, p + 33)
            if sx not in (1, 2) or age > 1000 or not _finite(fit, x, y, z):
                continue
            events.append((p, "a", dict(latin=latin, sex="M" if sx == 1 else "F", variant=variant,
                                        cls=path.split(".")[-1], age=age, fitness=fit, aid=aid,
                                        x=x, y=y, z=z, yaw=ry)))
    for h, (latin, path) in groups.items():
        start = 0
        while True:
            p = db.find(h, start)
            if p < 0:
                break
            start = p + 1
            if p + 48 > len(db) or db[p + 8:p + 12] != b"\0\0\0\0":
                continue
            guid = db[p + 20:p + 36].hex()
            x, y, z = struct.unpack_from("<3f", db, p + 36)
            if not _finite(x, y, z):
                continue
            events.append((p, "h", dict(latin=latin, guid=guid, x=x, y=y, z=z, mission="Mission" in path)))
    events.sort(key=lambda e: e[0])

    herds, animals, seen = [], [], set()
    cur = None
    for off, kind, e in events:
        if kind == "h":
            sp = species_of(e["latin"])
            cur = {"id": e["guid"][:10], "guid": e["guid"], "index": len(herds), "latin": e["latin"],
                   "species": sp[0], "species_zh": sp[1], "map": sp[2], "x": e["x"], "y": e["y"], "z": e["z"],
                   "size": 0, "alive": 0, "males": 0, "females": 0, "offset": off, "path": f"db@{off}"}
            herds.append(cur)
            continue
        if e["aid"] in seen:
            continue
        seen.add(e["aid"])
        sp = species_of(e["latin"])
        herd = cur if cur is not None and cur["latin"] and e["latin"].startswith(cur["latin"][:8]) and off - cur["offset"] < 60000 else None
        var = e["variant"]
        a = {
            "species": sp[0], "species_zh": sp[1], "tier": None, "latin": e["latin"],
            "gender": e["sex"], "age": e["age"], "age_label": str(e["age"]),
            "weight": None, "score": None,
            "fitness": round(e["fitness"], 4) if e["sex"] == "M" else None,
            "variant": var, "variant_zh": VARIANT_ZH.get(var, var),
            "x": e["x"], "y": e["y"], "z": e["z"],
            "id": str(e["aid"]), "dead": False,
            "herd_id": herd["id"] if herd else "-", "herd_index": herd["index"] if herd else -1,
            "map": sp[2] or (herd["map"] if herd else None),
            "path": f"db@{off}", "key": f"id:{e['aid']}",
            "fields": {"class": e["cls"], "age": e["age"], "fitness": e["fitness"], "id": e["aid"],
                       "X": e["x"], "Y": e["y"], "Z": e["z"], "yaw": e["yaw"]},
        }
        if herd:
            herd["size"] += 1
            herd["alive"] += 1
            herd["males" if a["gender"] == "M" else "females"] += 1
        animals.append(a)
    herds = [h for h in herds if h["size"] > 0]
    for i, h in enumerate(herds):
        h["index"] = i
    idx = {h["id"]: h["index"] for h in herds}
    for a in animals:
        a["herd_index"] = idx.get(a["herd_id"], -1)
    # decide the reserve by majority of map-specific species
    votes = {}
    for a in animals:
        if a["map"]:
            votes[a["map"]] = votes.get(a["map"], 0) + 1
    reserve = max(votes, key=votes.get) if votes else None
    # Elkcrest reuses mostly Alaska/Idaho animals. Merriam's turkey is its
    # strongest signature; Kodiak bear + cougar is a fallback for saves where
    # no turkey happens to be present in the population.
    species_present = {a["species"] for a in animals}
    if any("Merriami" in a["latin"] for a in animals) or (
            "Kodiak Bear" in species_present and "Cougar" in species_present):
        reserve = "Elkcrest Island"
    for a in animals:
        a["map"] = a["map"] or reserve
    for h in herds:
        h["map"] = h["map"] or reserve
    by = {}
    for a in animals:
        if a["fitness"] is not None:
            by.setdefault(a["species"], []).append(a["fitness"])
    for v in by.values():
        v.sort()
    for a in animals:
        a["stars"] = None
        a["percentile"] = None
        if a["fitness"] is not None:
            v = by[a["species"]]
            a["percentile"] = round(100.0 * sum(1 for x in v if x < a["fitness"]) / max(1, len(v) - 1), 1) if len(v) > 1 else 100.0
    info = {"format": "WOTH Database", "names": len(names), "db_bytes": table_at - props_end,
            "reserve": reserve, "record_classes": len(classes), "group_classes": len(groups)}
    return animals, herds, info
