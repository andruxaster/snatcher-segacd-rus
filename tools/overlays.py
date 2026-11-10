"""Russian text screens outside the script (DATA_D1: disclaimer, ...).

Each screen: the file offsets of the code-table longs that point at its
tiles and tilemap block, the area to clear and the Russian text to draw.
"""
import os, sys
import numpy as np
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


# --- DATA_D2: backup RAM screens --------------------------------------------
import pixfont

BIG = dict(f="10x20", core=1, outline=2)        # "Couldn't save onto"
HI = dict(f="10x20", core=5, outline=7)         # "CD Backup RAM Cart" (highlighted)
MID = dict(f="7x13", core=1, outline=2)         # the long "no free memory" message
MIDHI = dict(f="7x13", core=5, outline=7)
CAPS = dict(f="6x10", core=5)                   # "- PRESS START BUTTON -"
SMALL = dict(f="6x10", core=5)


def text(img, y, segs, cx=128):
    """Draw a line of (text, style) segments centred on `cx`."""
    if isinstance(segs, str):
        raise TypeError
    fonts = [pixfont.font(st["f"]) for _, st in segs]
    w = sum(f.width(t) for (t, _), f in zip(segs, fonts))
    x = cx - w // 2
    for (t, st), f in zip(segs, fonts):
        pixfont.draw(img, x, y, t, f, st["core"], st.get("outline"), height=f.ascent + 4)
        x += f.width(t)
    return w


START = [("- НАЖМИТЕ START -", CAPS)]
OWN = {0x3cc: 1}         # its first tile block is full: new tiles go after the second one

# (descriptor, [(y0, y1, x0, x1) areas to clear], [(y, [(text, style)...])]).
# y = top of the font's ascent box (10x20 capitals start 3 px below it).
D2_SCREENS = [
    (0x35c, [(40, 86, 0, 256), (110, 120, 50, 212), (158, 168, 50, 212)],
     [(39, [("Картридж памяти", HI), (" подключен.", BIG)]),
      (63, [("Какую память выбрать?", BIG)]),
      (110, [("ВНУТРЕННЯЯ ПАМЯТЬ", dict(f="6x10", core=1))]),
      (158, [("КАРТРИДЖ ПАМЯТИ", dict(f="6x10", core=5))])]),
    (0x394, [(70, 138, 0, 256)],
     [(70, [("Вернитесь в меню приставки", BIG)]), (93, [("и отформатируйте память.", BIG)]),
      (127, START)]),
    (0x3cc, [(16, 138, 0, 256)],
     [(17, [("В памяти нет свободного места:", MID)]),
      (33, [("для записи нужно 14 блоков.", MID)]),
      (49, [("Сотрите файл другой игры или", MID)]),
      (65, [("скопируйте его в ", MID), ("картридж памяти", MIDHI)]),
      (81, [("или во ", MID), ("внутреннюю память", MIDHI), (".", MID)]),
      (110, [("НАЖМИТЕ START,", CAPS)]),
      (123, [("чтобы выйти в меню приставки", SMALL)])]),
    (0x40c, [(70, 118, 46, 210), (132, 146, 0, 256)],
     [(69, [("Ошибка загрузки!", BIG)]), (94, [("Начните сначала.", BIG)]),
      (135, START)]),
    (0x444, [(38, 106, 0, 256)],
     [(38, [("Не удалось записать", BIG)]), (60, [("во внутреннюю память.", BIG)]), (95, START)]),
    (0x474, [(38, 106, 0, 256)],
     [(38, [("Не удалось записать", BIG)]), (60, [("в картридж памяти.", HI)]), (95, START)]),
]


def patch_d2(d2):
    d2 = patch_title(d2)
    for at, clear, lines in D2_SCREENS:
        s = screens.Screen(d2, at, own=OWN.get(at, 0))
        bg = int(np.bincount(s.img.flatten()).argmax())
        for y0, y1, x0, x1 in clear:
            s.img[y0:y1, x0:x1] = bg
        for y, segs in lines:
            text(s.img, y, segs)
        d2 = s.save()
    return d2


# --- DATA_D2: title menu (sprites) ------------------------------------------
# Block at VRAM 0x20: one blank tile, then 64 8x16 sprite columns holding
# "▶ NEW GAME CONTINUE OPTION" twice (two colour sets). Each word is redrawn
# inside its own columns; the layout stays the same.
TITLE_PTRS = (0x28c, 0x508)
TITLE_WORDS = [(16, 112, "НОВАЯ ИГРА"), (112, 200, "ПРОДОЛЖИТЬ"), (200, 256, "ОПЦИИ")]
TITLE_COLOURS = [(0, 13, 14), (256, 12, 15)]          # strip x, upper, lower core colour


def serif_mask(text, gap=1, space=6):
    """(core, aa) masks of `text` in the dedication's serif capitals."""
    cols_c, cols_a = [], []
    for k, ch in enumerate(text):
        if ch == " ":
            cols_c.append(np.zeros((9, space), bool)); cols_a.append(np.zeros((9, space), bool))
            continue
        g = seriffont.G[ch]
        cols_c.append(np.array([[p == "#" for p in r] for r in g]))
        cols_a.append(np.array([[p == "o" for p in r] for r in g]))
        if k < len(text) - 1 and text[k + 1] != " ":
            cols_c.append(np.zeros((9, gap), bool)); cols_a.append(np.zeros((9, gap), bool))
    return np.hstack(cols_c), np.hstack(cols_a)


def sprite_word(strip, x0, x1, text, top, bot, shadow=3, y=4):
    """Serif word in the title-menu style: light core, darker anti-aliasing,
    a dark 1-px drop shadow (the letters are thinner than the English ones:
    ПРОДОЛЖИТЬ has to fit where CONTINUE was)."""
    strip[:, x0:x1] = 0
    c, a = serif_mask(text)
    m = c | a
    h, w = m.shape
    x = x0 + 1
    assert x + w + 1 <= x1, (text, w, x1 - x0)
    H = strip.shape[0]
    sh = np.zeros((H + 2, w + 1), dtype=bool)
    sh[y + 1:y + 1 + h, 1:w + 1] = m
    reg = strip[:, x:x + w + 1]
    reg[sh[:H]] = shadow
    full = lambda q: np.vstack([np.zeros((y, w), bool), q, np.zeros((H - y - h, w), bool)])
    m, a = full(m), full(a)
    reg = strip[:, x:x + w]
    reg[m] = top
    reg[a] = bot


def patch_title(d2):
    off = screens.ptr(d2, TITLE_PTRS[0])
    t = screens.tiles_to_array(screens.block(d2, off))
    strip = np.hstack([np.vstack([t[i], t[i + 1]]) for i in range(1, len(t) - 1, 2)])
    for base, top, bot in TITLE_COLOURS:
        for x0, x1, word in TITLE_WORDS:
            sprite_word(strip, base + x0, base + x1, word, top, bot)
    for n, i in enumerate(range(1, len(t) - 1, 2)):
        t[i], t[i + 1] = strip[:8, n * 8:n * 8 + 8], strip[8:, n * 8:n * 8 + 8]
    return screens.put_blocks(d2, [TITLE_PTRS[0]], [screens.array_to_tiles(t)], also=[TITLE_PTRS[1]])
