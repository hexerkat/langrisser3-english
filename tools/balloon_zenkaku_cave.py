"""tools/balloon_zenkaku_cave.py — width-class draw dispatcher (v0.8 mixed steps).

SH-2 code cave that gives the PROG_3 balloon renderer PER-GLYPH width classes:
hankaku band tiles step 1 column (8px), EVERY other tile (kanji/kana, bigram,
zenkaku specials, the 16px ellipsis 906, full-width space 0) steps 2 columns
(16px) and renders full-width. This is the piece that lets zenkaku render
inside hankaku prose — and it makes ALL not-yet-converted content (bigram
dialogue, nameplates, vertical menus) render exactly like v0.7 again, so the
hankaku conversion becomes incremental instead of all-at-once.

HOW (zero code bytes patched in PROG_3 — one DATA literal):
The per-char dispatcher FUN_0607d168 calls the layout fn FUN_0607cf80 through
a POOL POINTER (0x0607D220, the only 0x0607CF80 reference in any game binary).
tools/prog3_balloon_zenkaku_dispatch.py repoints it to this cave. The cave:

  1. tile in the hankaku band [HANKAKU_LO..HANKAKU_HI] -> tail-jump to the real cf80
     (8px cell, exactly as before).
  2. any other tile -> draw it as TWO adjacent 8px cells:
       a. build a SCRATCH GLYPH = the glyph's rows shifted left 8px
          (`row_word << 8`), stored in font tile 1340's slot;
       b. call cf80(win, &tile,        col,   row)  -> left  half, cell N
       c. call cf80(win, &scratch_tile,col+1, row)  -> right half, cell N+1
       (cf80 + the 8px-wide rasterizer of prog3_balloon_hankaku_grid emit the
        LEFT 8px of any 16px glyph — so the shifted copy IS the right half,
        with the drop-shadow preprocessing applied to the shifted rows too.)
       d. rowcur[win*5 + row%5] += 1. FUN_0607d168 increments the SAME memory
          byte (read-modify-write) after the call returns, so the cursor
          advances 2 columns total = 16px. Line limits (34/26) then charge
          zenkaku 2 units — a pure-zenkaku JP line gets 17 glyphs = the JP
          budget, a bigram line gets 17 tiles = the v0.7 budget.

WHY a cave in FONT.BIN: PROG_3 has no reachable free code bytes (bra ±4KB,
pc-rel pools full), but FONT.BIN loads at LWRAM 0x00288000 and the
tiles at 1420+ are unused (the hankaku band, its headroom and the v4 twin
band end at 1416; the _VD_SPACE bigrams start at 1435, NEW_FONT_TILES=1691). The cave rides the font: resident whenever any
text can render, fixed address, delivered by the normal build. Tile 1340 is
the runtime scratch glyph (stays zero in the file); code occupies 1341-1345.

Register contract (verified in the d168/cf80 disassembly, RE doc §2):
entry r4=win r5=&tile r6=column r7=row_raw; r0-r3 scratch; r8/r9 callee-saved
(d168 keeps its rowcur base/row in r8/r9 across the call — preserved here).
SH-2 `mov.w @r5` sign-extends: drawable tiles are < 0x8000, control codes
never reach the draw dispatcher (consumed upstream by FUN_0607cd58).
"""

FONT_LWRAM_BASE = 0x00288000     # FONT.BIN load address (glyph src, RE-pinned)
SCRATCH_TILE = 1420              # runtime scratch glyph slot (zero in the file)
CAVE_TILE = 1421                 # cave code starts at this tile
CAVE_TILES = 5                   # tiles 1421-1425 reserved for the cave
CAVE_ADDR = FONT_LWRAM_BASE + CAVE_TILE * 32
SCRATCH_GLYPH_ADDR = FONT_LWRAM_BASE + SCRATCH_TILE * 32

CF80_ADDR = 0x0607CF80           # the real layout fn (JP pool value we replace)
ROWCUR_ADDR = 0x06088518         # per-row column cursor, 5 B/window (unmoved)
# Width-class bounds: [HANKAKU_LO..HANKAKU_HI] steps 8px, everything else is
# zenkaku (2 cells). HI = 1349 leaves band GROWTH headroom (content ends at
# 1344) without a cave rebuild; the v4 name-entry TWIN band (1350..1416) and
# the cave itself (1420+) sit above the class range, below the _VD_SPACE
# bigrams at 1435. Shrunk from 1419 on 2026-07-15 so the twins render 16px.
from width_class import NARROW_LO as HANKAKU_LO   # the ONE rule (2026-10-08):
from width_class import NARROW_HI as HANKAKU_HI   # band + the glue space 43
from width_class import NARROW_GLUE_TILE


def _assemble(resolve, labels):
    out = []

    def here():
        return len(out) * 2

    def w(x):
        out.append(x & 0xFFFF)

    def mark(name):
        labels[name] = here()

    def movw_pc(rn, lbl):        # mov.w @(disp,PC),Rn
        d = 0
        if resolve:
            d = (labels[lbl] - (here() + 4)) // 2
            assert 0 <= d < 256, (lbl, d)
        w(0x9000 | rn << 8 | d)

    def movl_pc(rn, lbl):        # mov.l @(disp,PC),Rn
        d = 0
        if resolve:
            d = (labels[lbl] - ((here() & ~3) + 4)) // 4
            assert 0 <= d < 256, (lbl, d)
        w(0xD000 | rn << 8 | d)

    def bf(lbl):                 # branch if T==0
        d = 0
        if resolve:
            d = (labels[lbl] - (here() + 4)) // 2
            assert -128 <= d < 128, (lbl, d)
        w(0x8B00 | (d & 0xFF))

    def bt(lbl):                 # branch if T==1
        d = 0
        if resolve:
            d = (labels[lbl] - (here() + 4)) // 2
            assert -128 <= d < 128, (lbl, d)
        w(0x8900 | (d & 0xFF))

    def bra(lbl):
        d = 0
        if resolve:
            d = (labels[lbl] - (here() + 4)) // 2
            assert -2048 <= d < 2048, (lbl, d)
        w(0xA000 | (d & 0xFFF))

    # ---- class test -------------------------------------------------------
    w(0x6051)                    # mov.w @r5,r0        ; tile code
    w(0x8800 | NARROW_GLUE_TILE)  # cmp/eq #43,r0       ; engine 8px glue space
    bt('hk')
    movw_pc(1, 'BAND_LO')        # mov.w #1265,r1
    w(0x3013)                    # cmp/ge r1,r0        ; T = tile >= 1265
    bf('zk')
    movw_pc(1, 'BAND_HI')        # mov.w #HANKAKU_HI,r1
    w(0x3017)                    # cmp/gt r1,r0        ; T = tile > HI
    bt('zk')
    mark('hk')
    movl_pc(1, 'CF80')           # hankaku: tail-jump the real cf80
    w(0x412B)                    # jmp @r1
    w(0x0009)                    # (delay) nop
    # ---- zenkaku: two 8px cells --------------------------------------------
    mark('zk')
    w(0x4F22)                    # sts.l pr,@-r15
    w(0x2F86)                    # mov.l r8,@-r15
    w(0x2F96)                    # mov.l r9,@-r15
    w(0x6843)                    # mov r4,r8           ; win  (survives cf80)
    w(0x6973)                    # mov r7,r9           ; row_raw
    w(0x2F66)                    # mov.l r6,@-r15      ; save column
    # scratch glyph = each 1bpp row << 8 (right half -> left half)
    w(0x6051)                    # mov.w @r5,r0        ; tile
    w(0x4008)                    # shll2 r0
    w(0x4008)                    # shll2 r0
    w(0x4000)                    # shll r0             ; tile*0x20
    movl_pc(1, 'FONTBASE')
    w(0x301C)                    # add r1,r0           ; glyph src
    movl_pc(2, 'SCRATCHG')
    w(0xE310)                    # mov #16,r3          ; 16 rows
    mark('row')
    w(0x6105)                    # mov.w @r0+,r1
    w(0x4118)                    # shll8 r1
    w(0x2211)                    # mov.w r1,@r2
    w(0x7202)                    # add #2,r2
    w(0x4310)                    # dt r3
    bf('row')
    # left half: cf80(win,&tile,col,row) — r4-r7 still the entry args
    movl_pc(1, 'CF80')
    w(0x410B)                    # jsr @r1
    w(0x0009)                    # (delay) nop
    # right half: cf80(win,&scratch_tile,col+1,row)
    w(0x66F6)                    # mov.l @r15+,r6      ; column
    w(0x7601)                    # add #1,r6
    w(0x6483)                    # mov r8,r4           ; win
    w(0x6793)                    # mov r9,r7           ; row_raw
    movl_pc(5, 'SCRATCH_TP')     # r5 = &scratch_tile_number
    movl_pc(1, 'CF80')
    w(0x410B)                    # jsr @r1
    w(0x0009)                    # (delay) nop
    # rowcur[win*5 + row%5] += 1  (d168 adds the other +1 after we return)
    w(0x6193)                    # mov r9,r1           ; row_raw
    w(0xE204)                    # mov #4,r2
    mark('m5')
    w(0x3126)                    # cmp/hi r2,r1        ; T = r1 > 4
    bf('m5done')
    w(0x71FB)                    # add #-5,r1
    bra('m5')
    w(0x0009)                    # (delay) nop
    mark('m5done')
    w(0x6083)                    # mov r8,r0
    w(0x4008)                    # shll2 r0
    w(0x308C)                    # add r8,r0           ; win*5
    w(0x301C)                    # add r1,r0           ; + row
    movl_pc(2, 'ROWCUR')
    w(0x012C)                    # mov.b @(r0,r2),r1
    w(0x7101)                    # add #1,r1
    w(0x0214)                    # mov.b r1,@(r0,r2)
    w(0x69F6)                    # mov.l @r15+,r9
    w(0x68F6)                    # mov.l @r15+,r8
    w(0x4F26)                    # lds.l @r15+,pr
    w(0x000B)                    # rts
    w(0x0009)                    # (delay) nop
    # ---- literal pool -------------------------------------------------------
    while here() % 4:
        w(0x0009)
    mark('CF80')
    w(CF80_ADDR >> 16); w(CF80_ADDR)
    mark('FONTBASE')
    w(FONT_LWRAM_BASE >> 16); w(FONT_LWRAM_BASE)
    mark('SCRATCHG')
    w(SCRATCH_GLYPH_ADDR >> 16); w(SCRATCH_GLYPH_ADDR)
    mark('SCRATCH_TP')
    tp = CAVE_ADDR + labels.get('SCRATCH_NO', 0)
    w(tp >> 16); w(tp)
    mark('ROWCUR')
    w(ROWCUR_ADDR >> 16); w(ROWCUR_ADDR)
    mark('BAND_LO')
    w(HANKAKU_LO)
    mark('BAND_HI')
    w(HANKAKU_HI)
    mark('SCRATCH_NO')
    w(SCRATCH_TILE)
    return b''.join(x.to_bytes(2, 'big') for x in out)


def cave_blob():
    """The assembled cave (two passes: label discovery, then resolution)."""
    labels = {}
    _assemble(False, labels)
    blob = _assemble(True, labels)
    assert len(blob) <= CAVE_TILES * 32, len(blob)
    return blob


# Encoding spot-checks against opcodes seen in the PROG_3 disassembly.
assert (0x6153).to_bytes(2, 'big')  # mov r5,r1 (format used by the grid module)
_b = cave_blob()
assert _b[:2] == b"\x60\x51"        # mov.w @r5,r0
assert _b.count(b"\x41\x0b") == 2   # exactly two jsr @r1 (left + right half)
assert _b.count(b"\x41\x2b") == 1   # one tail jmp @r1 (hankaku fast path)
del _b
