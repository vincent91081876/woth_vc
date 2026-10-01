"""Rebuild data/need_zones.json from a local clone of codeaid/woth-toolbox (GPL-3.0).

Usage: python tools/build_need_zones.py <path-to-woth-toolbox>
Toolbox coordinates are normalised 0..1 image coordinates (x right, y down).
Image registration (SIFT + RANSAC, 6 maps) against the bundled Toolbox map
images gave an identity transform (mean residual ~0.0001 = ~1 m), so world
coordinates are x_min + u*(x_max-x_min), y_min + v*(y_max-y_min).
"""
import json, os, re, sys, subprocess
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1]
MAPS = {"idaho": "Nez Perce Valley", "transylvania": "Transylvania", "alaska": "Aurora Shores",
        "africa": "Tikamoon Plains", "new-zealand": "Matariki Park", "lintukoto": "Lintukoto Reserve"}
KEY_SLUG = {"red stag": "red-deer-new-zealand", "ross goose": "rosss-goose",
            "eastern wild turkey": "merriams-wild-turkey"}
cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))["maps"]
species = json.load(open(os.path.join(HERE, "species_data.json"), encoding="utf-8"))["animals"]
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
by_name = {norm(a["name"]): a["slug"] for a in species}
en = json.load(open(os.path.join(SRC, "src/locales/en/woth.json"), encoding="utf-8"))
zh = json.load(open(os.path.join(SRC, "src/locales/zh-Hant/woth.json"), encoding="utf-8"))
commit = subprocess.run(["git", "-C", SRC, "log", "-1", "--format=%H %cI"], capture_output=True, text=True).stdout.strip()
out = {"source": "https://github.com/codeaid/woth-toolbox", "license": "GPL-3.0 (data derived from codeaid/woth-toolbox)",
       "source_commit": commit, "calibration": "SIFT/RANSAC registration vs bundled maps: identity, mean residual ~1e-4",
       "activity_of_zone": {"drink": "Drink", "eat": "Feed", "sleep": "Sleep"}, "reserves": {}}
for folder, reserve in MAPS.items():
    c = cfg[reserve]
    wx = lambda u: round(c["x_min"] + u * (c["x_max"] - c["x_min"]))
    wy = lambda v: round(c["y_min"] + v * (c["y_max"] - c["y_min"]))
    pts = lambda flat: [[wx(flat[i]), wy(flat[i + 1])] for i in range(0, len(flat) - 1, 2)]
    doc = json.load(open(os.path.join(SRC, f"src/config/{folder}/animals.json"), encoding="utf-8"))
    terr = []
    for key, rows in doc.items():
        name = key.split(":", 1)[1]
        slug = KEY_SLUG.get(name) or by_name.get(norm(name))
        if not slug:
            raise SystemExit(f"unmapped {key}")
        for tid, x, y, drink, eat, sleep in rows:
            terr.append({"id": tid, "slug": slug, "x": wx(x), "y": wy(y),
                         "Drink": pts(drink), "Feed": pts(eat), "Sleep": pts(sleep)})
    labels = json.load(open(os.path.join(SRC, f"src/config/{folder}/labels.json"), encoding="utf-8"))
    areas = [{"area": en.get(a, a), "area_zh": zh.get(a, en.get(a, a)), "habitat": en.get(h, h),
              "habitat_zh": zh.get(h, en.get(h, h)), "x": wx(x), "y": wy(y)} for a, h, x, y in labels]
    out["reserves"][reserve] = {"territories": terr, "areas": areas}
    print(reserve, len(terr), "territories", sum(len(t[k]) for t in terr for k in ("Drink", "Feed", "Sleep")), "zones", len(areas), "areas")
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
with open(os.path.join(HERE, "data", "need_zones.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
