"""v3.0 Way of the Hunter 2 (Early Access) save detection and safe format probe.

WOTH2 saves (*.nrgs, per SteamDB cloud config) are NOT parsed: their format is
unpublished. This module only lists files and reports non-sensitive facts
(size, time, first-bytes signature, entropy) read in 'rb' mode.
"""
import glob
import math
import os

PATTERNS = ("*.nrgs", "*.sav")


def dirs():
    out = []
    la = os.environ.get("LOCALAPPDATA")
    if os.environ.get("WOTH2_SAVE_DIR"):
        out.append(os.environ["WOTH2_SAVE_DIR"])
    if la:
        out.append(os.path.join(la, "WOTH2", "Saved", "SaveGames"))
    home = os.path.expanduser("~")
    for steam in (".steam/steam", ".local/share/Steam", ".var/app/com.valvesoftware.Steam/.local/share/Steam"):
        out.append(os.path.join(home, steam, "steamapps/compatdata/2543830/pfx/drive_c/users/steamuser/AppData/Local/WOTH2/Saved/SaveGames"))
    return [d for i, d in enumerate(out) if d and os.path.isdir(d) and d not in out[:i]]


def entropy(b):
    if not b:
        return 0.0
    counts = [0] * 256
    for x in b:
        counts[x] += 1
    n = len(b)
    return round(-sum(c / n * math.log2(c / n) for c in counts if c), 3)


def probe(path):
    st = os.stat(path)
    with open(path, "rb") as f:  # READ ONLY
        head = f.read(65536)
    magic = head[:4]
    kind = ("GVAS (Unreal SaveGame)" if magic == b"GVAS" else
            "UE compressed chunks" if head[:4] == b"\xc1\x83\x2a\x9e" else
            "zlib" if head[:1] == b"\x78" else "unknown")
    return {"path": path, "name": os.path.basename(path), "size": st.st_size, "mtime": st.st_mtime,
            "magic_hex": head[:16].hex(" "), "kind": kind, "entropy_64k": entropy(head),
            "likely_compressed_or_encrypted": entropy(head) > 7.5, "parsed": False}


def scan():
    files = []
    for d in dirs():
        for pat in PATTERNS:
            for p in glob.glob(os.path.join(d, "**", pat), recursive=True):
                try:
                    files.append(probe(p))
                except OSError as e:
                    files.append({"path": p, "error": str(e), "parsed": False})
    files.sort(key=lambda x: -(x.get("mtime") or 0))
    return {"dirs": dirs(), "files": files[:50], "count": len(files), "supported": False,
            "note": "WOTH2 存檔格式尚未公開，本版只偵測與顯示檔案特徵，不解析、不修改。"}
