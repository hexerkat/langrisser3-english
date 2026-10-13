"""tools/width_class.py — the ONE glyph width-class rule (v0.8 hybrid).

Every text surface steps a glyph by its class: NARROW = one 8px cell, anything
else = two cells (16px). Narrow is:

  - the hankaku band [NARROW_LO..NARROW_HI] (8px letters/punct for odd tails);
  - NARROW_GLUE_TILE (43), a blank. The engine writes some glue tiles with an
    8-bit `mov #imm` (sign-extended, <= 0x7F), which can never reach the band,
    so this one low tile is the 8px space the engine can write itself
    (e.g. the separator before a number in the PROG_3 event messages).

Consumers that must agree: the PROG_3 balloon dispatcher (balloon_zenkaku_cave,
inline test), the A0LANG field renderer step (a0lang_field_hankaku_step,
inline test) and the two A0LANG box measurers, which call the font cave below.

The cave rides FONT.BIN (LWRAM 0x00288000, resident whenever text can render),
like the balloon and D00 caves.

    is_narrow:   in  r0 = tile (sign-extended word)
                 out T  = 1 narrow / 0 wide
                 clobbers r0 only (r1 is saved on the stack)
"""

FONT_LWRAM_BASE = 0x00288000

NARROW_LO = 1265          # font_tools.HANKAKU_BASE
NARROW_HI = 1349          # declared band top (content ends 1344)
NARROW_GLUE_TILE = 43     # blank, mov-#imm reachable 8px space

WIDTH_CAVE_TILE = 1469    # font_tools.CAVE_BLOCK (1431 until 2026-10-12)
WIDTH_CAVE_TILES = 1
WIDTH_CAVE_ADDR = FONT_LWRAM_BASE + WIDTH_CAVE_TILE * 32


def is_narrow_tile(tile: int) -> bool:
    return tile == NARROW_GLUE_TILE or NARROW_LO <= tile <= NARROW_HI


def cells(tiles) -> int:
    """8px cells a tile string occupies (control words count wide, as JP)."""
    return sum(1 if is_narrow_tile(t) else 2 for t in tiles)


#   00 882B  cmp/eq #43,r0
#   02 8906  bt   yes (0x12)
#   04 2F16  mov.l r1,@-r15
#   06 9106  mov.w @(LO),r1        ; 1265
#   08 3018  sub   r1,r0           ; tile - 1265 (wraps huge below the band)
#   0A 9105  mov.w @(SIZE),r1      ; band size + 1
#   0C 3106  cmp/hi r0,r1          ; T = size+1 > r0  -> narrow
#   0E 000B  rts
#   10 61F6  mov.l @r15+,r1        ; (delay) restore r1
#   12 000B  yes: rts              ; T = 1 from cmp/eq
#   14 0009  nop
#   16 LO    0x04F1
#   18 SIZE  0x0055
def cave_blob() -> bytes:
    words = [
        0x8800 | NARROW_GLUE_TILE, 0x8906, 0x2F16, 0x9106, 0x3018,
        0x9105, 0x3106, 0x000B, 0x61F6, 0x000B, 0x0009,
        NARROW_LO, NARROW_HI - NARROW_LO + 1,
    ]
    blob = b''.join(w.to_bytes(2, 'big') for w in words)
    assert len(blob) <= WIDTH_CAVE_TILES * 32
    return blob
