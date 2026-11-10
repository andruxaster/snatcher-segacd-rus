"""The typed location caption over the city (Konami Omni Building / Junker
Headquarters) in Russian.

The caption is a run of frames in a sprite table of DATA_H08 and DATA_H15:
each frame shows the text typed so far with palette-3 sprites whose tiles
(0x57E-0x5DD) are in the block loaded at VRAM 0xA000. The Russian lines are
drawn into those tiles as 32x16 blocks, and the typing frames rebuilt: every
frame shows a few more 8-px columns, line 1 first.
"""
import os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pixfont, screens, sprites

LINES = ("Здание Konami Omni", "Штаб ДЖАНКЕРа")
FIRST, LAST = 8, 43                 # caption frames of the table
TILE0, TILES = 0x57E, 96            # tiles the caption may use
VRAM_BASE = 0x500                   # the block sits at VRAM 0xA000
CORE = 7
# file: (tile block pointer long, sprite table offset)
FILES = {"DATA_H08.BIN": (0xb1c, 0x10f3a), "DATA_H15.BIN": (0x510, 0x5eac)}


def render(text):
    f = pixfont.font("9x15")
    img = np.zeros((16, f.width(text) + 2), np.uint8)
    m = f.mask(text, f.ascent + 4)[1:17]           # capitals on rows 1-10
    img[:m.shape[0], :m.shape[1]][m] = CORE
    return img


def patch(name, d):
    tile_ptr, tab = FILES[name]
    tab_ptrs = [i for i in range(0, 0x4000, 2)          # every object using the table
                if struct.unpack(">I", d[i:i + 4])[0] == screens.LOAD + tab]
    frs = sprites.frames(d, tab)
    raw = screens.block(d, screens.ptr(d, tile_ptr))
    T = screens.tiles_to_array(raw).copy()
    b0 = TILE0 - VRAM_BASE
    T[b0:b0 + TILES] = 0
    # blocks: (line y, x, tile, columns)
    blocks, used = [], 0
    for ly, text in ((0, LINES[0]), (16, LINES[1])):
        img = render(text)
        cols = (img.shape[1] + 7) // 8
        pad = np.zeros((16, cols * 8), np.uint8)
        pad[:, :img.shape[1]] = img
        for s in range(0, cols, 4):
            n = min(4, cols - s)
            t = TILE0 + used
            for c in range(s, s + n):
                T[t - VRAM_BASE + 2 * (c - s)] = pad[0:8, c * 8:c * 8 + 8]
                T[t - VRAM_BASE + 2 * (c - s) + 1] = pad[8:16, c * 8:c * 8 + 8]
            used += 2 * n
            blocks.append((ly, s * 8, t, n))
    assert used <= TILES, used
    total = sum(n for *_, n in blocks)
    count = LAST - FIRST + 1
    for k in range(count):
        show = round(total * (k + 1) / count)
        f = []
        for y, x, t, n in blocks:
            if show <= 0:
                break
            m = min(n, show)
            f.append((y, ((m - 1) << 10) | (1 << 8), 0x6000 | t, x))
            show -= m
        frs[FIRST + k] = f or [(0, 0, 0x6000 | TILE0, -64)]
    d = screens.put_blocks(d, [tile_ptr], [screens.array_to_tiles(T)])
    return screens.put_blocks(d, [tab_ptrs[0]], [b""], also=tab_ptrs[1:], raw=sprites.pack(frs))
