"""Russian text screens outside the script (DATA_D1: disclaimer, ...).

Each screen: the file offsets of the code-table longs that point at its
tiles and tilemap block, the area to clear and the Russian text to draw.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boldfont, screens, seriffont

DISCLAIMER = ("Эта история вымышлена. Все организации, компании и лица в ней "
              "вымышлены, а любое сходство с реальными - чистая случайность.")


def disclaimer(d1):
    tp, mp = 0xcb4, 0xcbc
    tiles = screens.block(d1, screens.ptr(d1, tp))
    tmap = screens.block(d1, screens.ptr(d1, mp))
    img, words = screens.decode(tiles, tmap, 32)  # H32 screen, 32x32 cells
    img[56:168, 24:240] = 5                       # the English text: 7 lines, 16 px apart
    lines = boldfont.wrap(DISCLAIMER, 196)
    x = (256 - max(boldfont.width(l) for l in lines)) // 2
    y = 56 + (7 - len(lines)) * 8
    for i, l in enumerate(lines):
        boldfont.render(img, x, y + 16 * i, l, ink=1, shadow=7)
    t, m = screens.encode(img, words)
    return screens.put_blocks(d1, [tp, mp], [t, m])


DEDICATION = ["ЭТА ИСТОРИЯ ПОСВЯЩАЕТСЯ", "ВСЕМ КИБЕРПАНКАМ,", "КОТОРЫЕ КАЖДЫЙ ДЕНЬ",
              "СВОЕЙ ЖИЗНИ БОРЮТСЯ", "С НЕСПРАВЕДЛИВОСТЬЮ", "И КОРРУПЦИЕЙ."]


def dedication(d1):
    tp, mp = 0xcf8, 0xd00
    tiles = screens.block(d1, screens.ptr(d1, tp))
    tmap = screens.block(d1, screens.ptr(d1, mp))
    img, words = screens.decode(tiles, tmap, 32)
    img[44:200] = 8                               # 5 lines at y 51 + 24n
    y = 44
    for l in DEDICATION:
        seriffont.render(img, (256 - seriffont.width(l)) // 2, y, l, core=11, aa=10, outline=9)
        y += 22
    t, m = screens.encode(img, words)
    return screens.put_blocks(d1, [tp, mp], [t, m])


def patch_d1(d1):
    return dedication(disclaimer(d1))
