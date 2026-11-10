"""Relaid-out script text for the Sega CD Snatcher.

SUBCODE.BIN: tools/textmap.s (offset remap + four hooks) is linked after
the font blob and the four places that turn a string offset into an
address call it (see docs/ENGINE.md).

SPxx.BIN: `relayout(sp, new)` writes the text region anew - every string
in its original order, replaced where `new` has it - then a remap table
(orig offset -> new offset, for every string start) and the table's own
offset into the bytecode area's padding at 0x37FE. The bytecode is not
touched.
"""
import os, struct, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SUB_BASE = 0xD400
TEXT_BASE = 0x3800
TPTR = 0x37FE
SP_MAX = 0x28000 - 0x1A800       # $28000 is another buffer: the file must end before it

# (address, original bytes, hook): each 10-byte site becomes jsr hook.l + 2 nops
SITES = [
    (0x139EA, "33f9000097d000009746", "hookS"),   # dialogue line start -> $9746
    (0x10ECE, "41f90001e00041f07000", "hookA0"),  # name/menu string copy
    (0x11324, "41f90001e00010307000", "hookB"),   # first letter of an item name
    (0x11B04, "43f90001e00043f17000", "hookA1"),  # menu string compare
]


def assemble(base):
    """(code bytes, {symbol: address}) of textmap.s linked at `base`."""
    with tempfile.TemporaryDirectory() as t:
        o, e, b = (os.path.join(t, n) for n in ("t.o", "t.elf", "t.bin"))
        subprocess.run(["m68k-linux-gnu-as", "-m68000", "--register-prefix-optional",
                        "-o", o, os.path.join(HERE, "textmap.s")], check=True)
        subprocess.run(["m68k-linux-gnu-ld", "-Ttext", hex(base), "-o", e, o], check=True)
        subprocess.run(["m68k-linux-gnu-objcopy", "-O", "binary", "-j", ".text", e, b], check=True)
        nm = subprocess.run(["m68k-linux-gnu-nm", e], check=True, capture_output=True, text=True).stdout
        syms = {p[2]: int(p[0], 16) for p in (l.split() for l in nm.splitlines()) if len(p) == 3}
        return open(b, "rb").read(), syms


def patch_subcode(sub):
    """SUBCODE.BIN (already with the font blob) + remap code and hooks."""
    sub = bytearray(sub)
    if len(sub) % 2:
        sub.append(0)
    base = SUB_BASE + len(sub)
    code, syms = assemble(base)
    assert base + len(code) <= 0x1A800, hex(base + len(code))
    for addr, orig, sym in SITES:
        o = addr - SUB_BASE
        assert sub[o:o + 10].hex() == orig, (hex(addr), sub[o:o + 10].hex())
        sub[o:o + 10] = b"\x4e\xb9" + struct.pack(">I", syms[sym]) + b"\x4e\x71\x4e\x71"
    return bytes(sub) + code


def strings(sp):
    """[(offset, bytes)] of the text region: every position after a 0xFF
    (and the region's start) begins a string, empty ones included."""
    out, i, n = [], TEXT_BASE, len(sp)
    while i < n:
        j = sp.find(b"\xff", i)
        if j < 0:
            out.append((i - TEXT_BASE, sp[i:]))
            break
        out.append((i - TEXT_BASE, sp[i:j]))
        i = j + 1
    return out


def relayout(sp, new=None, lead=b""):
    """`new`: {orig offset: replacement bytes (no 0xFF)}. `lead`: bytes put
    before the first string (a test that every offset moved)."""
    new = new or {}
    if len(sp) <= TEXT_BASE:
        return sp
    text, table = bytearray(lead), []
    for off, s in strings(sp):
        table.append((off, len(text)))
        text += new.get(off, s) + b"\xff"
    if len(text) % 2:
        text.append(0xFF)
    tpos = len(text)
    text += struct.pack(">H", len(table))
    for a, b in table:
        text += struct.pack(">HH", a, b)
    out = bytearray(sp[:TEXT_BASE]) + text
    assert out[TPTR:TPTR + 2] == b"\xff\xff", "bytecode padding expected at 0x37FE"
    out[TPTR:TPTR + 2] = struct.pack(">H", tpos)
    if len(out) > SP_MAX:
        raise SystemExit(f"script file {len(out)} bytes > {SP_MAX} (RAM up to $28000)")
    if tpos + 2 + 4 * len(table) > 0xFFFF:
        raise SystemExit("text region over 64 KB")
    return bytes(out)
