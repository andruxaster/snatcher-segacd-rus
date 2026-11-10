"""The engine test: Mika's first line (SP06) in Russian, appended to the text
region with its one reference moved. A string is referenced from the script's
bytecode by a 16-bit offset from the text region (file offset 0x3800,
loaded at $1E000); here the reference is found by its pattern, which is
good for this one line only."""
import struct
import cyrfont

TEXT_BASE = 0x3800


def patch_sp06(sp):
    sp = bytearray(sp)
    old = 0x3B20                     # "Welcome to Junker Headquarters."
    ref = sp.find(b"\x43\x20\x00\x04" + struct.pack(">H", old - TEXT_BASE))
    assert ref > 0
    new = len(sp)
    sp += cyrfont.encode("Добро пожаловать в штаб ДЖАНКЕРа.￥Чем могу помочь?") + b"\xff"
    sp[ref + 4:ref + 6] = struct.pack(">H", new - TEXT_BASE)
    return bytes(sp)
