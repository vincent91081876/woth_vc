"""Synthetic WOTH *Database* save (Nez Perce Valley) placed on real Toolbox territories.

Used for v3.0 journal / habitat / browser tests. Real saves are never bundled.
  build(year=0, remove=(), spawn=0, seed=7) -> bytes
"""
import json, os, random, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from make_sample import fstr, p_int, p_bool, none  # noqa: E402

COMMON = b"\x4f\x40\x90\x2f\x3b\x6a\xe1\x9a"
SPECIES = {  # slug -> (latin, herds, size range)
    "mule-deer": ("OdocoileusHemionus", 14, (3, 7)),
    "white-tailed-deer": ("OdocoileusVirginianus", 12, (3, 6)),
    "rocky-mountain-elk": ("CervusCanadensis", 8, (4, 9)),
    "western-moose": ("AlcesAmericanus", 6, (1, 3)),
    "american-black-bear": ("UrsusAmericanus", 5, (1, 2)),
    "wild-duck": ("AnasPlatyrhynchos", 6, (4, 8)),
}


def _h(s):
    return struct.pack("<Q", hash(s) & 0xFFFFFFFFFFFFFFFF) if False else bytes(
        (sum(ord(c) * (i + 7) for i, c in enumerate(s)) >> k) & 0xFF for k in range(0, 64, 8))


def build(year=0, remove=(), spawn=0, seed=7):
    rng = random.Random(seed)
    with open(os.path.join(os.path.dirname(HERE), "data", "need_zones.json"), encoding="utf-8") as f:
        zones = json.load(f)
    terr = zones["reserves"]["Nez Perce Valley"]["territories"]
    names, body, aid = {}, b"", 1000
    for slug, (latin, n_herds, (lo, hi)) in SPECIES.items():
        cls = {}
        for sex, var in (("M", ""), ("F", ""), ("M", "Albino")):
            nm = f"BP_{latin}_{sex}" + (f"_{var}" if var else "")
            path = f"/Game/TEH/Animals/Big/{latin}/{nm}.{nm}_C"
            cls[(sex, var)] = _h(path)
            names[cls[(sex, var)]] = path
        gpath = f"/Game/TEH/Animals/Big/{latin}/AIC_GroundAnimalGroup_{latin}.AIC_GroundAnimalGroup_{latin}_C"
        gh = _h(gpath)
        names[gh] = gpath
        mine = [t for t in terr if t["slug"] == slug]
        for t in rng.sample(mine, min(n_herds, len(mine))):
            hx, hy = t["x"] + rng.uniform(-8000, 8000), t["y"] + rng.uniform(-8000, 8000)
            body += gh + b"\0" * 4 + COMMON + bytes(rng.getrandbits(8) for _ in range(16)) + struct.pack("<3f", hx, hy, -8e4) + b"\0" * 64
            for i in range(rng.randint(lo, hi)):
                aid += 1
                sex = "M" if i % 2 == 0 else "F"
                var = "Albino" if (sex == "M" and rng.random() < 0.03) else ""
                age = rng.randint(1, 9) + year
                fit = round(rng.random(), 4) if sex == "M" else 0.0
                if aid in remove:
                    continue
                body += cls[(sex, var)] + b"\0" * 4 + COMMON + struct.pack("<IfBI", age, fit, 1 if sex == "M" else 2, aid)
                body += struct.pack("<6f", hx + rng.uniform(-3000, 3000), hy + rng.uniform(-3000, 3000), -8e4, 0, rng.uniform(0, 360), 0) + b"\0" * 40
            for k in range(spawn if slug == "mule-deer" and t is mine[0] else 0):
                pass
        if slug == "mule-deer" and spawn:
            t = mine[0]
            body += gh + b"\0" * 4 + COMMON + bytes(range(16)) + struct.pack("<3f", t["x"], t["y"], -8e4) + b"\0" * 64
            for k in range(spawn):
                body += cls[("M", "")] + b"\0" * 4 + COMMON + struct.pack("<IfBI", 1, 0.9, 1, 900000 + k)
                body += struct.pack("<6f", t["x"] + 500 * k, t["y"], -8e4, 0, 0, 0) + b"\0" * 40
    table = struct.pack("<I", len(names)) + b"".join(h + struct.pack("<I", len(s)) + s.encode("utf-16-le") for h, s in names.items())
    header = (b"GVAS" + struct.pack("<ii", 2, 522) + struct.pack("<HHHI", 4, 27, 2, 18319896)
              + fstr("++UE4+Release-4.27") + struct.pack("<ii", 3, 0)
              + fstr("/Script/WayOfTheHunter.DatabaseSaveHeader"))
    props = p_int("m_databaseCodeVersion", 84) + p_bool("m_isMigrated", 1) + none()
    return header + props + struct.pack("<II", 0, len(body)) + body + table


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "SaveData.sav"
    open(out, "wb").write(build())
    print("written", out)
