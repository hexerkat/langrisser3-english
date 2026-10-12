"""jpeg_baseline.py — decode a baseline JPEG to RGB, standard library only.

Tkinter cannot show JPEG and the launcher may not depend on Pillow, so this
decodes the disc gallery picture itself. Scope: baseline / extended sequential
Huffman (SOF0, SOF1), 8-bit, 3 components (YCbCr), any sampling factors. Progressive,
arithmetic coding and restart intervals raise ValueError (the caller falls
back to no picture).

scale=2/4/8 decodes straight to 1/scale size: each 8x8 block's IDCT is
evaluated already averaged over scale x scale pixels, so the full-size image
is never built. Chroma is upsampled by replication.
"""
import math

_ZIGZAG = [
    0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
    12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
    35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
    58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63,
]
_LOOK = 9   # bits resolved by one table lookup


class _Huff:
    def __init__(self, counts, symbols):
        self.look = [None] * (1 << _LOOK)
        self.slow = {}
        code = k = 0
        for ln in range(1, 17):
            for _ in range(counts[ln - 1]):
                sym = symbols[k]
                k += 1
                if ln <= _LOOK:
                    pad = _LOOK - ln
                    for low in range(1 << pad):
                        self.look[(code << pad) | low] = (sym, ln)
                else:
                    self.slow[(ln, code)] = sym
                code += 1
            code <<= 1


class _Bits:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.buf = 0
        self.n = 0

    def peek(self, k):
        while self.n < k:
            b = self.data[self.pos] if self.pos < len(self.data) else 0
            self.pos += 1
            self.buf = ((self.buf << 8) | b) & 0xFFFFFFFF
            self.n += 8
        return (self.buf >> (self.n - k)) & ((1 << k) - 1)

    def skip(self, k):
        self.n -= k

    def get(self, k):
        if k == 0:
            return 0
        v = self.peek(k)
        self.n -= k
        return v

    def symbol(self, h):
        hit = h.look[self.peek(_LOOK)]
        if hit is not None:
            self.n -= hit[1]
            return hit[0]
        code = self.get(_LOOK)
        for ln in range(_LOOK + 1, 17):
            code = (code << 1) | self.get(1)
            sym = h.slow.get((ln, code))
            if sym is not None:
                return sym
        raise ValueError("bad Huffman code")


def _extend(v, t):
    return v - (1 << t) + 1 if t and v < (1 << (t - 1)) else v


def _basis(scale):
    """B[u][x]: c(u)/2 * cos((2p+1)u*pi/16) averaged over the scale pixels
    p that output pixel x covers."""
    n = 8 // scale
    B = []
    for u in range(8):
        cu = math.sqrt(0.5) if u == 0 else 1.0
        row = []
        for x in range(n):
            ps = range(x * scale, x * scale + scale)
            row.append(sum(cu / 2 * math.cos((2 * p + 1) * u * math.pi / 16) for p in ps) / scale)
        B.append(row)
    # outer products, indexed by the natural (row-major) coefficient index
    return n, [[B[k // 8][y] * B[k % 8][x] for y in range(n) for x in range(n)]
               for k in range(64)]


def decode(data: bytes, scale: int = 1):
    """Return (width, height, rgb bytes) at 1/scale size."""
    width, height, comps = _decode_comps(data, scale)
    return _to_rgb(width, height, comps, scale)


def decode_planes(data: bytes, scale: int = 1):
    """Return (width, height, [(w, h, bytes) per component]) at 1/scale
    size, before any chroma upsampling or color conversion."""
    width, height, comps = _decode_comps(data, scale)
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    planes = []
    for c in comps:
        cw = -(-(-(-width * c["h"] // hmax)) // scale)
        ch = -(-(-(-height * c["v"] // vmax)) // scale)
        p = c["plane"]
        planes.append((cw, ch, bytes(p[y * c["pw"] + x] for y in range(ch) for x in range(cw))))
    return width, height, planes


def _decode_comps(data, scale):
    if scale not in (1, 2, 4, 8):
        raise ValueError("scale must be 1, 2, 4 or 8")
    if data[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    qt, hts, comps = {}, {}, []
    width = height = 0
    i = 2
    while True:
        if i + 4 > len(data) or data[i] != 0xFF:
            raise ValueError("bad JPEG marker structure")
        marker = data[i + 1]
        if marker == 0xFF:
            i += 1
            continue
        seglen = int.from_bytes(data[i + 2:i + 4], "big")
        seg = data[i + 4:i + 2 + seglen]
        if marker == 0xDB:
            j = 0
            while j < len(seg):
                pq, tq = seg[j] >> 4, seg[j] & 15
                if pq:
                    vals = [int.from_bytes(seg[j + 1 + 2 * k:j + 3 + 2 * k], "big") for k in range(64)]
                    j += 129
                else:
                    vals = list(seg[j + 1:j + 65])
                    j += 65
                q = [0] * 64
                for k in range(64):
                    q[_ZIGZAG[k]] = vals[k]
                qt[tq] = q
        elif marker in (0xC0, 0xC1):
            if seg[0] != 8:
                raise ValueError("only 8-bit JPEG")
            height = int.from_bytes(seg[1:3], "big")
            width = int.from_bytes(seg[3:5], "big")
            for k in range(seg[5]):
                cid, hv, tq = seg[6 + 3 * k:9 + 3 * k]
                comps.append({"id": cid, "h": hv >> 4, "v": hv & 15, "tq": tq})
            if len(comps) != 3:
                raise ValueError("only 3-component (YCbCr) JPEG")
        elif 0xC2 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            raise ValueError("unsupported JPEG type (progressive / lossless / arithmetic)")
        elif marker == 0xC4:
            j = 0
            while j < len(seg):
                tc, th = seg[j] >> 4, seg[j] & 15
                counts = seg[j + 1:j + 17]
                total = sum(counts)
                hts[(tc, th)] = _Huff(counts, seg[j + 17:j + 17 + total])
                j += 17 + total
        elif marker == 0xDD:
            if int.from_bytes(seg[0:2], "big"):
                raise ValueError("restart intervals not supported")
        elif marker == 0xDA:
            if not comps:
                raise ValueError("scan before frame header")
            ns = seg[0]
            if ns != len(comps):
                raise ValueError("only single interleaved scan")
            for k in range(ns):
                cid, t = seg[1 + 2 * k], seg[2 + 2 * k]
                c = next(c for c in comps if c["id"] == cid)
                c["dc"], c["ac"] = hts[(0, t >> 4)], hts[(1, t & 15)]
            _scan(data, i + 2 + seglen, width, height, comps, qt, scale)
            return width, height, comps
        elif marker == 0xD9:
            raise ValueError("no scan in JPEG")
        i += 2 + seglen


def _scan(data, start, width, height, comps, qt, scale):
    end = start
    while True:
        end = data.find(b"\xff", end)
        if end < 0 or end + 1 >= len(data):
            end = len(data)
            break
        if data[end + 1] != 0x00:
            break
        end += 2
    bits = _Bits(data[start:end].replace(b"\xff\x00", b"\xff"))

    n, outer = _basis(scale)
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    mcux = (width + 8 * hmax - 1) // (8 * hmax)
    mcuy = (height + 8 * vmax - 1) // (8 * vmax)
    for c in comps:
        c["pw"] = mcux * c["h"] * n
        c["ph"] = mcuy * c["v"] * n
        c["plane"] = bytearray(c["pw"] * c["ph"])
        c["pred"] = 0
        c["q"] = qt[c["tq"]]
    nn = n * n
    base = [128.0] * nn

    for my in range(mcuy):
        for mx in range(mcux):
            for c in comps:
                q, dc, ac, plane, pw = c["q"], c["dc"], c["ac"], c["plane"], c["pw"]
                for by in range(c["v"]):
                    for bx in range(c["h"]):
                        t = bits.symbol(dc)
                        c["pred"] += _extend(bits.get(t), t)
                        block = [b + c["pred"] * q[0] * o for b, o in zip(base, outer[0])]
                        k = 1
                        while k < 64:
                            rs = bits.symbol(ac)
                            r, s = rs >> 4, rs & 15
                            if s == 0:
                                if r != 15:
                                    break
                                k += 16
                                continue
                            k += r
                            if k > 63:
                                raise ValueError("bad AC run")
                            z = _ZIGZAG[k]
                            v = _extend(bits.get(s), s) * q[z]
                            block = [b + v * o for b, o in zip(block, outer[z])]
                            k += 1
                        ox = (mx * c["h"] + bx) * n
                        oy = (my * c["v"] + by) * n
                        for y in range(n):
                            row = (oy + y) * pw + ox
                            for x in range(n):
                                v = int(block[y * n + x] + 0.5)
                                plane[row + x] = 0 if v < 0 else 255 if v > 255 else v


def _to_rgb(width, height, comps, scale):
    hmax = max(c["h"] for c in comps)
    vmax = max(c["v"] for c in comps)
    ow = (width + scale - 1) // scale
    oh = (height + scale - 1) // scale
    rgb = bytearray(ow * oh * 3)
    Y, Cb, Cr = comps
    yx = [x * Y["h"] // hmax for x in range(ow)]
    bx_ = [x * Cb["h"] // hmax for x in range(ow)]
    rx_ = [x * Cr["h"] // hmax for x in range(ow)]
    o = 0
    for y in range(oh):
        yrow = (y * Y["v"] // vmax) * Y["pw"]
        brow = (y * Cb["v"] // vmax) * Cb["pw"]
        rrow = (y * Cr["v"] // vmax) * Cr["pw"]
        yp, bp, rp = Y["plane"], Cb["plane"], Cr["plane"]
        for x in range(ow):
            l = yp[yrow + yx[x]]
            cb = bp[brow + bx_[x]] - 128
            cr = rp[rrow + rx_[x]] - 128
            r = int(l + 1.402 * cr + 0.5)
            g = int(l - 0.344136 * cb - 0.714136 * cr + 0.5)
            b = int(l + 1.772 * cb + 0.5)
            rgb[o] = 0 if r < 0 else 255 if r > 255 else r
            rgb[o + 1] = 0 if g < 0 else 255 if g > 255 else g
            rgb[o + 2] = 0 if b < 0 else 255 if b > 255 else b
            o += 3
    return ow, oh, bytes(rgb)
