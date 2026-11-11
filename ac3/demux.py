"""Extraction des trames AC-3 depuis un fichier .ac3, MP4/M4V/MOV ou MKV/WebM (sans FFmpeg)."""
import os, struct
from .decoder import frame_size

def _raw(f):
    data = f.read(); pos = 0
    while pos < len(data) - 5:
        n = frame_size(data, pos)
        if n is None: pos += 1; continue
        yield data[pos:pos + n], pos; pos += n

def _mp4(f, track):
    size = os.fstat(f.fileno()).st_size
    def boxes(a, b):
        while a + 8 <= b:
            f.seek(a); sz, t = struct.unpack(">I4s", f.read(8)); hdr = 8
            if sz == 1: sz = struct.unpack(">Q", f.read(8))[0]; hdr = 16
            elif sz == 0: sz = b - a
            yield t.decode("latin1"), a + hdr, a + sz; a += sz
    def find(a, b, name): return next(((x, y) for t, x, y in boxes(a, b) if t == name), None)
    found = []
    moov = find(0, size, "moov")
    for t, a, b in boxes(*moov):
        if t != "trak": continue
        stbl = find(*find(*find(a, b, "mdia"), "minf"), "stbl")
        stsd = find(*stbl, "stsd")
        f.seek(stsd[0] + 12); entry = f.read(4)
        if entry != b"ac-3": continue
        def tab(name, fmt, hdr):
            x, y = find(*stbl, name); f.seek(x + 4); n = struct.unpack(">I", f.read(4))[0]
            return struct.unpack(">" + fmt * n, f.read(n * struct.calcsize(fmt))) if hdr == 0 else n
        f.seek(find(*stbl, "stsz")[0] + 4); fixed, n = struct.unpack(">II", f.read(8))
        sizes = [fixed] * n if fixed else list(struct.unpack(f">{n}I", f.read(4 * n)))
        x, _ = find(*stbl, "stsc"); f.seek(x + 4); n = struct.unpack(">I", f.read(4))[0]
        stsc = [struct.unpack(">III", f.read(12)) for _ in range(n)]
        c = find(*stbl, "stco"); wide = False
        if c is None: c = find(*stbl, "co64"); wide = True
        f.seek(c[0] + 4); n = struct.unpack(">I", f.read(4))[0]
        offs = struct.unpack(">" + ("Q" if wide else "I") * n, f.read(n * (8 if wide else 4)))
        found.append((sizes, stsc, offs))
    if track >= len(found): return
    sizes, stsc, offs = found[track]; si = 0
    for ci, off in enumerate(offs):
        per = [s for s in stsc if s[0] <= ci + 1][-1][1]
        for _ in range(per):
            if si >= len(sizes): return
            f.seek(off); yield f.read(sizes[si]), off; off += sizes[si]; si += 1

MASTER = {0x18538067, 0x1F43B675, 0xA0, 0x1654AE6B, 0xAE}

def _mkv(f, track):
    size = os.fstat(f.fileno()).st_size; tracks = []; cur = {}
    def vint(keep):
        b = f.read(1)
        if not b: return None, 0
        n = 1; m = 0x80
        while n <= 8 and not (b[0] & m): n += 1; m >>= 1
        v = b[0] if keep else b[0] & (m - 1)
        for x in f.read(n - 1): v = (v << 8) | x
        return v, n
    def walk(end):
        while f.tell() < end:
            eid, _ = vint(True)
            if eid is None: return
            sz, n = vint(False); unk = sz == (1 << (7 * n)) - 1
            start = f.tell(); stop = end if unk else start + sz
            if eid in MASTER:
                if eid == 0xAE: cur.clear()
                yield from walk(stop)
                if eid == 0xAE and cur.get("codec") == "A_AC3": tracks.append(cur.get("num"))
            elif eid == 0xD7: cur["num"] = int.from_bytes(f.read(sz), "big")
            elif eid == 0x86: cur["codec"] = f.read(sz).decode("latin1").strip("\0")
            elif eid in (0xA3, 0xA1):
                tn, k = vint(False)
                if track < len(tracks) and tn == tracks[track]:
                    f.read(3); yield f.read(sz - k - 3), start
            if not unk: f.seek(stop)
    yield from walk(size)

def frames(path, track=0):
    """Génère (trame_ac3, position_dans_le_fichier)."""
    with open(path, "rb") as f:
        head = f.read(12); f.seek(0)
        if head[:2] == b"\x0b\x77": yield from _raw(f)
        elif head[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"wide"): yield from _mp4(f, track)
        elif head[:4] == b"\x1a\x45\xdf\xa3": yield from _mkv(f, track)
        else: raise ValueError("format non pris en charge (utiliser .ac3, MP4/MOV ou MKV)")
