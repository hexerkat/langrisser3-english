"""tools/a0lang_field_hankaku_step.py — width-class step for the A0LANG
FIELD-UI renderer (v0.8: location labels render hankaku, menus stay 16px).

Owned byte patch over the **JP** `A0LANG.BIN` (load base 0x0600E000).

WHY (branch font-hankaku-per-glyph, 2026-07-09..12): location labels
(`<$FFFF>`-terminated field strings) draw through the A0LANG VDP2 tilemap
renderer `FUN_06016d94` (file 0x8D94) — the FIELD-UI path shared with menus
and the number formatter, NOT the PROG_3 VDP1 balloon. That renderer steps a
FIXED 2 tilemap cells (16px) per glyph, so v0.8 hankaku label strings drew
with a blank 8px hole after every glyph. Ralf rejected the route-labels-back-
to-bigram scaffold (v0.8 kills bigram); the real fix is width-class stepping
IN THIS RENDERER, mirroring what PROG_3 Piece C already does for the balloon.

DECISION — RE-READ the tile string, no stash (2026-07-11, from the
sh-elf-objdump disasm): Phase 2 iterates a COUNT (r10) and never holds the
tile codes (Phase 1 consumed them via `mov.w @r9+,r4`). The width class lives
only in the tile string, and the string start is recoverable with ZERO scratch
RAM as `r9 - r10*2` — r9 (terminator ptr) and r10 (glyph count) both survive
Phase 1 into Phase 2 (callee-saved across the rasterizer jsr, proven by the
JP code itself relying on r9/r10 across it). A stash buffer would need "free"
RAM — the exact trap of the citizen-portrait staging-ring bug
(archive/docs/20260708_citizen_portrait_staging_ring_bug.md).

ENGINE (JP Phase 2, file 0x8E30..0x8EB8):
  r4 = base pattern name (4th arg + 0x100)   r5 = 0x5000 (attr)
  r7 = VDP2 tilemap ptr at (Y*64+X)*2        r6/r10 = glyph count
  Per glyph g it wrote pattern names 0x5000+base+g*4+{0,1} on the top row
  (2 cells, `add #2,r7` twice = 16px), then jumped `(64-count*2)*2` to the
  next tilemap row and wrote +{2,3} on the bottom row. The right sub-tiles
  {1,3} of a hankaku glyph are blank (art in the left 8px) = the visible hole.

THE REWRITE (in place, 0x8E58..0x8EB8, 49 words — no cave needed):
  ONE loop, walking the re-read tile string, writing BOTH rows per glyph
  (bottom ptr r11 = r7 + 0x80 = one 64-cell row below). Per glyph:
    write top-left (+0) and bottom-left (+2), step both ptrs 1 cell;
    if the tile is NOT in the hankaku band [1265..1419]: also write
    top-right (+1) / bottom-right (+3) and step 1 more cell (= JP 16px).
  Because both rows advance together, the width-blind `64 - count*2`
  inter-row jump is eliminated BY CONSTRUCTION — no row-width bookkeeping
  exists to get wrong. For all-wide strings (menus, kanji, stat digits) the
  cell writes and steps are exactly the JP ones — behavior-identical.
  Free regs in Phase 2 (verified in the disasm): r0, r8, r9, r11, r12, r13
  (r8/r9 are dead after Phase 1; r11-r13 dead until the exit code reloads
  them; the exit code at 0x8EBA is untouched and reads only r10/@(10,r14)).

  Width test (6 insns, 1 pool word): r0 = tile - 1265 (pool 0x04F1), then
  unsigned r0 > 154 -> wide. Tiles below the band wrap to huge -> wide. The
  narrow class [1265..1419] is the identical predicate PROG_3 Piece C uses
  (font_tools "hankaku class range [1265..1419]"; cave/nakaguro at 1420+
  deliberately test wide = zenkaku 16px).

  The pool constant lives in the function's own literal pool at 0x8EE6 — the
  mov.l-alignment PAD word (0x0000). Scanned: no mov.w pc-rel reaches it, no
  branch from anywhere in A0LANG.BIN targets inside 0x8E58..0x8EB8 (the one
  candidate, word 0xB27A @0x8986, is the low half of pool literal 0x0602B27A
  — data, not code), and no 32-bit literal points into the region.

Phase 1 is untouched: its `+4`/`0x300` accumulator is STAGING budget, not
pixels (Phase-0 FINDING 1) — a narrow glyph still occupies a full 0x80-byte
staging char, so `+4` stays correct, as does the `slot + count*4` return.

Guard: tests/test_a0lang_field_hankaku_step.py (JP baseline truth-lock +
patched-stream disasm lock + an SH-2 mini-interpreter that EXECUTES the
patched bytes against the reference render model).
"""

# ── Width class (must equal the renderer's test; single source of truth for
#    the Python model) ──────────────────────────────────────────────────────
NARROW_LO = 1265          # font_tools.HANKAKU_BASE
NARROW_HI = 1419          # band headroom top; 1420+ (cave/nakaguro) = wide
ATTR_BASE = 0x5000        # r5: VDP2 pattern-name attribute bits
SUBTILE_PER_GLYPH = 4     # pattern names per 16x16 staging char

# ── Patch site bookkeeping ──────────────────────────────────────────────────
A0LANG_LOAD_BASE = 0x0600E000
PHASE2_REWRITE_OFF = 0x8E58          # file offset of the rewritten stream
POOL_CONST_OFF = 0x8EE6              # pool pad word -> 0x04F1 (=1265)

# The rewritten Phase-2 stream (SH-2 big-endian, hand-assembled and locked by
# the disasm test). Addresses are load addresses (0x0600E000 + file offset).
#
#   8E58 4608  shll2 r6            ; r6 = count*4 (loop bound, as JP)
#   8E5A 6893  mov r9,r8           ; r9 = string terminator ptr (dead reg)
#   8E5C 61A3  mov r10,r1
#   8E5E 311C  add r1,r1           ; count*2
#   8E60 3818  sub r1,r8           ; r8 = string START (the RE-READ walker)
#   8E62 EB40  mov #0x40,r11
#   8E64 4B00  shll r11            ; 0x80 = 64 cells * 2 B = one tilemap row
#   8E66 3B7C  add r7,r11          ; r11 = bottom-row write ptr
#   8E68 E300  mov #0,r3           ; sub-tile index g*4
#   8E6A E100  mov #0,r1
#   8E6C 3162  cmp/hs r6,r1        ; count == 0 ?
#   8E6E 8924  bt 0x8EBA           ; -> untouched exit code
# loop:
#   8E70 6085  mov.w @r8+,r0       ; r0 = tile[g]  (THE re-read)
#   8E72 6243  mov r4,r2
#   8E74 323C  add r3,r2           ; base + g*4
#   8E76 6153  mov r5,r1
#   8E78 312C  add r2,r1           ; 0x5000+base+g*4 = top-left pn
#   8E7A 2711  mov.w r1,@r7        ; write top-left
#   8E7C 7102  add #2,r1           ; -> bottom-left pn (+2)
#   8E7E 2B11  mov.w r1,@r11       ; write bottom-left
#   8E80 7702  add #2,r7           ; both rows step 1 cell
#   8E82 7B02  add #2,r11
#   8E84 912F  mov.w @(0x2F,pc),r1 ; = 0x04F1 from pool 0x8EE6
#   8E86 3018  sub r1,r0           ; r0 = tile - 1265 (wraps huge if below)
#   8E88 E14D  mov #77,r1
#   8E8A 311C  add r1,r1           ; 154 = NARROW_HI - NARROW_LO
#   8E8C 3016  cmp/hi r1,r0        ; T = outside band -> wide
#   8E8E 8B07  bf 0x8EA0           ; narrow: skip the right-half writes
# wide:
#   8E90 6153  mov r5,r1
#   8E92 312C  add r2,r1           ; r2 still base+g*4
#   8E94 7101  add #1,r1           ; top-right pn (+1)
#   8E96 2711  mov.w r1,@r7
#   8E98 7102  add #2,r1           ; bottom-right pn (+3)
#   8E9A 2B11  mov.w r1,@r11
#   8E9C 7702  add #2,r7           ; second cell = the JP 16px step
#   8E9E 7B02  add #2,r11
# cont:
#   8EA0 7304  add #4,r3
#   8EA2 613D  extu.w r3,r1
#   8EA4 3162  cmp/hs r6,r1
#   8EA6 8BE3  bf 0x8E70           ; next glyph
#   8EA8 A007  bra 0x8EBA          ; -> untouched exit code
#   8EAA 0009  nop                 ; (delay)
#   8EAC-8EB8  7x 0009 nop         ; unreachable pad to the region end
_NEW_STREAM = bytes.fromhex(
    "4608" "6893" "61A3" "311C" "3818" "EB40" "4B00" "3B7C"
    "E300" "E100" "3162" "8924"
    "6085" "6243" "323C" "6153" "312C" "2711" "7102" "2B11"
    "7702" "7B02"
    "912F" "3018" "E14D" "311C" "3016" "8B07"
    "6153" "312C" "7101" "2711" "7102" "2B11" "7702" "7B02"
    "7304" "613D" "3162" "8BE3"
    "A007" "0009"
    "0009" "0009" "0009" "0009" "0009" "0009" "0009"
)
assert len(_NEW_STREAM) == 0x62      # 49 words: exactly fills 0x8E58..0x8EB9

A0LANG_FIELD_HANKAKU_STEP = {
    "A0LANG.BIN": [
        (PHASE2_REWRITE_OFF, _NEW_STREAM),
        (POOL_CONST_OFF, bytes.fromhex("04F1")),   # pool pad 0000 -> 1265
    ],
}

# JP baseline at both sites — truth-locked against the pristine JP disc by
# tests/test_a0lang_field_hankaku_step.py before any build.
A0LANG_FIELD_HANKAKU_STEP_JP_BASELINE = {
    PHASE2_REWRITE_OFF: bytes.fromhex(
        "e100" "4608" "3162" "8d0f" "e300"                       # top-loop head
        "6243" "323c" "6153" "312c" "2711" "7702" "7201"
        "6153" "312c" "2711" "7304" "613d" "3162" "8ff1" "7702"  # top loop
        "62a3" "322c" "e140" "3128" "311c" "371c"                # inter-row jump
        "e202" "61a3" "4108" "7102" "3212" "8d10" "e302" "6613"  # bottom head
        "6243" "323c" "6153" "312c" "2711" "7702" "7201"
        "6153" "312c" "2711" "7304" "613d" "3162" "8ff1" "7702"  # bottom loop
    ),
    POOL_CONST_OFF: bytes.fromhex("0000"),                       # alignment pad
}


# ── Python render model (the requirement the bytes implement) ───────────────
def is_narrow_tile(tile: int) -> bool:
    """Width class: True = hankaku band = 1 cell (8px); else 2 cells (16px)."""
    return NARROW_LO <= tile <= NARROW_HI


def simulate_field_row(tiles, base_pn: int, row: str, width_aware: bool):
    """Model one tilemap row of `FUN_06016d94` Phase 2: {cell_col: pattern_name}.

    row='top' -> sub-tiles {0,1}; row='bottom' -> {2,3}. width_aware=False
    models the JP binary (every glyph 2 cells); True models this patch.
    """
    sub_left = 0 if row == 'top' else 2
    col = 0
    out = {}
    for g, t in enumerate(tiles):
        pn_left = ATTR_BASE + base_pn + g * SUBTILE_PER_GLYPH + sub_left
        out[col] = pn_left
        if (not width_aware) or (not is_narrow_tile(t)):
            out[col + 1] = pn_left + 1
            col += 2
        else:
            col += 1
    return out


def field_row_cells(tiles, width_aware: bool) -> int:
    """Cells one row consumes (the JP inter-row jump assumed 2*len(tiles))."""
    if not width_aware:
        return 2 * len(tiles)
    return sum(1 if is_narrow_tile(t) else 2 for t in tiles)
