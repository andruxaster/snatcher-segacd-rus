"""Text pictures of the Sega CD Snatcher: decode a screen (tiles + tilemap,
both Konami-LZ blocks of a DATA_* file), redraw it, encode it back.

A block in a DATA file is `length.w` + LZ stream; code tables point at the
length word with an absolute address (file loaded at LOAD = $28000).
Tilemap words: priority 15, palette 14-13, vflip 12, hflip 11, tile 10-0.
"""
import os, struct, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import konamilz

LOAD = 0x28000


def block(data, ptr):
    """Decompressed block whose length word is at file offset `ptr`."""
    n = struct.unpack(">H", data[ptr:ptr + 2])[0]
    out, _ = konamilz.decompress(data, ptr + 2)
    assert len(out) == n, (hex(ptr), len(out), n)
    return out


def pack(raw):
    return struct.pack(">H", len(raw)) + konamilz.compress(raw)


def tiles_to_array(t):
    n = len(t) // 32
    a = np.frombuffer(t[:n * 32], dtype=np.uint8).reshape(n, 8, 4)
    hi, lo = a >> 4, a & 15
    return np.stack([hi, lo], axis=3).reshape(n, 8, 8)


def array_to_tiles(arr):
    a = arr.reshape(-1, 8, 4, 2)
    return ((a[..., 0] << 4) | a[..., 1]).astype(np.uint8).tobytes()


def decode(tiles, tmap, width):
    """(pixels HxW of colour indices, attr array of map words) of a screen."""
    t = tiles_to_array(tiles)
    words = np.array(struct.unpack(">%dH" % (len(tmap) // 2), tmap), dtype=np.uint16)
    h = len(words) // width
    words = words[:h * width].reshape(h, width)
    img = np.zeros((h * 8, width * 8), dtype=np.uint8)
    for y in range(h):
        for x in range(width):
            v = int(words[y, x])
            i = v & 0x7FF
            if i >= len(t):
                continue
            g = t[i]
            if v & 0x800:
                g = g[:, ::-1]
            if v & 0x1000:
                g = g[::-1, :]
            img[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = g
    return img, words


def encode(img, words):
    """Tiles (deduplicated, flips not used) + tilemap for `img`, keeping each
    cell's priority/palette bits from `words`."""
    h, w = words.shape
    seen, tiles, out = {}, [], np.zeros_like(words)
    for y in range(h):
        for x in range(w):
            g = img[y * 8:y * 8 + 8, x * 8:x * 8 + 8]
            key = g.tobytes()
            if key not in seen:
                seen[key] = len(tiles)
                tiles.append(g.copy())
            out[y, x] = (int(words[y, x]) & 0xE000) | seen[key]
    t = array_to_tiles(np.array(tiles)) if tiles else b""
    return t, struct.pack(">%dH" % out.size, *[int(v) for v in out.flatten()])


def put_blocks(data, ptrs, raws):
    """Append each raw block (packed) to the file and point the code-table
    longs at file offsets `ptrs` to it. Returns the new file."""
    out = bytearray(data)
    for p, raw in zip(ptrs, raws):
        if len(out) & 1:
            out.append(0)
        off = len(out)
        out += pack(raw)
        out[p:p + 4] = struct.pack(">I", LOAD + off)
    return bytes(out)


def ptr(data, at):
    """File offset of the block a code-table long at `at` points to."""
    return struct.unpack(">I", data[at:at + 4])[0] - LOAD


def descriptor(data, at):
    """(ptr_offset, vram) pairs of a screen descriptor starting at the first
    pointer long `at`: pointer, vram, pointer, vram... until 0xffff."""
    out = []
    while True:
        p, v = struct.unpack(">IH", data[at:at + 6])[0], struct.unpack(">I", data[at + 4:at + 8])[0]
        if p >> 24 or not (LOAD <= p < LOAD + len(data)):
            break
        out.append((at, v))
        at += 8
        if v in (0xC000, 0xE000):
            break
    return out


class Vram:
    """Tiles of the blocks of one screen, by VRAM tile number."""

    def __init__(self):
        self.tiles = {}

    def load(self, raw, vram):
        t = tiles_to_array(raw)
        base = vram // 32
        for i in range(len(t)):
            self.tiles[base + i] = t[i]

    def draw(self, tmap, width):
        words = np.array(struct.unpack(">%dH" % (len(tmap) // 2), tmap), dtype=np.uint16)
        h = len(words) // width
        words = words[:h * width].reshape(h, width)
        img = np.zeros((h * 8, width * 8), dtype=np.uint8)
        pal = np.zeros((h * 8, width * 8), dtype=np.uint8)
        for y in range(h):
            for x in range(width):
                v = int(words[y, x])
                g = self.tiles.get(v & 0x7FF)
                if g is None:
                    continue
                if v & 0x800:
                    g = g[:, ::-1]
                if v & 0x1000:
                    g = g[::-1, :]
                img[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = g
                pal[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = (v >> 13) & 3
        return img, pal, words
