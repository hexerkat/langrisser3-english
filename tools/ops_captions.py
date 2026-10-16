"""tools/ops_captions.py: the opening's staff and cast captions in English.

LANG/OPS.DAT is a container of 3 groups; each group is a container whose
entry 0 is a Huffman tree (codec: tools/staff_roll.py) and the rest are
compressed. Group 0 holds the captions as two blocks of 4 bpp sprites, 40 px
high: block 1 the 14 staff captions, block 2 the 17 cast captions, each
block starting with an 8x8 dummy. Groups 1 and 2 are the portraits.

PROG_2 (the title program, base 0x06052800) plays the opening in
FUN_0605461c: it unpacks block 1 to LWRAM 0x00200000 and block 2 to
0x00209000 (OPS.DAT itself sits at 0x00212000), finds caption k at the sum
of w8 * h8 * 32 over the size-table entries before it, copies it alone to
VDP1 VRAM 0x25C18C00 and draws it at (x, 88). Tables, 4 bytes per entry
(w8, h8 / x, y), entry 0 the dummy:
  staff  sizes 0x060579F8, positions 0x060579BC, 15 entries
  cast   sizes 0x06057974, positions 0x0605792C, 18 entries

The English captions (assets/ops_captions, drawn by the separate
langrisser3-graphics-extractor repo) only change the widths. The build swaps
both blocks (the dummy comes from the player's disc), writes each new w8,
and moves each x by half the width change so the caption keeps its JP
center. Limits kept (tests/test_ops_captions.py): no caption above 200x40
(the largest JP one, its VRAM slot), each block within its JP size, and
OPS.DAT no larger than the JP file.
"""
from __future__ import annotations

import json
from pathlib import Path

import png_indexed
from staff_roll import compress_group, decompress, pack_container, parse_container

PROG2_PATH = 'LANG/PROG_2.BIN'
PROG2_BASE = 0x06052800
HEIGHT = 40
DUMMY = 32                      # bytes of the 8x8 entry 0 of each block

# (sizes table, positions table) per block, and the JP entries
# [(w8, h8, x), ...], entry 0 the dummy. Truth-locked against the disc.
TABLES = [(0x060579F8, 0x060579BC), (0x06057974, 0x0605792C)]
JP_TABLES = [
    [(1, 1, -100), (21, 5, 81), (14, 5, 104), (12, 5, 112), (12, 5, 112), (12, 5, 112),
     (12, 5, 112), (12, 5, 112), (18, 5, 88), (18, 5, 88), (13, 5, 108), (13, 5, 108),
     (18, 5, 88), (25, 5, 61), (14, 5, 104)],
    [(1, 1, 82), (11, 5, 42), (12, 5, 38), (14, 5, 30), (12, 5, 38), (14, 5, 30),
     (14, 5, 30), (14, 5, 30), (14, 5, 30), (12, 5, 38), (14, 5, 30), (12, 5, 38),
     (12, 5, 38), (12, 5, 38), (10, 5, 46), (12, 5, 38), (14, 5, 30), (14, 5, 30)],
]


def load(asset_dir: Path) -> tuple[list, list]:
    """(widths per block, sprite bytes per block) from the asset files."""
    meta = json.loads((asset_dir / 'ops_captions_en.json').read_text())
    blocks = []
    for b, widths in enumerate(meta['widths'], 1):
        _, _, px = png_indexed.read_indexed_png(str(asset_dir / f'ops_captions{b}_en.png'))
        sprites = []
        for i, w in enumerate(widths):
            vals = [px[x, HEIGHT * i + y] & 15 for y in range(HEIGHT) for x in range(w)]
            sprites.append(bytes((vals[k] << 4) | vals[k + 1] for k in range(0, len(vals), 2)))
        blocks.append(sprites)
    return meta['widths'], blocks


def prog2_edits(asset_dir: Path) -> dict:
    """{PROG_2: [(offset, byte)]}: each caption's w8 and its re-centered x."""
    widths, _ = load(asset_dir)
    edits = []
    for (sizes, xs), jp, block in zip(TABLES, JP_TABLES, widths):
        if len(block) != len(jp) - 1:
            raise ValueError(f'{len(block)} English captions for {len(jp) - 1} Japanese')
        for i, w in enumerate(block, 1):
            jw8, _, jx = jp[i]
            if w % 8 or (jw8 * 8 - w) % 2:
                raise ValueError(f'caption width {w} is not a multiple of 8')
            x = jx + (jw8 * 8 - w) // 2
            if not -128 <= x <= 127:
                raise ValueError(f'caption x {x} does not fit the table byte')
            edits.append((sizes - PROG2_BASE + 4 * i, bytes([w // 8])))
            edits.append((xs - PROG2_BASE + 4 * i, bytes([x & 0xFF])))
    return {PROG2_PATH: edits}


def apply(ops_dat: bytes, asset_dir: Path) -> bytes:
    """The player's OPS.DAT with both caption blocks in English."""
    _, sprites = load(asset_dir)
    top = parse_container(ops_dat)
    group = parse_container(top[0])
    jp_blocks = [decompress(group[0], blob) for blob in group[1:]]
    blocks = [jp[:DUMMY] + b''.join(block) for jp, block in zip(jp_blocks, sprites)]
    for jp, new in zip(jp_blocks, blocks):
        if len(new) > len(jp):
            raise ValueError(f'caption block grew: {len(jp)} -> {len(new)} bytes')
    tree, blobs = compress_group(blocks)
    out = pack_container([pack_container([tree] + blobs)] + top[1:])
    if len(out) > len(ops_dat):
        raise ValueError(f'OPS.DAT grew: {len(ops_dat)} -> {len(out)} bytes')
    return out
