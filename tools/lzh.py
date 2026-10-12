"""Read members of an LHA/LZH archive (-lh0- stored, -lh5- LZ+Huffman).

Standard library only, so the packaged launcher can open the disc gallery
(LANG/OMAKE/GRAPHIC.LZH) without 7-Zip. Header levels 0 and 1, which is what
1990s DOS LHA wrote. -lh5- is the classic LHA scheme: 8 KiB window, blocks of
canonical Huffman codes (literal/length table + position table).
"""
from dataclasses import dataclass


@dataclass
class Member:
    name: str
    method: str
    size: int          # original size
    crc: int           # CRC-16/ARC of the original data
    data_offset: int   # start of the packed data in the archive
    packed_size: int


def _crc_table():
    table = []
    for n in range(256):
        c = n
        for _ in range(8):
            c = (c >> 1) ^ 0xA001 if c & 1 else c >> 1
        table.append(c)
    return table


_CRC = _crc_table()


def crc16(data: bytes) -> int:
    """CRC-16/ARC (poly 0xA001 reflected, init 0), the LHA checksum."""
    crc = 0
    for b in data:
        crc = (crc >> 8) ^ _CRC[(crc ^ b) & 0xFF]
    return crc


def list_members(archive: bytes) -> list[Member]:
    out = []
    i = 0
    while i < len(archive) and archive[i] != 0:
        hsize = archive[i]
        method = archive[i + 2:i + 7].decode("ascii", "replace")
        packed = int.from_bytes(archive[i + 7:i + 11], "little")
        size = int.from_bytes(archive[i + 11:i + 15], "little")
        level = archive[i + 20]
        if level not in (0, 1):
            raise ValueError(f"unsupported LZH header level {level}")
        nlen = archive[i + 21]
        name = archive[i + 22:i + 22 + nlen].decode("cp932", "replace")
        crc = int.from_bytes(archive[i + 22 + nlen:i + 24 + nlen], "little")
        data = i + hsize + 2
        if level == 1:
            # Extended headers follow the base header; their sizes are
            # counted in the packed size.
            nxt = int.from_bytes(archive[data - 2:data], "little")
            while nxt:
                packed -= nxt
                data += nxt
                nxt = int.from_bytes(archive[data - 2:data], "little")
        out.append(Member(name, method, size, crc, data, packed))
        i = data + packed
    return out


def extract(archive: bytes, name: str) -> bytes:
    for m in list_members(archive):
        if m.name == name:
            packed = archive[m.data_offset:m.data_offset + m.packed_size]
            if m.method == "-lh0-":
                data = bytes(packed)
            elif m.method == "-lh5-":
                data = _lh5(packed, m.size)
            else:
                raise ValueError(f"unsupported LZH method {m.method}")
            if crc16(data) != m.crc:
                raise ValueError(f"CRC mismatch in {name}")
            return data
    raise KeyError(name)


# --- -lh5- ---------------------------------------------------------------

_NC, _NT, _NP = 510, 19, 14          # literal/length, code-length, position
_CBIT, _TBIT, _PBIT = 9, 5, 4


class _Bits:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.buf = 0
        self.n = 0

    def _fill(self, need):
        while self.n < need:
            b = self.data[self.pos] if self.pos < len(self.data) else 0
            self.pos += 1
            self.buf = (self.buf << 8) | b
            self.n += 8

    def peek(self, k):
        self._fill(k)
        return (self.buf >> (self.n - k)) & ((1 << k) - 1)

    def get(self, k):
        if k == 0:
            return 0
        v = self.peek(k)
        self.n -= k
        self.buf &= (1 << self.n) - 1
        return v


class _Huff:
    """Canonical code: shorter first, then by symbol (LHA make_table order)."""

    def __init__(self, lengths, const=None):
        self.const = const
        self.table = {}
        if const is not None:
            return
        code = 0
        for ln in range(1, 17):
            for sym, l in enumerate(lengths):
                if l == ln:
                    self.table[(ln, code)] = sym
                    code += 1
            code <<= 1

    def decode(self, bits: _Bits):
        if self.const is not None:
            return self.const
        code = 0
        for ln in range(1, 17):
            code = (code << 1) | bits.get(1)
            sym = self.table.get((ln, code))
            if sym is not None:
                return sym
        raise ValueError("bad Huffman code in -lh5- stream")


def _read_pt(bits, nn, nbit, special):
    n = bits.get(nbit)
    if n == 0:
        return _Huff(None, const=bits.get(nbit))
    lens = [0] * nn
    i = 0
    while i < n:
        c = bits.get(3)
        if c == 7:
            while bits.get(1):
                c += 1
        lens[i] = c
        i += 1
        if i == special:
            i += bits.get(2)
    return _Huff(lens)


def _read_c(bits, pt):
    n = bits.get(_CBIT)
    if n == 0:
        return _Huff(None, const=bits.get(_CBIT))
    lens = [0] * _NC
    i = 0
    while i < n:
        c = pt.decode(bits)
        if c <= 2:
            run = 1 if c == 0 else bits.get(4) + 3 if c == 1 else bits.get(_CBIT) + 20
            i += run
        else:
            lens[i] = c - 2
            i += 1
    return _Huff(lens)


def _lh5(packed: bytes, size: int) -> bytes:
    bits = _Bits(packed)
    out = bytearray()
    while len(out) < size:
        count = bits.get(16)
        pt = _read_pt(bits, _NT, _TBIT, 3)
        c = _read_c(bits, pt)
        p = _read_pt(bits, _NP, _PBIT, -1)
        for _ in range(count):
            sym = c.decode(bits)
            if sym < 256:
                out.append(sym)
            else:
                length = sym - 256 + 3
                j = p.decode(bits)
                dist = j if j <= 1 else (1 << (j - 1)) + bits.get(j - 1)
                start = len(out) - dist - 1
                if start < 0:
                    raise ValueError("bad back-reference in -lh5- stream")
                for k in range(length):
                    out.append(out[start + k])
            if len(out) >= size:
                break
    return bytes(out[:size])
