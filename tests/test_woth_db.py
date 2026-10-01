"""Synthetic test for the WOTH Database layout (real saves are not bundled)."""
import os, struct, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import woth_db

H_M = b"\x11" * 8; H_F = b"\x22" * 8; H_G = b"\x33" * 8; COMMON = b"\x4f\x40\x90\x2f\x3b\x6a\xe1\x9a"

def animal(h, age, fit, sex, aid, x, y):
    return h + b"\0" * 4 + COMMON + struct.pack("<IfBI", age, fit, sex, aid) + struct.pack("<6f", x, y, -8e4, 0, 90, 0) + b"\0" * 200

def herd(x, y):
    return H_G + b"\0" * 4 + COMMON + bytes(range(16)) + struct.pack("<3f", x, y, -8e4) + b"\0" * 100

def names(d):
    out = struct.pack("<I", len(d))
    for h, s in d.items():
        out += h + struct.pack("<I", len(s)) + s.encode("utf-16-le")
    return out

class T(unittest.TestCase):
    def test_parse(self):
        body = herd(1000, 2000) + animal(H_M, 7, 0.9, 1, 101, 1000, 2000) + animal(H_F, 5, 0.0, 2, 102, 1010, 2010) + animal(H_F, 6, 0.0, 2, 103, 990, 1990)
        head = b"HEADER" + b"\0" * 10
        props_end = len(head)
        raw = head + struct.pack("<II", 0, len(body)) + body + b"\0" + names({
            H_M: "/Game/TEH/Animals/Big/CervusCanadensis/BP_CervusCanadensis_M.BP_CervusCanadensis_M_C",
            H_F: "/Game/TEH/Animals/Big/CervusCanadensis/BP_CervusCanadensis_F_Albino.BP_CervusCanadensis_F_Albino_C",
            H_G: "/Game/TEH/Animals/Big/CervusCanadensis/AIC_GroundAnimalGroup_CervusCanadensis.AIC_GroundAnimalGroup_CervusCanadensis_C"})
        a, h, info = woth_db.parse(raw, props_end)
        self.assertEqual(len(a), 3); self.assertEqual(len(h), 1)
        self.assertEqual(h[0]["size"], 3); self.assertEqual(h[0]["males"], 1)
        m = [x for x in a if x["gender"] == "M"][0]
        self.assertEqual((m["species"], m["age"], m["id"]), ("Rocky Mountain Elk", 7, "101"))
        self.assertAlmostEqual(m["fitness"], 0.9, 5)
        self.assertEqual([x["variant_zh"] for x in a if x["gender"] == "F"], ["白化", "白化"])
        self.assertEqual(info["reserve"], "Nez Perce Valley")

if __name__ == "__main__":
    unittest.main(verbosity=2)
