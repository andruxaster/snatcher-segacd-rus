"""Konami LZ as used by the Sega CD Snatcher (Main CPU, $FF1996).

Flag bytes, read LSB first, one bit per step: 0 = copy one literal byte;
1 = a command byte c:
  c == 0x1F            end
  c <  0x80            long copy: offset = ((c & 0xE0) << 3) | next byte,
                       length = (c & 0x1F) + 3
  0x80 <= c < 0xC0     short copy: offset = c & 0x0F, length = (c >> 4) - 6
  c >= 0xC0            literal run: c - 0xB8 bytes follow
Copies read from the output `offset` bytes back.
"""


def decompress(src, pos=0):
    """(data, end position) of the stream at src[pos]."""
    out = bytearray()
    flags = bits = 0
    while True:
        if bits == 0:
            flags = src[pos]
            pos += 1
            bits = 8
        bit = flags & 1
        flags >>= 1
        bits -= 1
        if not bit:
            out.append(src[pos])
            pos += 1
            continue
        c = src[pos]
        pos += 1
        if c < 0x80:
            if c == 0x1F:
                return bytes(out), pos
            off = ((c & 0xE0) << 3) | src[pos]
            pos += 1
            n = (c & 0x1F) + 3
        elif c < 0xC0:
            off = c & 0x0F
            n = (c >> 4) - 6
        else:
            n = c - 0xB8
            out += src[pos:pos + n]
            pos += n
            continue
        if off == 0 or off > len(out):
            raise ValueError(f"bad offset {off} at {pos}")
        for _ in range(n):
            out.append(out[-off])


def compress(data):
    """A stream `decompress` reads back: greedy matches (long copies of 3-34
    bytes within 1023 back - c < 0x80 leaves two offset bits in c - short
    ones of 2-5 within 15), literal runs. A long copy whose command byte
    would be 0x1F (the end mark) is shortened by one."""
    data = bytes(data)
    out = bytearray()
    ops = []                                    # (is_command, bytes)
    lit = bytearray()

    def flush_lit():
        nonlocal lit
        while len(lit) >= 8:
            n = min(len(lit), 71)
            ops.append((True, bytes([0xB8 + n]) + bytes(lit[:n])))
            lit = lit[n:]
        for b in lit:
            ops.append((False, bytes([b])))
        lit = bytearray()

    i, n = 0, len(data)
    while i < n:
        best_len = best_off = 0
        lo = max(0, i - 1023)
        maxlen = min(34, n - i)
        j = data.rfind(data[i:i + 3], lo, i + 2) if maxlen >= 3 else -1
        # scan candidates
        start = lo
        while maxlen >= 2:
            k = data.find(data[i:i + 2], start, i + 1)
            if k < 0 or k >= i:
                break
            L = 0
            while L < maxlen and data[k + L] == data[i + L]:
                L += 1                          # overlap allowed (k + L may pass i)
            off = i - k
            if L > best_len or (L == best_len and off < best_off):
                best_len, best_off = L, off
            start = k + 1
        if best_len == 34 and best_off < 256:
            best_len = 33                       # c would be 0x1F, the end mark
        if best_len >= 3 and not (best_len <= 5 and best_off <= 15):
            flush_lit()
            ops.append((True, bytes([((best_off >> 3) & 0xE0) | (best_len - 3), best_off & 0xFF])))
            i += best_len
        elif best_len >= 2 and best_off <= 15:
            L = min(best_len, 5)
            flush_lit()
            ops.append((True, bytes([0x80 | ((L + 6) - 8) << 4 | best_off])))
            i += L
        else:
            lit.append(data[i])
            i += 1
    flush_lit()
    ops.append((True, b"\x1f"))
    for k in range(0, len(ops), 8):
        group = ops[k:k + 8]
        flags = 0
        for b, (cmd, _) in enumerate(group):
            if cmd:
                flags |= 1 << b
        out.append(flags)
        for _, payload in group:
            out += payload
    return bytes(out)
