"""Mode 1 CD image (2352-byte sectors) editing: ISO9660 files in place, with
the directory record's size updated and EDC/ECC regenerated.

    img = Mode1Image(path); data = img.read_file("SP06.BIN")
    img.write_file("SP06.BIN", new_bytes)   # must fit the file's sector slot
"""
import struct

# --- EDC / ECC (ECMA-130) --------------------------------------------------
_EDC = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    _EDC.append(e)
_F = [0] * 256
_B = [0] * 256
for i in range(256):
    j = (i << 1) ^ (0x11D if i & 0x80 else 0)
    _F[i] = j & 0xFF
    _B[i ^ j & 0xFF] = i


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ _EDC[(e ^ b) & 0xFF]
    return e


def _ecc_block(sec, major_count, minor_count, major_mult, minor_inc, dest):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            temp = sec[0x0C + index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= temp
            b ^= temp
            a = _F[a]
        a = _B[_F[a] ^ b]
        sec[dest + major] = a
        sec[dest + major + major_count] = a ^ b


def fix_sector(sec):
    """sec: bytearray(2352), Mode 1 with sync/header already present."""
    sec[0x810:0x814] = struct.pack("<I", edc(sec[0:0x810]))
    sec[0x814:0x81C] = bytes(8)
    _ecc_block(sec, 86, 24, 2, 86, 0x81C)      # P
    _ecc_block(sec, 52, 43, 86, 88, 0x8C8)     # Q


class Mode1Image:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "r+b")
        self.files = self._dir()

    def sector(self, n):
        self.f.seek(n * 2352)
        return bytearray(self.f.read(2352))

    def put_user(self, n, data):
        sec = self.sector(n)
        sec[16:16 + 2048] = data.ljust(2048, b"\0")
        fix_sector(sec)
        self.f.seek(n * 2352)
        self.f.write(sec)

    def _dir(self):
        pvd = self.sector(16)[16:]
        assert pvd[1:6] == b"CD001"
        self.dir_lba = struct.unpack("<I", pvd[158:162])[0]
        self.dir_size = struct.unpack("<I", pvd[166:170])[0]
        files = {}
        for s in range((self.dir_size + 2047) // 2048):
            blk = self.sector(self.dir_lba + s)[16:16 + 2048]
            i = 0
            while i < 2048:
                L = blk[i]
                if L == 0:
                    break
                r = blk[i:i + L]
                name = r[33:33 + r[32]].decode("latin1").split(";")[0]
                if name not in ("\x00", "\x01"):
                    files[name] = dict(lba=struct.unpack("<I", r[2:6])[0],
                                       size=struct.unpack("<I", r[10:14])[0],
                                       rec=(self.dir_lba + s, i))
                i += L
        lbas = sorted(v["lba"] for v in files.values())
        for v in files.values():                 # sectors up to the next file
            nxt = [l for l in lbas if l > v["lba"]]
            v["slot"] = (nxt[0] - v["lba"]) * 2048 if nxt else None
        return files

    def read_file(self, name):
        v = self.files[name]
        out = bytearray()
        for k in range((v["size"] + 2047) // 2048):
            out += self.sector(v["lba"] + k)[16:16 + 2048]
        return bytes(out[:v["size"]])

    def write_file(self, name, data):
        v = self.files[name]
        if v["slot"] is not None and len(data) > v["slot"]:
            raise SystemExit(f"{name}: {len(data)} bytes > slot {v['slot']}")
        for k in range((len(data) + 2047) // 2048):
            self.put_user(v["lba"] + k, data[k * 2048:(k + 1) * 2048])
        if len(data) != v["size"]:
            lba, off = v["rec"]
            blk = bytearray(self.sector(lba)[16:16 + 2048])
            blk[off + 10:off + 14] = struct.pack("<I", len(data))
            blk[off + 14:off + 18] = struct.pack(">I", len(data))
            self.put_user(lba, bytes(blk))
            v["size"] = len(data)

    def verify(self, n):
        sec = self.sector(n)
        t = bytearray(sec)
        fix_sector(t)
        return t == sec
