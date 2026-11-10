"""The Cyrillic font for SUBCODE.BIN (the sub CPU program, loaded at $D400).

The text renderer takes a glyph index = code - 0x20 and reads an 8x8 1bpp
bitmap from FONT + index*8 and an advance from WIDTH + index; both tables
hold the 102 glyphs of the game's own font. The two `lea table,a5` that set
them up become `jsr hook`: the hook loads the game's table, or ours for an
index from the first Cyrillic code on. Hooks, glyphs and widths are appended
to SUBCODE.BIN, in the free PRG-RAM between its end ($1A376) and where the
script file is loaded ($1A800). See docs/ENGINE.md.
"""
import struct
import cyrfont

SUB_BASE = 0xD400            # SUBCODE.BIN load address (sub CPU PRG-RAM)
FONT, WIDTH = 0x14B7C, 0x14EAC
SITE_FONT, SITE_WIDTH = 0x13EB8, 0x13F94     # the two `lea abs.l,a5`


def hook(table, ext, first_index):
    """lea table,a5 / cmpi.w #first,d1 / bcs.s +6 / lea ext-first*k,a5 / rts"""
    return (b"\x4b\xf9" + struct.pack(">I", table) + b"\x0c\x41" + struct.pack(">H", first_index)
            + b"\x65\x06" + b"\x4b\xf9" + struct.pack(">I", ext) + b"\x4e\x75")


def patch_subcode(sub):
    sub = bytearray(sub)
    font = sub[FONT - SUB_BASE:FONT - SUB_BASE + 102 * 8]
    widths = sub[WIDTH - SUB_BASE:WIDTH - SUB_BASE + 102]
    gl, wd = cyrfont.build(bytes(font), bytes(widths))
    first = cyrfont.FIRST - 0x20                     # glyph index of the first Cyrillic code
    end = SUB_BASE + len(sub)
    assert end % 2 == 0
    hf, hw = end, end + 20
    ext_f, ext_w = end + 40, end + 40 + len(gl)
    blob = hook(FONT, ext_f - first * 8, first) + hook(WIDTH, ext_w - first, first) + gl + wd
    if len(blob) % 2:
        blob += b"\0"
    assert end + len(blob) <= 0x1A800, hex(end + len(blob))
    for site, target in ((SITE_FONT, hf), (SITE_WIDTH, hw)):
        o = site - SUB_BASE
        assert sub[o:o + 2] == b"\x4b\xf9", (hex(site), sub[o:o + 6].hex())
        sub[o:o + 6] = b"\x4e\xb9" + struct.pack(">I", target)
    return bytes(sub) + blob


