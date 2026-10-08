"""tools/prog3_balloon_hankaku_grid.py — 34-col hankaku balloon grid (v0.8 Piece B).

In-place byte patches over the **JP** `LANG/PROG_3.BIN` (load base 0x06052800)
that re-dimension the VDP1 dialogue-balloon grid for per-glyph 8px hankaku text.
Full RE reference: archive/docs/20260707_prog3_dialogue_balloon_pipeline_re.md
(render chain, buffers, pools; RE'd via Ghidra headless + Ymir dumps 2026-07-07).

WHAT / WHY
==========
The balloon renderer (FUN_0607ccac clear-all, FUN_0607cd58 newline/scroll
handler "fnA", FUN_0607cf3c scroll, FUN_0607cf80 layout, FUN_0607d168
dispatcher, FUN_0607d224 flush) draws a per-window grid of 17 cols x 5 rows:
window stride 0x55 = 17*5, row stride 0x11, one 16x16 4bpp texture (0x80 B)
per cell in VDP1 VRAM at 0x25C60000 + win*0x2A80 + cell*0x80. With the 8px
step NOP (tools/prog3_dialogue_hankaku_step.py) each column is 8px, so the
17-col grid fills only half the balloon. This module widens the grid to
**34 cols (narration) / 26 (dialogue)** — the SAME per-line char budgets as
the v0.7 bigram encoding (17/13 tiles x 2 chars each) and the same pixel
spans (34*8 = 17*16 = 272px; 26*8 = 13*16 = 208px), so the existing <$FFFC>
line breaks carry over unchanged.

Three coordinated groups of in-place changes (no code caves needed):

1. GRID GEOMETRY. Row stride immediates 0x11->0x22, col-clear loop bounds
   0x10->0x21, d168 line limits 17->34 (0x0607D192) / 13->26 (0x0607D1A0).

2. WINDOW STRIDE 0x55 -> 0x100. `mov #imm8` sign-extends, so a stride
   >= 0x80 (needs 5*0x22 = 0xAA) is not loadable as an immediate. Each of
   the 7 `mov #0x55,rK / ... / mul.l rK,rWIN / sts macl,rD` sequences is
   rewritten in place as `mov rWIN,rD / shll8 rD` (+ nop where the mov#
   itself is replaced): win<<8 = win*0x100. The window index is only ever
   0 or 1, and every rWIN register was verified live at each site (ccac r5,
   fnA-FFFC r4, fnA-char r3, cf3c r4, cf80 r10, flush-clear r3, flush-draw
   r12). The orphaned `mov #0x55` setup instructions become dead loads and
   are left in place (harmless, keeps the diff minimal).

3. 8PX-WIDE TEXTURES (0x40 B/cell). At 34 cols the old 16px-wide cells
   would need 0xAA*0x80 = 0x5500 per window, but VDP1 VRAM past the current
   2*0x2A80 window pair (0x65500+) is occupied (dump-verified). Hankaku
   glyphs only use the left 8px, so the rasterizer FUN_0607d0b8 is switched
   to emit 4 bytes/row (its middle loop counts pixels in r6 += 2 per output
   byte and exits past 0xF; bumping the increment to 4 exits after 4 bytes
   = the left 8px — the 0xF bound register is shared with the 16-row outer
   loop and must NOT change). Staging step, blit dest and flush CMDSRCA drop
   one doubling (cell<<7 -> cell<<6), the slot-byte recover shift drops
   >>7 -> >>6, the glyph copy length u16 0x80->0x40, and CMDSIZE u16
   0x210->0x110 (8px-wide, 16 tall sprites). Result: 0xAA cells * 0x40 =
   0x2A80 = EXACTLY the JP per-window VRAM stride — the VDP1 VRAM layout
   (0x25C60000, stride literals 0x2A80 at 0x0607D082/0x0607D490) is
   untouched. Staging use also halves (0xAA*0x40 = 0x2A80 <= the 0x4000
   ring at *0x0604F8A0 = 0x0600A000).

BUFFER RELOCATION (the pre-0.4 "full balloon" wall)
===================================================
The 4 per-cell grid buffers (1 B/cell: slot 0x06088308, X 0x060883B8,
Y 0x06088468, occupied-flag 0x06088528) are packed at 0xB0 = 2 windows x
0x55 + 6 in HWRAM; any widening overflows the next buffer. With the 0x100
window stride each needs 0x200 (2 windows), so they move to free LWRAM:

    slot 0x002A6000  X 0x002A6200  Y 0x002A6400  flag 0x002A6600

(inside the free block 0x002A57C8 + 0x2483B, zero in a dialogue-state Ymir
dump; CPU-only metadata, no DMA — same approach as the CN patch's LWRAM
font buffer). All 11 pool literals referencing the 4 buffers are repointed
(value-exact sweep over every game binary found no other reference). The
row cursor 0x06088518 (5 B/window), the per-window scalars 0x060885D8..F8
and the 0x20-byte VDP1 command template 0x060882E8 do not scale with
columns and STAY at their JP addresses.

COMPANIONS / CAVEATS
====================
- Requires tools/prog3_dialogue_hankaku_step.py (the 8px column step NOP).
- tools/prog3_balloon_zenkaku_dispatch.py adds the per-glyph width class on
  top: non-band tiles (kanji, bigram, zenkaku specials) draw as two adjacent
  8px cells = 16px, so unconverted content renders like v0.7 instead of
  garbled left-half-only. The three modules ship together.
- File offset = RAM - 0x06052800.
"""

_B = 0x06052800  # PROG_3 load base (RAM - _B = file offset)

# LWRAM homes of the 4 per-cell grid buffers (0x200 each = 2 windows x 0x100).
LWRAM_SLOT = 0x002A6000
LWRAM_X    = 0x002A6200
LWRAM_Y    = 0x002A6400
LWRAM_FLAG = 0x002A6600

# (file_offset, jp_bytes, new_bytes, comment) — SH-2 big-endian words / u16 / u32.
_SITES = [
    # -- col-clear loop bounds: mov #0x10 -> mov #0x21 (cmp/hi -> 34 iterations)
    (0x0607CCD2 - _B, b"\xEB\x10", b"\xEB\x21", "ccac col bound r11"),
    (0x0607CE36 - _B, b"\xEA\x10", b"\xEA\x21", "fnA FFFC-path col bound r10"),
    (0x0607CED8 - _B, b"\xEA\x10", b"\xEA\x21", "fnA char-path col bound r10"),
    (0x0607CF46 - _B, b"\xE9\x10", b"\xE9\x21", "cf3c scroll col bound r9"),
    (0x0607D292 - _B, b"\xEB\x10", b"\xEB\x21", "flush row-clear col bound r11"),
    # -- row stride 0x11 -> 0x22 (34-col rows)
    (0x0607CCE0 - _B, b"\xE4\x11", b"\xE4\x22", "ccac row stride r4"),
    (0x0607CE3C - _B, b"\xE5\x11", b"\xE5\x22", "fnA FFFC-path row stride r5"),
    (0x0607CEDE - _B, b"\xE4\x11", b"\xE4\x22", "fnA char-path row stride r4"),
    (0x0607CF70 - _B, b"\x73\x11", b"\x73\x22", "cf3c row advance add #,r3"),
    (0x0607CFB8 - _B, b"\xE1\x11", b"\xE1\x22", "cf80 row stride r1"),
    (0x0607D298 - _B, b"\xE8\x11", b"\xE8\x22", "flush row-clear stride r8"),
    (0x0607D44E - _B, b"\x7A\x11", b"\x7A\x22", "flush draw row advance add #,r10"),
    # -- d168 per-line char limits
    (0x0607D192 - _B, b"\xE3\x11", b"\xE3\x22", "narration line limit 17 -> 34"),
    (0x0607D1A0 - _B, b"\xE3\x0D", b"\xE3\x1A", "dialogue line limit 13 -> 26"),
    # -- window stride 0x55 -> 0x100 (win<<8; mov #imm8 can't load >= 0x80)
    (0x0607CCE4 - _B, b"\x05\xA7", b"\x61\x53", "ccac: mul.l r10,r5 -> mov r5,r1"),
    (0x0607CCE8 - _B, b"\x01\x1A", b"\x41\x18", "ccac: sts macl,r1 -> shll8 r1"),
    (0x0607CE60 - _B, b"\x04\x97", b"\x61\x43", "fnA FFFC: mul.l r9,r4 -> mov r4,r1"),
    (0x0607CE64 - _B, b"\x01\x1A", b"\x41\x18", "fnA FFFC: sts macl,r1 -> shll8 r1"),
    (0x0607CEE2 - _B, b"\x03\x97", b"\x61\x33", "fnA char: mul.l r9,r3 -> mov r3,r1"),
    (0x0607CEE6 - _B, b"\x01\x1A", b"\x41\x18", "fnA char: sts macl,r1 -> shll8 r1"),
    # cf3c is the ONE site whose inner loop re-enters BETWEEN the pair
    # (bf/s -> 0x0607CF54): a per-iteration shll8 there accumulated garbage
    # addresses after column 0 (playtest: "only the first column scrolls").
    # Fix: win<<8 precomputed ONCE in r4 (dead #0x55 slot, r4 already extu'd
    # at 0x0607CF48), r1 re-initialized fresh EACH inner iteration (base added
    # by the unchanged `add r6,r1` at 0x0607CF58).
    (0x0607CF4A - _B, b"\xE8\x55", b"\x44\x18", "cf3c: dead mov #0x55,r8 -> shll8 r4 (pre-loop win<<8)"),
    (0x0607CF52 - _B, b"\x04\x87", b"\x00\x09", "cf3c: mul.l r8,r4 -> nop"),
    (0x0607CF56 - _B, b"\x01\x1A", b"\x61\x43", "cf3c: sts macl,r1 -> mov r4,r1 (per-iteration)"),
    (0x0607CFAC - _B, b"\xE1\x55", b"\x6B\xA3", "cf80: mov #0x55,r1 -> mov r10,r11"),
    (0x0607CFAE - _B, b"\x0A\x17", b"\x4B\x18", "cf80: mul.l r1,r10 -> shll8 r11"),
    (0x0607CFB0 - _B, b"\x0B\x1A", b"\x00\x09", "cf80: sts macl,r11 -> nop"),
    (0x0607D2AC - _B, b"\x03\xA7", b"\x61\x33", "flush clear: mul.l r10,r3 -> mov r3,r1"),
    (0x0607D2B0 - _B, b"\x01\x1A", b"\x41\x18", "flush clear: sts macl,r1 -> shll8 r1"),
    (0x0607D3A2 - _B, b"\x0C\x17", b"\x67\xC3", "flush draw: mul.l r1,r12 -> mov r12,r7"),
    (0x0607D3A4 - _B, b"\x07\x1A", b"\x47\x18", "flush draw: sts macl,r7 -> shll8 r7"),
    # -- 8px-wide textures: cell step x0x80 -> x0x40
    (0x0607CFE0 - _B, b"\x31\x1C", b"\x00\x09", "cf80 staging slot<<7 -> <<6 (drop add r1,r1)"),
    (0x0607D000 - _B, b"\x32\x2C", b"\x00\x09", "cf80 blit dest cell<<7 -> <<6 (drop add r2,r2)"),
    (0x0607D012 - _B, b"\x42\x01", b"\x00\x09", "cf80 slot-byte recover >>7 -> >>6 (drop shlr)"),
    (0x0607D084 - _B, b"\x00\x80", b"\x00\x40", "cf80 glyph copy length u16"),
    (0x0607D128 - _B, b"\x76\x02", b"\x76\x04", "rasterizer: 4 bytes/row = left 8px"),
    (0x0607D3F8 - _B, b"\x31\x1C", b"\x00\x09", "flush CMDSRCA slot<<7 -> <<6 (drop add r1,r1)"),
    (0x0607D492 - _B, b"\x02\x10", b"\x01\x10", "CMDSIZE u16: 16x16 -> 8x16 sprites"),
    # -- relocate the 4 per-cell buffers to LWRAM (11 pool literals)
    (0x0607D09C - _B, (0x06088308).to_bytes(4, "big"), LWRAM_SLOT.to_bytes(4, "big"), "slot buf @cf80"),
    (0x0607D4CC - _B, (0x06088308).to_bytes(4, "big"), LWRAM_SLOT.to_bytes(4, "big"), "slot buf @flush"),
    (0x0607D0A0 - _B, (0x060883B8).to_bytes(4, "big"), LWRAM_X.to_bytes(4, "big"),    "X buf @cf80"),
    (0x0607D4D0 - _B, (0x060883B8).to_bytes(4, "big"), LWRAM_X.to_bytes(4, "big"),    "X buf @flush"),
    (0x0607CF7C - _B, (0x06088468).to_bytes(4, "big"), LWRAM_Y.to_bytes(4, "big"),    "Y buf @cf3c"),
    (0x0607D0A8 - _B, (0x06088468).to_bytes(4, "big"), LWRAM_Y.to_bytes(4, "big"),    "Y buf @cf80"),
    (0x0607D4D8 - _B, (0x06088468).to_bytes(4, "big"), LWRAM_Y.to_bytes(4, "big"),    "Y buf @flush"),
    (0x0607CD40 - _B, (0x06088528).to_bytes(4, "big"), LWRAM_FLAG.to_bytes(4, "big"), "flag buf @ccac"),
    (0x0607CF38 - _B, (0x06088528).to_bytes(4, "big"), LWRAM_FLAG.to_bytes(4, "big"), "flag buf @fnA"),
    (0x0607D088 - _B, (0x06088528).to_bytes(4, "big"), LWRAM_FLAG.to_bytes(4, "big"), "flag buf @cf80"),
    (0x0607D4A4 - _B, (0x06088528).to_bytes(4, "big"), LWRAM_FLAG.to_bytes(4, "big"), "flag buf @flush"),
]

PROG3_BALLOON_HANKAKU_GRID = {
    "LANG/PROG_3.BIN": [(off, new) for off, _jp, new, _c in _SITES],
}

# JP baseline bytes at every patch site — verified against the pristine JP
# PROG_3 by tests/test_prog3_balloon_hankaku_grid.py before any build.
JP_BASELINE = {off: jp for off, jp, _new, _c in _SITES}
