"""Sprite animation tables of the DATA files.

A table is a list of word offsets (from the table start) to frames; a frame
is `count - 1` followed by `count` sprites of 8 bytes: y (signed), size
(bits 11-10 width - 1, 9-8 height - 1, in tiles), attribute (priority,
palette, flips, tile number as on the VDP), x (signed). Objects point at a
table with an absolute long ($28000 + offset).
"""
import struct

LOAD = 0x28000


def W(d, i):
    return struct.unpack(">H", d[i:i + 2])[0]


def tables(d, scan=0x8000):
    """Offsets of plausible frame tables pointed at from the file head."""
    out = {}
    for i in range(0, min(len(d) - 4, scan), 2):
        p = struct.unpack(">I", d[i:i + 4])[0] - LOAD
        if not (0 <= p < len(d) - 4):
            continue
        n0 = W(d, p)
        if n0 < 2 or n0 > 600 or n0 % 2 or p + n0 >= len(d):
            continue
        offs = [W(d, p + 2 * k) for k in range(n0 // 2)]
        if offs != sorted(offs) or p + offs[-1] + 2 >= len(d):
            continue
        try:
            frames(d, p)
        except ValueError:
            continue
        out.setdefault(p, []).append(i)
    return out


def frames(d, t):
    n0 = W(d, t)
    res = []
    for k in range(n0 // 2):
        p = t + W(d, t + 2 * k)
        n = W(d, p) + 1
        if n > 80 or p + 2 + 8 * n > len(d):
            raise ValueError
        res.append([struct.unpack(">hHHh", d[p + 2 + 8 * j:p + 10 + 8 * j]) for j in range(n)])
    return res


def pack(frs):
    """Table bytes for a list of frames (lists of (y, size, attr, x))."""
    head = 2 * len(frs)
    body = b""
    offs = []
    for f in frs:
        offs.append(head + len(body))
        body += struct.pack(">H", len(f) - 1) + b"".join(struct.pack(">hHHh", *e) for e in f)
    return b"".join(struct.pack(">H", o) for o in offs) + body
