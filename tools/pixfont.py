"""Bitmap text from X11 misc-fixed BDF fonts (public domain, tools/fonts/),
drawn in the colours of the game's text screens: a 1-px skeleton font as the
core, an optional 4-neighbour outline and an optional anti-aliasing colour
on stroke ends. Glyphs are trimmed to their ink: proportional spacing."""
import os
import numpy as np

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_cache = {}


class Font:
    def __init__(self, name, gap=1, space=None):
        self.glyphs, self.gap = {}, gap
        cur = None
        for line in open(os.path.join(FONTS, name + ".bdf"), encoding="latin-1"):
            p = line.split()
            if not p:
                continue
            if p[0] == "FONT_ASCENT":
                self.ascent = int(p[1])
            elif p[0] == "FONTBOUNDINGBOX":
                self.cell = int(p[1])
            elif p[0] == "ENCODING":
                cur = {"code": int(p[1])}
            elif p[0] == "BBX" and cur is not None:
                cur["bbx"] = list(map(int, p[1:5]))
            elif p[0] == "BITMAP" and cur is not None:
                cur["rows"] = []
            elif p[0] == "ENDCHAR" and cur is not None:
                w, h, xo, yo = cur["bbx"]
                rows = cur["rows"]
                bits = np.array([[(int(r, 16) >> (len(r) * 4 - 1 - x)) & 1 for x in range(w)] for r in rows],
                                dtype=bool).reshape(h, w)
                top = self.ascent - (h + yo)
                cur["bits"], cur["top"] = bits, top
                self.glyphs[cur["code"]] = cur
                cur = None
            elif cur is not None and "rows" in cur:
                cur["rows"].append(p[0])
        self.space = space if space is not None else max(2, self.cell // 2)

    def glyph(self, ch):
        g = self.glyphs[ord(ch)]
        b = g["bits"]
        cols = np.nonzero(b.any(0))[0]
        if len(cols) == 0:
            return None, 0
        return b[:, cols[0]:cols[-1] + 1], g["top"]

    def width(self, text):
        w = 0
        for ch in text:
            b, _ = (None, 0) if ch == " " else self.glyph(ch)
            w += self.space if b is None else b.shape[1] + self.gap
        return w - self.gap

    def mask(self, text, height):
        """Skeleton mask of the text line, rows 0..height-1 = font ascent box."""
        m = np.zeros((height, self.width(text) + 1), dtype=bool)
        x = 0
        for ch in text:
            b, top = (None, 0) if ch == " " else self.glyph(ch)
            if b is None:
                x += self.space
                continue
            h, w = b.shape
            m[max(top, 0):top + h, x:x + w] |= b[max(-top, 0):height - top]
            x += w + self.gap
        return m


def font(name, **kw):
    key = (name, tuple(sorted(kw.items())))
    if key not in _cache:
        _cache[key] = Font(name, **kw)
    return _cache[key]


def draw(img, x, y, text, f, core, outline=None, height=None, bold=False):
    """Draw `text` with its ascent box top-left at (x, y)."""
    height = height or f.cell + 4
    m = f.mask(text, height)
    if bold:
        m[:, 1:] |= m[:, :-1].copy()
    h, w = m.shape
    big = np.zeros((h + 2, w + 2), dtype=bool)
    big[1:-1, 1:-1] = m
    reg = img[y - 1:y - 1 + h + 2, x - 1:x - 1 + w + 2]
    big = big[:reg.shape[0], :reg.shape[1]]
    if outline is not None:
        o = np.zeros_like(big)
        o[1:, :] |= big[:-1, :]; o[:-1, :] |= big[1:, :]
        o[:, 1:] |= big[:, :-1]; o[:, :-1] |= big[:, 1:]
        reg[o & ~big] = outline
    reg[big] = core
    return x + w


def wrap(text, px, f, bold=False):
    words, out = text.split(" "), []
    for wd in words:
        if out and len(out[-1].split(" ")[-1]) == 1 and out[-1][-1].isalpha():
            out[-1] += " " + wd
        else:
            out.append(wd)
    lines, cur = [], ""
    for wd in out:
        t = wd if not cur else cur + " " + wd
        if f.width(t) + (len(t) if bold else 0) <= px:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    return lines + [cur]
