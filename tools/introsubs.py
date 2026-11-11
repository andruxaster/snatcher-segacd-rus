"""Russian subtitles for the intro newsreel (DATA_D1).

text/ru/intro_subs.json holds the cues: track-time span, text, and the
palette entries to draw with (line, text index, outline index) per span of
the scene palette. This module turns them into data for tools/introsubs.s
(glyphs of the 7x13 misc-fixed font, line-broken strings, a BCD cue table),
links the player after the end of DATA_D1 and points DATA_D1's per-frame
routine (header long +8) at it. See docs/ENGINE.md, "Субтитры вступления".
"""
import json
import os
import struct
import subprocess
import tempfile

import pixfont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CUES = os.path.join(ROOT, "text", "ru", "intro_subs.json")
LOAD = 0x28000
FONT = "7x13"
MAXW = 246          # text width per line, px (sprites cover 256)
SCRATCH = 0x4E000   # introsubs.s scratch RAM: the file must end below it


def bcd(t):
    m, s = divmod(t, 60)
    f = int(round((s % 1) * 75))
    s = int(s)
    if f == 75:
        s, f = s + 1, 0
    b = lambda v: (v // 10) << 4 | v % 10
    return b(int(m)) << 24 | b(s) << 16 | b(f) << 8


def layout(text, f):
    lines = pixfont.wrap(text, MAXW, f)
    if len(lines) > 2:
        raise SystemExit(f"intro_subs: more than two lines: {text}")
    return lines


def data_source(cues):
    f = pixfont.font(FONT)
    chars = sorted({ch for c in cues for ch in c["ru"]})
    gid = {ch: i for i, ch in enumerate(chars)}
    glyphs = []
    for ch in chars:
        if ch == " ":
            glyphs.append([f.space] + [0] * 13)
            continue
        m = f.mask(ch, 13)
        m = m[:, :m.any(0).nonzero()[0][-1] + 1]
        if m.shape[1] > 8:
            raise SystemExit(f"glyph too wide: {ch}")
        rows = [int("".join("1" if v else "0" for v in r).ljust(8, "0"), 2) for r in m]
        glyphs.append([m.shape[1] + f.gap] + rows)
    texts, table = [], []
    for k, c in enumerate(cues):
        blob = []
        for i, ln in enumerate(layout(c["ru"], f)):
            if i:
                blob.append(0xFE)
            blob.append((256 - f.width(ln)) // 2)
            blob += [gid[ch] for ch in ln]
        blob.append(0xFF)
        texts.append(blob)
        for start, line, w, b in c["pal"]:
            table.append((bcd(start), f"text{k}", line << 8 | w << 4 | b))
        table.append((bcd(c["end"]), None, 0))
    table.sort(key=lambda e: e[0])
    out = ["        .even", "CUES:"]
    for t, lab, col in table:
        out.append(f"        .long   0x{t:08x}, {lab or 0}")
        out.append(f"        .word   0x{col:04x}")
    out.append("        .long   -1")
    out.append("GLYPHS:")
    for g in glyphs:
        out.append("        .byte   " + ", ".join(str(v) for v in g))
    for k, blob in enumerate(texts):
        out.append(f"text{k}:")
        out.append("        .byte   " + ", ".join(str(v) for v in blob))
    return "\n".join(out) + "\n"


def assemble(base, cues):
    with tempfile.TemporaryDirectory() as t:
        open(os.path.join(t, "introsubs_data.s"), "w").write(data_source(cues))
        src = os.path.join(t, "introsubs.s")
        open(src, "w").write(open(os.path.join(HERE, "introsubs.s")).read())
        o, e, b = (os.path.join(t, n) for n in ("s.o", "s.elf", "s.bin"))
        subprocess.run(["m68k-linux-gnu-as", "-m68000", "--register-prefix-optional",
                        "-I", t, "-o", o, src], check=True)
        subprocess.run(["m68k-linux-gnu-ld", "-Ttext", hex(base), "-o", e, o], check=True)
        subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", "-j", ".text", e, b], check=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", e], check=True, capture_output=True, text=True).stdout
        syms = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
        return open(b, "rb").read(), syms


def patch(d1):
    """DATA_D1 bytes (already with the translated screens) -> with subtitles."""
    d = bytearray(d1)
    if struct.unpack(">I", d[8:12])[0] != 0x29266:
        raise SystemExit("DATA_D1: unexpected frame routine")
    while len(d) % 4:
        d.append(0)
    cues = json.load(open(CUES, encoding="utf-8"))["cues"]
    code, syms = assemble(LOAD + len(d), cues)
    d += code
    if LOAD + len(d) > SCRATCH:
        raise SystemExit(f"DATA_D1 too long: ends at {LOAD + len(d):#x}")
    d[8:12] = struct.pack(">I", syms["tick"])
    return bytes(d), len(code)
