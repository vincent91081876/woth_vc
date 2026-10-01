"""Generic, read-only Unreal Engine GVAS (.sav) reader.

Design goals: never crash on unknown data. Every tagged property carries its
byte size, so anything we cannot decode is skipped and kept as a raw marker.
"""
import io
import struct
import zlib
import gzip

PACKAGE_FILE_TAG = 0x9E2A83C1


class GvasError(Exception):
    pass


# ---------------------------------------------------------------- decompress
def decompress(data: bytes):
    """Return (gvas_bytes, method)."""
    if data[:4] == b"GVAS":
        return data, "raw"
    if data[:2] == b"\x1f\x8b":
        return _unwrap(gzip.decompress(data), "gzip")
    if len(data) > 8 and struct.unpack_from("<I", data, 0)[0] == PACKAGE_FILE_TAG:
        out, m = _ue_chunks(data)
        return _unwrap(out, f"ue-chunks({m})")
    # Way of the Hunter wrapper: int64 uncompressed size + int32 + UE compressed chunks
    if len(data) > 16 and struct.unpack_from("<I", data, 12)[0] == PACKAGE_FILE_TAG:
        out, m = _ue_chunks(data[12:])
        return _unwrap(out, f"woth+ue-chunks({m})")
    if data[:1] == b"\x78":
        try:
            return _unwrap(zlib.decompress(data), "zlib")
        except zlib.error:
            pass
    # some games prepend a small header before GVAS / zlib stream
    idx = data.find(b"GVAS", 0, 4096)
    if idx > 0:
        return data[idx:], f"offset-{idx}"
    for off in range(0, min(len(data), 64)):
        if data[off:off + 1] == b"\x78" and data[off + 1:off + 2] in (b"\x01", b"\x5e", b"\x9c", b"\xda"):
            try:
                return _unwrap(zlib.decompress(data[off:]), f"zlib@{off}")
            except zlib.error:
                continue
    raise GvasError("檔案不是可辨識的 GVAS/壓縮格式（可能使用 Oodle 或加密）")


def _unwrap(d, method):
    if d[:4] == b"GVAS":
        return d, method
    inner, m2 = decompress(d)
    return inner, method + "+" + m2


# Real Oodle blocks are 128 KiB. Anything far beyond that in a header means a damaged file, and the
# native decoder must never be asked to allocate a file-controlled (possibly hundreds of GB) buffer.
_MAX_BLOCK_BYTES = 64 * 1024 * 1024


def _ue_chunks(data):
    out = bytearray()
    methods = set()
    f = io.BytesIO(data)
    while True:
        hdr = f.read(8)
        if len(hdr) < 8:
            break
        tag = struct.unpack("<I", hdr[:4])[0]
        if tag != PACKAGE_FILE_TAG:
            break
        # FCompressedChunkInfo: tag(int64) chunkSize(int64) summary(comp,uncomp int64) blocks...
        f.read(8)  # max chunk size
        comp_total, uncomp_total = struct.unpack("<qq", f.read(16))
        blocks = []
        got = 0
        while got < uncomp_total:
            c, u = struct.unpack("<qq", f.read(16))
            blocks.append(c)
            got += u
        sizes = []
        f.seek(f.tell() - 16 * len(blocks))
        for _ in blocks:
            sizes.append(struct.unpack("<qq", f.read(16)))
        for c, u in sizes:
            if not (0 <= c <= len(data) and 0 <= u <= _MAX_BLOCK_BYTES):
                raise GvasError(f"壓縮區塊表頭異常（壓縮 {c} / 解壓 {u} bytes），存檔可能已損毀")
            chunk = f.read(c)
            if chunk[:1] == b"\x78":
                out += zlib.decompress(chunk)
                methods.add("zlib")
            else:
                out += oodle_decompress(chunk, u)
                methods.add("oodle")
    return bytes(out), "+".join(sorted(methods)) or "empty"


_oodle_fn = None


def _find_oodle_dll():
    import glob
    import os
    cands = []
    if os.environ.get("OODLE_DLL"):
        cands.append(os.environ["OODLE_DLL"])
    here = os.path.dirname(os.path.abspath(__file__))
    cands += glob.glob(os.path.join(here, "oo2core*.dll")) + glob.glob(os.path.join(here, "vendor", "oo2core*.dll"))
    for root in ("C:/Program Files (x86)/Steam/steamapps/common", "C:/Program Files/Steam/steamapps/common",
                 "D:/SteamLibrary/steamapps/common", "E:/SteamLibrary/steamapps/common",
                 "C:/Program Files/Epic Games", "D:/Epic Games"):
        cands += glob.glob(os.path.join(root, "Way of the Hunter*", "**", "oo2core*.dll"), recursive=True)
    return next((c for c in cands if os.path.isfile(c)), None)


def oodle_decompress(buf, raw_size):
    """Oodle (Kraken/Mermaid/...) block decompression via pyooz, or oo2core DLL."""
    global _oodle_fn
    if _oodle_fn is None:
        try:
            import ooz  # pip install pyooz
            _oodle_fn = lambda b, n: bytes(ooz.decompress(b, n))
        except ImportError:
            dll = _find_oodle_dll()
            if not dll:
                raise GvasError("存檔使用 Oodle 壓縮：請執行 run_windows.bat（會自動安裝 pyooz），"
                                "或 pip install pyooz，或把 oo2core_*_win64.dll 放到程式資料夾")
            import ctypes
            lib = ctypes.WinDLL(dll) if hasattr(ctypes, "WinDLL") else ctypes.CDLL(dll)
            fn = lib.OodleLZ_Decompress
            fn.restype = ctypes.c_int64
            fn.argtypes = [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_int64] + [ctypes.c_int] * 3 + \
                          [ctypes.c_void_p, ctypes.c_int64, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int64, ctypes.c_int]

            def _f(b, n):
                out = ctypes.create_string_buffer(n)
                r = fn(b, len(b), out, n, 0, 0, 0, None, 0, None, None, None, 0, 3)
                if r != n:
                    raise GvasError("Oodle 解壓縮失敗")
                return out.raw
            _oodle_fn = _f
    out = _oodle_fn(buf, raw_size)
    if len(out) != raw_size:
        raise GvasError("Oodle 解壓縮大小不符")
    return out


# ---------------------------------------------------------------- reader
class Reader:
    def __init__(self, data: bytes, warnings=None):
        self.b = data
        self.p = 0
        self.warnings = warnings if warnings is not None else []

    def left(self):
        return len(self.b) - self.p

    def read(self, n):
        if n < 0 or self.p + n > len(self.b):
            raise GvasError(f"讀取超出範圍 @{self.p} (+{n})")
        v = self.b[self.p:self.p + n]
        self.p += n
        return v

    def u8(self): return self.read(1)[0]
    def i16(self): return struct.unpack("<h", self.read(2))[0]
    def u16(self): return struct.unpack("<H", self.read(2))[0]
    def i32(self): return struct.unpack("<i", self.read(4))[0]
    def u32(self): return struct.unpack("<I", self.read(4))[0]
    def i64(self): return struct.unpack("<q", self.read(8))[0]
    def u64(self): return struct.unpack("<Q", self.read(8))[0]
    def f32(self): return struct.unpack("<f", self.read(4))[0]
    def f64(self): return struct.unpack("<d", self.read(8))[0]

    def guid(self):
        return self.read(16).hex()

    def fstr(self):
        n = self.i32()
        if n == 0:
            return ""
        if n > 0:
            if n > 1 << 24:
                raise GvasError(f"字串長度異常 {n} @{self.p}")
            s = self.read(n)
            return s[:-1].decode("utf-8", "replace") if s.endswith(b"\0") else s.decode("utf-8", "replace")
        n = -n
        if n > 1 << 23:
            raise GvasError(f"字串長度異常 {n} @{self.p}")
        s = self.read(n * 2)
        return s.decode("utf-16-le", "replace").rstrip("\0")

    def peek_fstr(self):
        p = self.p
        try:
            return self.fstr()
        except Exception:
            return None
        finally:
            self.p = p


# Known "native" (binary) structs and their readers
def _vec(r, large):
    f = r.f64 if large else r.f32
    return {"X": f(), "Y": f(), "Z": f()}


NATIVE_STRUCTS = {
    "Vector": lambda r, L: _vec(r, L),
    "Rotator": lambda r, L: dict(zip(("Pitch", "Yaw", "Roll"), _vec(r, L).values())),
    "Quat": lambda r, L: dict(zip("XYZW", [(r.f64 if L else r.f32)() for _ in range(4)])),
    "Vector2D": lambda r, L: dict(zip("XY", [(r.f64 if L else r.f32)() for _ in range(2)])),
    "Vector4": lambda r, L: dict(zip("XYZW", [(r.f64 if L else r.f32)() for _ in range(4)])),
    "LinearColor": lambda r, L: dict(zip("RGBA", [r.f32() for _ in range(4)])),
    "Color": lambda r, L: dict(zip("BGRA", r.read(4))),
    "IntPoint": lambda r, L: {"X": r.i32(), "Y": r.i32()},
    "IntVector": lambda r, L: {"X": r.i32(), "Y": r.i32(), "Z": r.i32()},
    "Guid": lambda r, L: r.guid(),
    "DateTime": lambda r, L: {"_ticks": r.i64()},
    "Timespan": lambda r, L: {"_ticks": r.i64()},
    "Box": lambda r, L: {"Min": _vec(r, L), "Max": _vec(r, L), "IsValid": r.u8()},
    "GameplayTag": lambda r, L: r.fstr(),
}


class Gvas:
    def __init__(self, data: bytes, embedded_scan=True):
        self.warnings = []
        self.raw, self.compression = decompress(data)
        self.embedded_scan = embedded_scan
        r = Reader(self.raw, self.warnings)
        self.header = self._header(r)
        self.large_world = self.header.get("ue5", 0) >= 1004  # LWC doubles
        self.props = self.read_props(r, r.left())
        self.trailing = r.left()

    def _header(self, r):
        if r.read(4) != b"GVAS":
            raise GvasError("缺少 GVAS 標記")
        h = {"save_game_version": r.i32(), "ue4": r.i32()}
        if h["save_game_version"] >= 3:
            h["ue5"] = r.i32()
        h["engine"] = f"{r.u16()}.{r.u16()}.{r.u16()}-{r.u32()}"
        h["branch"] = r.fstr()
        h["custom_format"] = r.i32()
        n = r.i32()
        if not 0 <= n < 10000:
            raise GvasError("CustomVersion 數量異常")
        r.read(n * 20)
        h["custom_versions"] = n
        h["class"] = r.fstr()
        return h

    # --------------------------------------------------------- properties
    def read_props(self, r, limit, depth=0):
        """Read a 'None'-terminated tagged property list."""
        out = {}
        end = r.p + limit
        while r.p < end:
            name = r.fstr()
            if name == "None" or name == "":
                break
            ptype = r.fstr()
            size = r.i64()
            meta = self._prop_header(r, ptype)
            start = r.p
            if size < 0 or start + size > len(r.b):
                raise GvasError(f"{name}<{ptype}> 大小異常 {size}")
            try:
                val = self._prop_body(r, ptype, meta, size, depth)
            except Exception as e:  # skip safely using size
                self.warnings.append(f"{name}<{ptype}> 解析失敗，已跳過: {e}")
                val = {"_raw": ptype, "_size": size}
                r.p = start + size
            if ptype != "BoolProperty" and r.p != start + size:
                self.warnings.append(f"{name}<{ptype}> 大小不符 ({r.p - start}/{size})，已校正")
                r.p = start + size
            key = name
            i = 1
            while key in out:
                i += 1
                key = f"{name}#{i}"
            out[key] = val
        return out

    def _prop_header(self, r, t):
        meta = {}
        if t == "BoolProperty":
            meta["v"] = bool(r.u8())
        elif t == "StructProperty":
            meta["st"] = r.fstr(); r.read(16)
        elif t in ("ArrayProperty", "SetProperty"):
            meta["inner"] = r.fstr()
        elif t == "MapProperty":
            meta["kt"] = r.fstr(); meta["vt"] = r.fstr()
        elif t in ("ByteProperty", "EnumProperty"):
            meta["en"] = r.fstr()
        self._opt_guid(r)
        return meta

    def _prop_body(self, r, t, meta, size, depth):
        if t == "BoolProperty":
            return meta["v"]
        if t == "StructProperty":
            return self._struct_body(r, meta["st"], size, depth)
        if t == "ArrayProperty":
            return self._array(r, meta["inner"], size, depth)
        if t == "MapProperty":
            return self._map(r, meta["kt"], meta["vt"], size, depth)
        if t == "SetProperty":
            r.i32(); n = r.i32()
            return [self._value(r, meta["inner"], depth) for _ in range(n)]
        if t == "ByteProperty":
            return r.u8() if meta["en"] == "None" or size == 1 else r.fstr()
        if t == "EnumProperty":
            return r.fstr()
        if t == "TextProperty":
            return self._text(r, size)
        return self._value(r, t, depth, size)

    def _opt_guid(self, r):
        if r.u8():
            r.read(16)

    def _text(self, r, size):
        start = r.p
        try:
            r.u32()  # flags
            ht = r.u8()
            if ht == 0:  # base
                r.fstr(); r.fstr()
                return r.fstr()
            if ht == 255:
                if r.u32():
                    return r.fstr()
                return ""
        except Exception:
            pass
        r.p = start
        blob = r.read(size)
        return {"_text_raw": blob.hex()[:200]}

    def _value(self, r, t, depth, size=None):
        if t == "IntProperty": return r.i32()
        if t == "Int64Property": return r.i64()
        if t == "UInt32Property": return r.u32()
        if t == "UInt64Property": return r.u64()
        if t == "Int16Property": return r.i16()
        if t == "UInt16Property": return r.u16()
        if t == "Int8Property": return struct.unpack("<b", r.read(1))[0]
        if t == "FloatProperty": return r.f32()
        if t == "DoubleProperty": return r.f64()
        if t == "BoolProperty": return bool(r.u8())
        if t == "ByteProperty": return r.u8()
        if t in ("StrProperty", "NameProperty", "ObjectProperty", "EnumProperty",
                 "ClassProperty", "InterfaceProperty"):
            return r.fstr()
        if t == "SoftObjectProperty" or t == "SoftClassProperty":
            a = r.fstr(); b = r.fstr()
            return a + ("::" + b if b else "")
        if t == "StructProperty":  # inside map/set without type info
            return self._untyped_struct(r, depth)
        if size is not None:
            r.read(size)
            return {"_raw": t, "_size": size}
        raise GvasError(f"未知型別 {t}")

    def _struct_body(self, r, st, size, depth):
        if st in NATIVE_STRUCTS:
            return NATIVE_STRUCTS[st](r, self.large_world)
        v = self.read_props(r, size, depth + 1)
        if st not in ("", "None"):
            v["_struct"] = st
        return v

    def _untyped_struct(self, r, depth):
        p = r.p
        nm = r.peek_fstr()
        if nm is not None and (nm == "None" or self._looks_prop(r)):
            return self.read_props(r, r.left(), depth + 1)
        r.p = p
        return r.guid()  # most common key struct is FGuid

    def _looks_prop(self, r):
        p = r.p
        try:
            r.fstr()
            t = r.fstr()
            return t.endswith("Property")
        except Exception:
            return False
        finally:
            r.p = p

    def _array(self, r, inner, size, depth):
        n = r.i32()
        if inner == "StructProperty":
            r.fstr(); r.fstr(); r.i64()
            st = r.fstr(); r.read(16); self._opt_guid(r)
            items = []
            for _ in range(n):
                items.append(self._struct_body(r, st, r.left(), depth))
            return items
        if inner == "ByteProperty" and n == size - 4:
            blob = r.read(n)
            return self._maybe_embedded(blob, depth)
        return [self._value(r, inner, depth) for _ in range(n)]

    def _map(self, r, kt, vt, size, depth):
        r.i32()
        n = r.i32()
        out = []
        for _ in range(n):
            k = self._value(r, kt, depth)
            v = self._value(r, vt, depth)
            out.append({"key": k, "value": v})
        return {"_map": out}

    def _maybe_embedded(self, blob, depth):
        """Byte arrays often hold serialized UObjects (tagged property streams)."""
        if not self.embedded_scan or depth > 6 or len(blob) < 16:
            return {"_bytes": len(blob)}
        for off in (0, 4, 8, 12, 16):
            sub = Reader(blob[off:], self.warnings)
            if not self._looks_prop(sub):
                continue
            saved = len(self.warnings)
            try:
                props = self.read_props(sub, sub.left(), depth + 1)
                if props:
                    props["_embedded"] = True
                    return props
            except Exception:
                del self.warnings[saved:]
        if blob[:4] == b"GVAS":
            try:
                g = Gvas(blob)
                return {"_embedded_gvas": True, **g.props}
            except Exception:
                pass
        return {"_bytes": len(blob)}


def load(path, embedded_scan=True):
    with open(path, "rb") as f:  # read-only
        data = f.read()
    return Gvas(data, embedded_scan)
