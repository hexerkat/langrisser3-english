"""tools/staff_roll.py: the English staff roll in LANG/STAFF.DAT.

STAFF.DAT (PROG_2 FUN_06054c00 plays it after the ending) is a container
(u32 count, then u32 offset/size pairs, entries 4-byte aligned) of 3:
  0  Huffman tree shared by the two entries below
  1  the roll: u8 u8, u16 width (320), u16, 16 BGR555 colors, then
     320x1536 pixels at 4 bpp, high nibble first; unpacked to VDP1 VRAM
     0x25C0FFDA so the pixels land at 0x25C10000
  2  the 16x16 katakana font that writes the player's name into the roll

The build unpacks the player's own STAFF.DAT, pastes the English overlay
(assets/staff_roll/staff_roll_en.png) inside the rectangles listed in
staff_roll_en_rects.json, and packs it again. The overlay and the rects are
made by the separate langrisser3-graphics-extractor repo; they hold no
Japanese art. The file grows (about 39 KB -> 46 KB); PROG_2 loads it at
LWRAM 0x00217000, inside the scratch the same program uses for OPS.DAT.

Codec: port of the JP A0LANG routine FUN_0600FA88 and its byte helper
FUN_0600FA48 (tests/test_staff_roll.py runs both on sh2_mini).
  Tree: 2-byte nodes, root at offset 0. At an inner node the next bit b
  (LSB first) moves to node + (table[node + b] + 1) * 2. A node is a leaf
  when its second byte is above 0xF9: 0xFF literal table[node], 0xFE end,
  0xFA..0xFD symbol k = type - 0xFA written table[node] + 1 times.
  Entry header b0..b4: symbol k writes value (0, b0, b1, b2)[k] in mode
  (b3 & 15, b3 >> 4, b4 & 15, b4 >> 4)[k]; mode d adds the byte written d
  outputs before (16-byte history, zero at start), mode 0 writes it as is.
"""
from __future__ import annotations

import heapq
import json
import struct

import png_indexed

LEAF_MIN, END, LITERAL = 0xFA, 0xFE, 0xFF
ROLL_HEADER = 6 + 32
ROLL_WIDTH = 320

# --- container -----------------------------------------------------------------


def parse_container(data: bytes) -> list:
    (count,) = struct.unpack_from('>I', data, 0)
    out = []
    for i in range(count):
        off, size = struct.unpack_from('>II', data, 4 + 8 * i)
        out.append(data[off:off + size])
    return out


def pack_container(entries: list, align: int = 4) -> bytes:
    pad = lambda n: -n % align
    off = 4 + 8 * len(entries)
    off += pad(off)
    head, body = bytearray(struct.pack('>I', len(entries))), bytearray()
    for e in entries:
        head += struct.pack('>II', off + len(body), len(e))
        body += e + bytes(pad(len(e)))
    head += bytes(pad(len(head)))
    return bytes(head + body)

# --- decompressor --------------------------------------------------------------


def decompress(table: bytes, data: bytes, limit: int = 1 << 22) -> bytes:
    values = (0, data[0], data[1], data[2])
    dists = (data[3] & 15, data[3] >> 4, data[4] & 15, data[4] >> 4)
    pos, bits, left = 5, 0, 0
    last = [0] * 16
    out = bytearray()

    def emit(value, dist):
        if dist:
            value = (last[dist - 1] + value) & 0xFF
        last.insert(0, value)
        del last[16:]
        out.append(value)

    while len(out) < limit:
        node = 0
        while table[node + 1] < LEAF_MIN:
            if not left:
                bits, left = data[pos], 8
                pos += 1
            node += (table[node + (bits & 1)] + 1) * 2
            bits >>= 1
            left -= 1
        value, kind = table[node], table[node + 1]
        if kind == END:
            return bytes(out)
        if kind == LITERAL:
            emit(value, 0)
        else:
            k = kind - LEAF_MIN
            for _ in range(value + 1):
                emit(values[k], dists[k])
    raise ValueError('no end code within the limit')

# --- compressor ----------------------------------------------------------------
# Every entry uses one header: the four symbols write 0 in modes 0, 1, 2, 4
# (a run of zeros, or a repeat of the byte 1, 2 or 4 outputs back).

HEADER = bytes([0, 0, 0, 0x10, 0x42])
RUN_DISTS = (0, 1, 2, 4)
MAX_RUN = 256


def _parse(plain: bytes) -> list:
    syms, i, n = [], 0, len(plain)
    while i < n:
        best_len, best_k = 0, 0
        for k, d in enumerate(RUN_DISTS):
            j = i
            while j < n and j - i < MAX_RUN and plain[j] == (
                    (plain[j - d] if j >= d else 0) if d else 0):
                j += 1
            if j - i > best_len:
                best_len, best_k = j - i, k
        if best_len >= 2:
            syms.append(('run', best_k, best_len))
            i += best_len
        else:
            syms.append(('lit', plain[i]))
            i += 1
    syms.append(('end',))
    return syms


def _leaf(sym) -> bytes:
    if sym[0] == 'lit':
        return bytes([sym[1], LITERAL])
    if sym[0] == 'run':
        return bytes([sym[2] - 1, LEAF_MIN + sym[1]])
    return bytes([0, END])


def _inner(node) -> bool:
    return isinstance(node, tuple) and len(node) == 2 and isinstance(node[0], tuple)


def _tree(freq: dict):
    heap = [(f, i, s) for i, (s, f) in enumerate(sorted(freq.items()))]
    heapq.heapify(heap)
    count = len(heap)
    while len(heap) > 1:
        f1, _, a = heapq.heappop(heap)
        f2, _, b = heapq.heappop(heap)
        heapq.heappush(heap, (f1 + f2, count, (a, b)))
        count += 1
    return heap[0][2]


def _layout(root) -> tuple:
    """Breadth-first, as the JP tables: an inner node's children are adjacent,
    the pair at index c stored as bytes (c - i - 1, c - i)."""
    queue, table, codes, i = [(root, '')], bytearray(), {}, 0
    while i < len(queue):
        node, path = queue[i]
        if _inner(node):
            c = len(queue)
            if c - i >= LEAF_MIN:
                raise ValueError('Huffman tree too wide for the format')
            table += bytes([c - i - 1, c - i])
            queue += [(node[0], path + '0'), (node[1], path + '1')]
        else:
            table += _leaf(node)
            codes[node] = path
        i += 1
    return bytes(table), codes


def compress_group(plains: list) -> tuple:
    """(tree, [compressed entry, ...]) for entries that share one tree."""
    parsed = [_parse(p) for p in plains]
    freq = {}
    for syms in parsed:
        for s in syms:
            freq[s] = freq.get(s, 0) + 1
    table, codes = _layout(_tree(freq))
    blobs = []
    for syms in parsed:
        out, acc, nbits = bytearray(HEADER), 0, 0
        for s in syms:
            for bit in codes[s]:
                acc |= (bit == '1') << nbits
                nbits += 1
                if nbits == 8:
                    out.append(acc)
                    acc, nbits = 0, 0
        if nbits:
            out.append(acc)
        blobs.append(bytes(out))
    return table, blobs

# --- the English roll ----------------------------------------------------------


def apply_overlay(staff_dat: bytes, overlay_png: str, rects_json: str) -> bytes:
    """The player's STAFF.DAT with the English overlay pasted in."""
    table, roll_blob, font_blob = parse_container(staff_dat)
    roll = bytearray(decompress(table, roll_blob))
    font = decompress(table, font_blob)
    w, h, px = png_indexed.read_indexed_png(overlay_png)
    rects = json.loads(open(rects_json).read())
    height = (len(roll) - ROLL_HEADER) * 2 // ROLL_WIDTH
    if (w, h) != (ROLL_WIDTH, height):
        raise ValueError(f'overlay is {w}x{h}, the roll is {ROLL_WIDTH}x{height}')
    for x0, y0, x1, y1 in rects:
        for y in range(y0, y1):
            for x in range(x0, x1):
                i = ROLL_HEADER + (y * ROLL_WIDTH + x) // 2
                v = px[x, y] & 15
                roll[i] = (roll[i] & 0x0F) | (v << 4) if x % 2 == 0 else (roll[i] & 0xF0) | v
    new_table, blobs = compress_group([bytes(roll), font])
    return pack_container([new_table] + blobs)
