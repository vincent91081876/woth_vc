"""Build synthetic WOTH-style GVAS saves for testing (the real field names are unknown)."""
import os
import random
import struct
import sys
import uuid
import zlib


def fstr(s):
    if s == "":
        return struct.pack("<i", 0)
    b = s.encode("utf-8") + b"\0"
    return struct.pack("<i", len(b)) + b


def prop(name, ptype, body, header=b""):
    return fstr(name) + fstr(ptype) + struct.pack("<q", len(body)) + header + b"\0" + body


def p_int(n, v): return prop(n, "IntProperty", struct.pack("<i", v))
def p_float(n, v): return prop(n, "FloatProperty", struct.pack("<f", v))
def p_str(n, v): return prop(n, "StrProperty", fstr(v))
def p_bool(n, v): return fstr(n) + fstr("BoolProperty") + struct.pack("<q", 0) + bytes([v]) + b"\0"
def p_enum(n, en, v): return prop(n, "EnumProperty", fstr(v), fstr(en))
def p_byte_enum(n, en, v): return prop(n, "ByteProperty", fstr(v), fstr(en))
def none(): return fstr("None")


def p_struct(n, st, body):
    return prop(n, "StructProperty", body, fstr(st) + b"\0" * 16)


def vec(x, y, z): return struct.pack("<fff", x, y, z)


def p_array_struct(n, st, elems):
    inner = b"".join(elems)
    body = struct.pack("<i", len(elems)) + fstr(n) + fstr("StructProperty") + struct.pack("<q", len(inner)) + fstr(st) + b"\0" * 16 + b"\0" + inner
    return prop(n, "ArrayProperty", body, fstr("StructProperty"))


def p_array_bytes(n, blob):
    return prop(n, "ArrayProperty", struct.pack("<i", len(blob)) + blob, fstr("ByteProperty"))


def p_map_str_int(n, d):
    body = struct.pack("<ii", 0, len(d)) + b"".join(fstr(k) + struct.pack("<i", v) for k, v in d.items())
    return prop(n, "MapProperty", body, fstr("StrProperty") + fstr("IntProperty"))


BP = "_{}_" + "0123456789ABCDEF0123456789ABCDEF"


def animal(rng, species_enum=None, dead=False):
    g = rng.choice(["EGender::Male", "EGender::Female"])
    body = (p_struct("AnimalGuid", "Guid", uuid.UUID(int=rng.getrandbits(128)).bytes)
            + p_enum("Gender", "EGender", g)
            + p_byte_enum("Age" + BP.format(5), "EAnimalAge", rng.choice(["EAnimalAge::Young", "EAnimalAge::Adult", "EAnimalAge::Mature"]))
            + p_float("Weight" + BP.format(7), rng.uniform(60, 220))
            + p_float("TrophyScore", rng.uniform(50, 500) if g.endswith("Male") else 0.0)
            + p_float("Fitness", rng.random())
            + p_bool("IsDead", dead)
            + p_struct("Location", "Vector", vec(rng.uniform(-3e5, 3e5), rng.uniform(-3e5, 3e5), rng.uniform(0, 5e3)))
            + (p_enum("Species", "EAnimalSpecies", species_enum) if species_enum else b"")
            + none())
    return body


def herd(rng, hid, species, n, kill=0, spawn=0):
    animals = [animal(rng, dead=(i == 0 and hid % 5 == 0)) for i in range(n)]
    if hid == 1:
        extra = random.Random(999)
        animals = animals[kill:] + [animal(extra) for _ in range(spawn)]
    return (p_int("HerdId", hid) + p_enum("Species", "EAnimalSpecies", species)
            + p_struct("CenterLocation", "Vector", vec(rng.uniform(-3e5, 3e5), rng.uniform(-3e5, 3e5), 0))
            + p_array_struct("Animals", "AnimalData", animals) + none())


def build(seed=1, kill=0, spawn=0):
    rng = random.Random(seed)
    herds = []
    hid = 1
    for sp, cnt in [("EAnimalSpecies::RedDeer", 6), ("EAnimalSpecies::WildBoar", 4), ("EAnimalSpecies::RoeDeer", 5), ("EAnimalSpecies::GrayWolf", 2)]:
        for _ in range(cnt):
            herds.append(herd(rng, hid, sp, rng.randint(2, 7), kill, spawn))
            hid += 1
    area = (p_str("AreaName", "Transylvania") + p_array_struct("Herds", "HerdData", herds) + none())
    # embedded UObject blob containing another area (Nez Perce Valley)
    rng2 = random.Random(seed + 100)
    herds2 = [herd(rng2, 100 + i, "EAnimalSpecies::WhitetailDeer", rng2.randint(3, 6)) for i in range(5)]
    blob = p_str("AreaName", "NezPerceValley") + p_array_struct("Herds", "HerdData", herds2) + none()
    props = (p_str("SaveSlotName", "SaveData")
             + p_struct("PlayerLocation", "Vector", vec(1, 2, 3))
             + p_map_str_int("Currency", {"Gold": 12345})
             + prop("Mystery", "WeirdUnknownProperty", b"\x01\x02\x03\x04")
             + p_array_struct("HuntingAreas", "HuntingAreaData", [area])
             + p_array_bytes("SerializedWorld", struct.pack("<i", 7) + blob)
             + none())
    header = (b"GVAS" + struct.pack("<ii", 2, 522) + struct.pack("<HHHI", 4, 27, 2, 18319896)
              + fstr("++UE4+Release-4.27") + struct.pack("<ii", 3, 1) + b"\x11" * 16 + struct.pack("<i", 1)
              + fstr("/Script/WayOfTheHunter.WOTHSaveGame"))
    return header + props + b"\0\0\0\0"


def ue_compress(data, block=131072):
    out = b""
    for i in range(0, len(data), block):
        chunk = data[i:i + block]
        c = zlib.compress(chunk)
        out += struct.pack("<IIq", 0x9E2A83C1, 0, block) + struct.pack("<qq", len(c), len(chunk)) + struct.pack("<qq", len(c), len(chunk)) + c
    return out


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else "samples"
    os.makedirs(d, exist_ok=True)
    raw = build()
    open(os.path.join(d, "SaveData.sav"), "wb").write(raw)
    open(os.path.join(d, "SaveData_compressed.sav"), "wb").write(ue_compress(raw))
    print("written", len(raw))
