"""tools/a0lang_label_box_width.py — width-class MEASURE for the A0LANG
location-label box (v0.8: the yellow frame hugs hankaku text like JP).

Owned byte patch over the **JP** `A0LANG.BIN` (load base 0x0600E000).

WHY (branch font-hankaku-per-glyph, 2026-07-13/14): with the per-glyph step
fix (`a0lang_field_hankaku_step`) the label GLYPHS render 8px, but the box
around them stayed ~2x the text ("Church of Laffel", scen044). The Ymir
captures (EN /tmp/uidbg.log + JP /tmp/uidbg_jp.log + wram dump, 2026-07-14)
pinned the whole pipeline:

  `FUN_06012A98` (file 0x4A98) measures the `<$FFFF>`-terminated tile string
  at a FIXED 2 cells (16px) per word (`add #2,r5` @0x6012AAC), rejects the
  label above 35 cells, and `FUN_06012AF4` builds a STACK descriptor
  (0x060FFxxx — why RAM watching never found a width writer):
      box W = cells + 4,  box X = 18 - cells/2  (screen-centred)
  The grow (`FUN_06017C64`) clamps to that descriptor, so in JP the box HUGS
  the text: ラフェルの都・教会 (18 cells) -> W=22 @X=9, seen live in the JP
  tilemap dump (rows 14..17, cols 9..30). The EN hankaku label measured
  2*16=32 -> W=36 @X=2: the reported stretch. The fixed X=3/W=35 constants
  in PROG_3 `FUN_0607D618` belong to a DIFFERENT splash instance and are a
  red herring (identical in JP).

THE REWRITE (in place, 0x4A9E..0x4AB9, 14 words — no cave needed):
  Same loop, but each word adds its WIDTH CLASS instead of a fixed 2:
  narrow band [1265..1349] -> 1 cell, everything else (kanji, zenkaku,
  cave/nakaguro 1420+, control words like F600) -> 2 cells, exactly the
  predicate `a0lang_field_hankaku_step` put in the renderer — measurer and
  renderer count the SAME cells, so the box hugs by construction.
    - `mov.w @r2+,r0` + `cmp/eq #-1,r0` replaces the JP `mov.l 0xFFFF,r3`
      compare, freeing r3 AND the pool long at 0x4ADC.
    - r3 = 1265 (pool pad 0x4ADA), r7 = band size (freed pool word 0x4ADC),
      loaded once before the loop; r7/r3 are dead here in the JP code.
    - Wide test: r0 = tile - 1265; unsigned r0 > size -> wide. Sign-extended
      control words (0xF600 -> 0xFFFFF600) wrap huge -> wide, like JP.
    - The cap test at 0x4ABA (`mov #35,r1; cmp/hi r1,r5`) is untouched: the
      35-CELL screen-fit cap keeps its JP meaning. It used to mean ~16
      glyphs; with narrow glyphs it now admits labels up to ~31 hankaku
      chars (budget check FUN_060186B8 only shrinks — safe).
    - r4 (string ptr) and r6 (arg copy) reach the `jsr FUN_06012AF4`
      untouched, as in JP. r2 ends at terminator+2 instead of terminator;
      r2 is dead after the loop (verified in the disasm through 0x4AD8).
  Scanned: no branch from anywhere in A0LANG targets inside 0x4A9E..0x4AB8,
  and the pool long 0x4ADC was referenced only by the replaced `mov.l`.

Guard: tests/test_a0lang_label_box_width.py (JP baseline truth-lock +
patched-stream lock + an SH-2 mini-interpreter that EXECUTES the patched
bytes against the reference geometry model).
"""

from width_class import (
    NARROW_LO,
    NARROW_HI,
    WIDTH_CAVE_ADDR,
    is_narrow_tile,
)

# ── Engine geometry constants (FUN_06012A98 / FUN_06012AF4 disasm) ──────────
CAP_CELLS = 35      # reject threshold at 0x4ABA (kept byte-identical)
BOX_PAD = 4         # descriptor W = cells + 4 (0x6012B42: add #4)
CENTER = 18         # descriptor X = 18 - cells/2 (0x6012B80: mov #18)

# ── Patch site bookkeeping ──────────────────────────────────────────────────
A0LANG_LOAD_BASE = 0x0600E000
MEASURE_OFF = 0x4A9E             # file offset of the rewritten measure loop
POOL_LONG_OFF = 0x4ADC           # JP 0x0000FFFF -> width-class cave address

# The measure loop (2026-10-08: asks the shared width-class cave per word, so
# the label box, the centred box and the renderers share ONE rule, including
# the engine's 8px glue tile 43).
#
#   4A9E 6653  mov r5,r6           ; keep: arg copy for FUN_06012AF4
#   4AA0 E500  mov #0,r5           ; r5 = cells accumulator
#   4AA2 6243  mov r4,r2           ; r2 = walker (r4 stays = string start)
#   4AA4 D30D  mov.l @(0x4ADC),r3  ; r3 = &is_narrow (the JP 0xFFFF pool)
# loop:
#   4AA6 6025  mov.w @r2+,r0       ; word (sign-extended)
#   4AA8 88FF  cmp/eq #-1,r0       ; 0xFFFF terminator?
#   4AAA 8906  bt 0x4ABA           ; -> untouched cap test (mov #35,r1)
#   4AAC 430B  jsr @r3             ; is_narrow(r0) -> T, keeps r1-r14
#   4AAE 7501  add #1,r5           ; (delay) every word >= 1 cell
#   4AB0 89F9  bt loop             ; narrow: next word
#   4AB2 AFF8  bra loop
#   4AB4 7501  add #1,r5           ; (delay) wide: second cell
#   4AB6 0009  nop x2              ; pad to the region end
# FUN_06012A98 saves PR at entry (4F22 @0x4A9A), so the jsr is safe.
_NEW_STREAM = bytes.fromhex(
    "6653" "E500" "6243" "D30D"
    "6025" "88FF" "8906" "430B" "7501" "89F9" "AFF8" "7501" "0009" "0009"
)
assert len(_NEW_STREAM) == 0x1C      # 14 words: exactly fills 0x4A9E..0x4AB9

A0LANG_LABEL_BOX_WIDTH = {
    "A0LANG.BIN": [
        (MEASURE_OFF, _NEW_STREAM),
        (POOL_LONG_OFF, WIDTH_CAVE_ADDR.to_bytes(4, "big")),
    ],
}

# JP baseline at both sites — truth-locked against the pristine JP disc
# by tests/test_a0lang_label_box_width.py before any build.
A0LANG_LABEL_BOX_WIDTH_JP_BASELINE = {
    MEASURE_OFF: bytes.fromhex(
        "6653" "e500" "6243" "d30d"                 # prologue + r3=0xFFFF
        "a002" "6141"                               # bra loop-mid quirk
        "6121" "7502" "611d" "3130" "8ffa" "7202"   # the width-blind loop
        "72fe" "655d"                               # r2 fixup + extu
    ),
    POOL_LONG_OFF: bytes.fromhex("0000ffff"),       # the terminator constant
}


# ── Python geometry model (the requirement the bytes implement) ─────────────
def label_box_cells(tiles):
    """Tilemap cells the label text occupies = what the renderer draws."""
    return sum(1 if is_narrow_tile(t) else 2 for t in tiles)


def label_box_geometry(tiles):
    """(accepted, box_x, box_w) the player sees, mirroring the engine:
    reject above CAP_CELLS, else centre a cells+BOX_PAD box on the 40-cell
    screen (FUN_06012AF4 stack-descriptor math)."""
    cells = label_box_cells(tiles)
    if cells > CAP_CELLS:
        return (False, None, None)
    return (True, CENTER - (cells >> 1), cells + BOX_PAD)
