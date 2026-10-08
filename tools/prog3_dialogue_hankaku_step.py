"""tools/prog3_dialogue_hankaku_step.py — dialogue half-width (hankaku) step.

ONE owned byte patch over the **JP** `LANG/PROG_3.BIN` (load base 0x06052800).
v0.8 spike (branch font-hankaku-per-glyph): render scen dialogue / nameplates as
per-glyph half-width (8px) instead of 16px bigram tiles.

RE (Ghidra headless + an independent Fable session both converged, 2026-07-06):
the dialogue text path is the PROG_3 VDP1 grid family
    FUN_0607bf6c -> 0x0607D1C0 -> FUN_0607d168 -> FUN_0607cf80 -> FUN_0607d0b8 -> VDP1
(NOT the A0LANG renderer FUN_06016d94, which is the field-UI path). In the layout
FUN_0607cf80 the per-glyph grid X byte is `baseX + column*2` (baseX from table
0x0604EDF8/window; `column` = the per-row cursor the dispatcher FUN_0607d168 bumps
by 1 per char). The flush FUN_0607d224 expands it to the sprite X:
    pixelX = byteX * 8 + 10          (unit = 8px, confirmed)
Chain closed: FUN_0607cf80 writes byteX to 0x060883B8, FUN_0607d224 reads byteX from
the SAME 0x060883B8. So each column advances 2*8 = 16px = one 16x16 bigram tile.

The `column*2` is a single instruction:
    0x0607D018  333C  add r3,r3      ; r3 = column (set @0x0607D004 `mov r6,r3`),
                                     ; doubled here, used ONLY by the X compute
                                     ; @0x0607D038 `add r3,r1` (r1 = baseX), and
                                     ; reassigned @0x0607D044 `mov.l @r14,r3`.
NOPing the doubling makes r3 = column*1, so pixelX advances 1*8 = 8px/glyph =
hankaku dialogue. Combined with hankaku glyphs drawn in the LEFT 8px of the 16x16
tile (right half transparent / overdrawn by the next glyph, drawn left-to-right),
the whole dialogue line renders half-width. The NOP is safe: r3 is not read between
0x0607D018 and 0x0607D038 except by the X compute, and it is reassigned at
0x0607D044 before any other use.

CAVEAT: this is ALWAYS-8px on this shared path (dialogue + nameplates + vertical
menus all ride FUN_0607cf80) — fine while all EN prose is hankaku by spec. A later
mixed-width need (a menu wanting full-width) requires replacing the fixed `column*2`
with a per-glyph pixel-unit accumulator (+2 full / +1 half) keyed on the tile's
width class. See archive/docs/20260706_v08_hankaku_font_plan.md.

Patch site: file offset 0x0607D018 - 0x06052800 = 0x2A818.
"""

PROG3_DIALOGUE_HANKAKU_STEP = {
    "LANG/PROG_3.BIN": [
        (0x0002A818, b"\x00\x09"),   # add r3,r3 (333C, column*2/16px) -> nop (0009, column*1/8px)
    ],
}

# JP baseline bytes at the patch site — verified against the pristine JP PROG_3
# by tests/test_prog3_dialogue_hankaku_step.py before any build.
JP_BASELINE = {
    0x0002A818: b"\x33\x3c",   # SH-2 `add r3,r3`
}
