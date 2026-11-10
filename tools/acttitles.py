"""Act titles (ACT 1 / SNATCH ...) in Russian.

Each title is a screen of its own: one tile block at VRAM 0x2000 (tile 0x100
blank) and a sprite table whose frames place 4x3-tile sprites: line 1 at
y 0, line 2 at y 48. The words are redrawn with tools/actfont.py in the
game's vertical gradient, cut into new sprites, and both the block and the
table are rewritten (the planes are empty then, so the block may grow).
"""
import os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import actfont, screens, sprites

GRAD = [0, 11, 10, 10, 10, 10, 10, 9, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7, 8, 8, 8, 9, 10, 0]
EDGE = 4
GAP, SPACE = 1, 7
MAXTILES = 160                      # VRAM 0x2000-0x3400

# file: [(tiles pointer long, table pointer longs, [(line 1, line 2) per frame])]
TITLES = {
    "DATA_H01.BIN": [(0x3d0, (0x3e2, 0x3ee), [("АКТ 1", "ЗАХВАТ")])],
    "DATA_H15.BIN": [(0x630, (0x642, 0x64e), [("АКТ 2", "ЛЕЧЕНИЕ")]),
                     (0x660, (0x672,), [("АКТ 3", "ХЛАМ")])],
    "DATA_F4.BIN": [(0x1b06, (0x1b1e, 0x1b2a), [("КОНЕЦ", "АКТА 1"), ("КОНЕЦ", "АКТА 2")])],
    "DATA_H14.BIN": [(0x17dc, (0x17ee, 0x17fa), [("КОНЕЦ", "АКТА 1"), ("КОНЕЦ", "АКТА 2")])],
}


def line(text):
    parts = []
    for ch in text:
        if ch == " ":
            parts.append(np.zeros((23, SPACE), bool))
            continue
        g = np.array([[c == "#" for c in r] for r in actfont.G[ch]])
        g = np.hstack([g, np.zeros((23, 1), bool)])
        g[:, 1:] |= g[:, :-1].copy()                     # heavier, like the English
        parts += [g, np.zeros((23, GAP), bool)]
    m = np.hstack(parts[:-1] if parts else [np.zeros((23, 1), bool)])
    m = np.vstack([m, np.zeros((1, m.shape[1]), bool)])            # 24 rows = 3 tiles
    img = np.zeros(m.shape, np.uint8)
    for r in range(24):
        img[r][m[r]] = GRAD[r] or 10
    edge = m.copy()
    edge[:, 1:] &= ~m[:, :-1]
    img[edge] = EDGE
    return img


def sprites_for(img, y, cx, tiles, base):
    """4x3 sprites covering a line image centred on cx; tiles appended."""
    h, w = img.shape
    cols = (w + 7) // 8
    pad = np.zeros((24, cols * 8), np.uint8)
    pad[:, :w] = img
    x0 = cx - (cols * 8) // 2
    out = []
    for s in range(0, cols, 4):
        n = min(4, cols - s)
        t = base + len(tiles)
        for c in range(s, s + n):
            for r in range(3):
                tiles.append(pad[r * 8:r * 8 + 8, c * 8:c * 8 + 8])
        out.append((y, ((n - 1) << 10) | (2 << 8), t, x0 + s * 8))
    return out


def patch(name, d):
    for tile_ptr, tab_ptrs, frames_text in TITLES.get(name, []):
        old_tab = screens.ptr(d, tab_ptrs[0])
        cx = 48
        tiles = [np.zeros((8, 8), np.uint8)]             # tile 0x100 stays blank
        cache, frs = {}, []
        for l1, l2 in frames_text:
            f = []
            for y, text in ((0, l1), (48, l2)):
                if text not in cache:
                    cache[text] = sprites_for(line(text), y, cx, tiles, 0x100)
                f += cache[text]
            frs.append([(y, size, attr, x) for y, size, attr, x in f])
        assert len(tiles) <= MAXTILES, (name, len(tiles))
        d = screens.put_blocks(d, [tile_ptr], [screens.array_to_tiles(np.array(tiles))])
        d = screens.put_blocks(d, [tab_ptrs[0]], [b""], also=tab_ptrs[1:], raw=sprites.pack(frs))
    return d
