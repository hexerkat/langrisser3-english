"""Codec for LANG/TITLE.DG2 — the Saturn title-screen CG container.

Self-contained, RE-derived (2026-06-24, see archive/docs/
20260624_cn_credit_fun299c_decompile.md). The build writes the patch credit
line into the title's empty footer (apply_credit_line): the JP logo and sky
stay as they are, the line's tiles are appended to res0 and its colors go to
free palette slots.

## Container
Header = u32 count(=4), then `count` (offset:u32, size:u32) pairs (BE). Each
resource is raw/uncompressed:
  - res0 @0x24            8bpp 8x8 char tiles (sky clouds + logo glyphs); the game
                          loads this verbatim into VDP2 VRAM char base 0x0.
  - res1 (LOGO_RES_INDEX) the logo+sky pattern-name maps (16-bit-per-cell grids).
  - res2                  the "GAME OVER" CG tiles.
  - res3                  res2's map.

## Logo map cell format (cracked from PROG_3 FUN_06059dd0, the map expander)
res1 holds the logo plane as a row-major 16-bit grid, width GRID_W, starting at
byte GRID_BASE within res1. Per cell (BE16):
  bits 0-11  tile index into res0 (the expander emits VRAM charno = index*2)
  bits 12-13 palette bank (256 colors each)   bit 14  H flip   bit 15  V flip
  0x0000     empty cell (transparent)
The expander writes VRAM pattern name = high(0x40 + (cell>>8 & 0x30) + (cell &
0xC000)), low((cell & 0x0FFF) * 2). Rows 6..22 carry "LANGRISSER III / TEAM
PRESENTS / ©NCS 1996"; rows 23..27 (footer, px 184..224) are empty.
(Bits 12-15 proved 2026-10-13 against a Ymir dump: the title sky plane vs VDP2
VRAM 0x44000 and CRAM 0x500. Until then they were read as flips here.)

The palette (256 BGR555 colors per bank) is in res1 at PALETTE_RES1_OFFSET;
the logo uses bank 0 slots 0..8.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List

import json
from pathlib import Path

# --- container layout ---
HEADER_COUNT_OFF = 0
RES0_OFFSET = 0x24

# --- logo map within res1 ---
LOGO_RES_INDEX = 1
GRID_BASE = 0x508   # byte offset of grid row 0 within res1
GRID_W = 40         # cells per row
GRID_H = 28         # rows (covers the visible 320x224 = 40x28 cells)

CELL_TILE_MASK = 0x0FFF
CELL_BANK_SHIFT = 12
CELL_BANK_MASK = 0x3000
CELL_HFLIP = 0x4000
CELL_VFLIP = 0x8000

FOOTER_ROW_START = 23  # first empty footer row (px 184)

# --- title palette (256 BGR555 colors, embedded in res1's header) ---
# res1[PALETTE_RES1_OFFSET .. +512] is bank 0. The stock title uses slots 0..8;
# slots 16..31 are unused (black). The credit line's 15-step ramp, from its
# outline color to its fill color, goes to slots 17..31.
PALETTE_RES1_OFFSET = 0x108   # byte offset of color index 0 within res1
CREDIT_RAMP_BASE = 16

CREDIT_ATLAS = Path(__file__).resolve().parent.parent / 'data' / 'fonts' / 'title_credit_atlas.json'
CREDIT_LAST_ROW = GRID_H * 8 - 1      # the line's lowest pixel row (223)
CREDIT_MARGIN = 4


def _bgr555(r, g, b, msb=1):
    return (msb << 15) | ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


@dataclass
class Resource:
    offset: int
    size: int


@dataclass
class Container:
    raw: bytes
    resources: List[Resource]


def parse_container(data: bytes) -> Container:
    (count,) = struct.unpack_from(">I", data, HEADER_COUNT_OFF)
    res = []
    for i in range(count):
        off, size = struct.unpack_from(">II", data, 4 + i * 8)
        res.append(Resource(off, size))
    return Container(bytes(data), res)


def pack_container(cont: Container) -> bytes:
    """Reproduce the container bytes. Byte-identical when resources are unchanged
    and keep their offsets/sizes."""
    end = max(r.offset + r.size for r in cont.resources)
    out = bytearray(cont.raw[:end])
    struct.pack_into(">I", out, HEADER_COUNT_OFF, len(cont.resources))
    for i, r in enumerate(cont.resources):
        struct.pack_into(">II", out, 4 + i * 8, r.offset, r.size)
    return bytes(out)


class LogoGrid:
    """A GRID_W x GRID_H grid of raw 16-bit cells from res1. Stores raw values so
    decode->encode is exact (attr bits we don't model are preserved)."""

    def __init__(self, cells: List[int]):
        assert len(cells) == GRID_W * GRID_H
        self.cells = cells
        self.width = GRID_W
        self.height = GRID_H

    def _idx(self, row: int, col: int) -> int:
        return row * GRID_W + col

    def raw(self, row: int, col: int) -> int:
        return self.cells[self._idx(row, col)]

    def tile(self, row: int, col: int) -> int:
        return self.cells[self._idx(row, col)] & CELL_TILE_MASK

    def flips(self, row: int, col: int):
        c = self.cells[self._idx(row, col)]
        return bool(c & CELL_HFLIP), bool(c & CELL_VFLIP)

    def bank(self, row: int, col: int) -> int:
        return (self.cells[self._idx(row, col)] & CELL_BANK_MASK) >> CELL_BANK_SHIFT

    def set_tile(self, row: int, col: int, tile: int,
                 hflip: bool = False, vflip: bool = False, bank: int = 0) -> None:
        cell = (tile & CELL_TILE_MASK) | ((bank & 3) << CELL_BANK_SHIFT)
        if hflip:
            cell |= CELL_HFLIP
        if vflip:
            cell |= CELL_VFLIP
        self.cells[self._idx(row, col)] = cell

    def clear(self, row: int, col: int) -> None:
        self.cells[self._idx(row, col)] = 0


def decode_logo_grid(dg2: bytes) -> LogoGrid:
    cont = parse_container(dg2)
    res1_off = cont.resources[LOGO_RES_INDEX].offset
    base = res1_off + GRID_BASE
    cells = [
        struct.unpack_from(">H", dg2, base + i * 2)[0]
        for i in range(GRID_W * GRID_H)
    ]
    return LogoGrid(cells)


def encode_logo_grid(dg2: bytes, grid: LogoGrid) -> bytes:
    """Write the grid cells back into res1 in place (size-preserving) and repack.
    With an unmodified grid this returns `dg2` byte-for-byte."""
    out = bytearray(dg2)
    cont = parse_container(dg2)
    res1_off = cont.resources[LOGO_RES_INDEX].offset
    base = res1_off + GRID_BASE
    for i, cell in enumerate(grid.cells):
        struct.pack_into(">H", out, base + i * 2, cell)
    return pack_container(parse_container(bytes(out)))


def footer_cell_count(dg2: bytes, footer_rows=None) -> int:
    """Number of non-empty (drawn) cells in the footer rows of the logo map.
    Used as a build-time assertion that the mandatory credit is actually present."""
    if footer_rows is None:
        footer_rows = range(FOOTER_ROW_START, GRID_H)
    grid = decode_logo_grid(dg2)
    return sum(1 for r in footer_rows for c in range(GRID_W) if grid.tile(r, c))


def repack(blobs: List[bytes]) -> bytes:
    """Build a container from resource blobs (recomputing offsets). With the
    original blobs at their natural contiguous offsets this equals the input."""
    hdr = 4 + len(blobs) * 8
    out = bytearray(struct.pack(">I", len(blobs)))
    off = hdr
    offs = []
    for b in blobs:
        offs.append(off)
        off += len(b)
    for o, b in zip(offs, blobs):
        out += struct.pack(">II", o, len(b))
    for b in blobs:
        out += b
    return bytes(out)


# --- the credit line ---------------------------------------------------------


def _credit_atlas():
    return json.loads(CREDIT_ATLAS.read_text(encoding='utf-8'))


def credit_ramp(atlas=None) -> list:
    """The 15 ramp colors (BGR555) for levels 1..15, outline to fill."""
    atlas = atlas or _credit_atlas()
    lo, hi, n = atlas['outline'], atlas['fill'], atlas['levels']
    return [_bgr555(*(round(a + (b - a) * k / (n - 1)) for a, b in zip(lo, hi)))
            for k in range(n)]


def render_credit_line(text: str, atlas=None) -> dict:
    """{(x, y): level} of `text` on one line, centered in the 320 px screen,
    its lowest pixel on row CREDIT_LAST_ROW."""
    atlas = atlas or _credit_atlas()
    glyphs, ink, pen = atlas['glyphs'], {}, 0.0
    for ch in text:
        g = glyphs.get(ch)
        if g is None:
            raise ValueError(f'no glyph for {ch!r} in the credit atlas')
        if 'rows' in g:
            for dy, row in enumerate(g['rows']):
                for dx, c in enumerate(row):
                    v = int(c, 16)
                    if v:
                        k = (round(pen) + g['left'] + dx, g['top'] + dy)
                        ink[k] = max(ink.get(k, 0), v)
        pen += g['advance'] + atlas['tracking']
    if not ink:
        raise ValueError('empty credit line')
    x0 = min(x for x, _ in ink); x1 = max(x for x, _ in ink)
    y1 = max(y for _, y in ink)
    width = x1 - x0 + 1
    if width > GRID_W * 8 - 2 * CREDIT_MARGIN:
        raise ValueError(f'credit line is {width} px wide; the title fits {GRID_W * 8 - 2 * CREDIT_MARGIN}')
    dx, dy = (GRID_W * 8 - width) // 2 - x0, CREDIT_LAST_ROW - y1
    out = {(x + dx, y + dy): v for (x, y), v in ink.items()}
    if min(y for _, y in out) < FOOTER_ROW_START * 8:
        raise ValueError('credit line is taller than the footer')
    return out


def apply_credit_line(dg2: bytes, text: str) -> bytes:
    """The JP TITLE.DG2 with `text` written into the empty logo footer.

    Byte-safe: res0 is append-only (the sky map references cloud tiles by
    index), every logo cell above the footer and the sky map stay, res2/res3
    (GAME OVER) stay, and the palette only gains the ramp in slots 17..31."""
    atlas = _credit_atlas()
    ink = render_credit_line(text, atlas)
    cont = parse_container(dg2)
    res0 = dg2[RES0_OFFSET:RES0_OFFSET + cont.resources[0].size]
    tiles = [res0[i:i + 64] for i in range(0, len(res0), 64)]
    index = {t: i for i, t in enumerate(tiles)}
    grid = decode_logo_grid(dg2)
    for row in range(FOOTER_ROW_START, GRID_H):
        for col in range(GRID_W):
            blk = bytes(CREDIT_RAMP_BASE + ink[col * 8 + x, row * 8 + y]
                        if (col * 8 + x, row * 8 + y) in ink else 0
                        for y in range(8) for x in range(8))
            if not any(blk):
                continue
            if grid.tile(row, col):
                raise ValueError(f'footer cell {row},{col} is not empty in this TITLE.DG2')
            if blk not in index:
                index[blk] = len(tiles)
                tiles.append(blk)
            grid.set_tile(row, col, index[blk])
    res1 = bytearray(dg2[cont.resources[1].offset:cont.resources[1].offset + cont.resources[1].size])
    for i, cell in enumerate(grid.cells):
        struct.pack_into('>H', res1, GRID_BASE + i * 2, cell)
    for k, color in enumerate(credit_ramp(atlas), 1):
        struct.pack_into('>H', res1, PALETTE_RES1_OFFSET + (CREDIT_RAMP_BASE + k) * 2, color)
    res2 = dg2[cont.resources[2].offset:cont.resources[2].offset + cont.resources[2].size]
    res3 = dg2[cont.resources[3].offset:cont.resources[3].offset + cont.resources[3].size]
    return repack([b''.join(tiles), bytes(res1), res2, res3])


# --- preview rendering (optional; needs a CRAM palette + Pillow) ---
def render_logo_png(dg2: bytes, cram: bytes, out_path: str, scale: int = 1) -> None:
    """Render the logo layer to a transparent PNG using a VDP2 CRAM dump."""
    from PIL import Image

    cont = parse_container(dg2)
    res0 = dg2[RES0_OFFSET:RES0_OFFSET + cont.resources[0].size]
    pal = []
    for i in range(0, len(cram), 2):
        v = struct.unpack_from(">H", cram, i)[0]
        pal.append(((v & 0x1F) * 255 // 31,
                    ((v >> 5) & 0x1F) * 255 // 31,
                    ((v >> 10) & 0x1F) * 255 // 31))
    grid = decode_logo_grid(dg2)
    nt = len(res0) // 64
    im = Image.new("RGBA", (GRID_W * 8, GRID_H * 8), (0, 0, 0, 0))
    px = im.load()
    for row in range(GRID_H):
        for col in range(GRID_W):
            tile = grid.tile(row, col)
            if tile <= 0 or tile >= nt:
                continue
            hf, vf = grid.flips(row, col)
            b = tile * 64
            for y in range(8):
                for x in range(8):
                    idx = res0[b + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                    if idx == 0:
                        continue
                    px[col * 8 + x, row * 8 + y] = (*pal[idx], 255)
    if scale != 1:
        im = im.resize((GRID_W * 8 * scale, GRID_H * 8 * scale), Image.NEAREST)
    im.save(out_path)
