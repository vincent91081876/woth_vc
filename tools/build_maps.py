"""Rebuild web/maps/*.webp in the Toolbox (toolbox.byteset.io) look.

Usage: python3 tools/build_maps.py [work_dir]      (needs numpy + Pillow with WebP)

Downloads base.webp / mask.webp / normal.webp for each reserve from
https://toolbox.byteset.io/maps/<slug>/ and composites them into one flat
top-down image: base texture x relief shading (normal map), water (mask G),
roads (mask R) and a darkened outside-of-map fringe (mask B).
The images cover exactly the x/y bounds in config.json (they match the
Toolbox mesh.gltf POSITION min/max), so no re-calibration is needed.
"""
import os, sys, urllib.request
import numpy as np
from PIL import Image

MAPS = {"nez_perce": "idaho", "transylvania": "transylvania", "aurora_shores": "alaska",
        "tikamoon_plains": "africa", "matariki_park": "new-zealand",
        "lintukoto_reserve": "finland", "elkcrest_island": "elkcrest"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch(slug, kind, work):
    path = os.path.join(work, f"{slug}-{kind}.webp")
    if not os.path.exists(path):
        req = urllib.request.Request(f"https://toolbox.byteset.io/maps/{slug}/{kind}.webp",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32) / 255


def render(slug, out, work, quality=82):
    base, mask, nrm = (fetch(slug, k, work) for k in ("base", "mask", "normal"))
    nx, ny = (nrm[..., 0] - .5) * 2, (nrm[..., 1] - .5) * 2      # R,G = -dH/dx, -dH/dy (image axes)
    nz = np.sqrt(np.clip(1 - nx * nx - ny * ny, 0, 1))
    light = np.array([-0.55, -0.55, 0.63], dtype=np.float32)
    light /= np.linalg.norm(light)
    shade = nx * light[0] + ny * light[1] + nz * light[2]
    f = np.clip(1 + 1.6 * (shade - light[2]), 0.55, 1.45)
    img = base * f[..., None]
    w = np.clip(mask[..., 1] * 1.4, 0, 1)[..., None]              # water
    img = img * (1 - w) + np.array([0.04, 0.24, 0.46], np.float32) * (0.75 + 0.5 * f[..., None]) * w
    r = np.clip((np.clip(mask[..., 0] * 2.2, 0, 1) - 0.22) / 0.4, 0, 1)[..., None]   # roads
    img = img * (1 - 0.85 * r) + np.array([0.90, 0.74, 0.30], np.float32) * 0.85 * r
    img = img * (1 - 0.65 * np.clip(mask[..., 2], 0, 1)[..., None])   # outside fringe
    Image.fromarray((np.clip(img, 0, 1) * 255 + .5).astype(np.uint8)).save(out, "WEBP", quality=quality, method=4)


if __name__ == "__main__":
    work = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "tools", "_maps_cache")
    os.makedirs(work, exist_ok=True)
    for name, slug in MAPS.items():
        render(slug, os.path.join(ROOT, "web", "maps", f"{name}.webp"), work)
        print("built", name)
