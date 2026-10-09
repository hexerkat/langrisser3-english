"""tools/a0lang_centered_box_width.py — width-class MEASURE for the A0LANG
centred message box (FUN_06012c98).

Owned byte patch over the **JP** `A0LANG.BIN` (load base 0x0600E000).

WHY (2026-10-08, archive/docs/20261008_hybrid_fntsys_surfaces_re.md §3):
FUN_06012c98 measures an FFFF-terminated tile string at a FIXED 2 cells per
word, then builds a centred box descriptor (X = 18 - cells/2, W = cells + 4).
Callers: the LOAD/SAVE "record + number" box (FUN_06013d80), PROG_3
0x0605544A/0x06055536 and PROG_5 FUN_0608cb7c. With hybrid FNT_SYS records an
odd word tail is one 8px band cell, so the JP count made the box one cell too
wide and pushed the text half a cell left.

THE REWRITE (in place, 0x4CF2..0x4D09, 12 words, the JP loop's exact span):
the JP loads 0x0000FFFF into r7 from pool 0x4D68 at 0x4CE2 for its terminator
compare; that pool long now holds the address of the shared width-class cave
(tools/width_class.py), and the loop compares the terminator with an
immediate instead:

    4CF2 E300  mov #0,r3           ; cells
  loop:
    4CF4 6045  mov.w @r4+,r0       ; word (sign-extended)
    4CF6 88FF  cmp/eq #-1,r0       ; terminator?
    4CF8 8907  bt 0x4D0A           ; -> untouched JP code (extu.w r3,r2 ...)
    4CFA 470B  jsr @r7             ; is_narrow(r0) -> T, keeps r1-r14
    4CFC 7301  add #1,r3           ; (delay) every word >= 1 cell
    4CFE 89F9  bt loop             ; narrow: done with this word
    4D00 AFF8  bra loop
    4D02 7301  add #1,r3           ; (delay) wide: second cell
    4D04..4D08 0009 x3             ; pad to the region end

Safe because (verified on the JP bytes 2026-10-08): the function saves PR at
entry (4F22), no branch from anywhere in A0LANG lands inside 0x4CF2..0x4D09,
the pool long 0x4D68 is read only by the mov.l at 0x4CE2, and after the loop
the JP code reads only r3 (r0, r4, r7 are dead or reloaded).

Guard: tests/test_a0lang_centered_box_width.py runs the JP and patched bytes
on tools/sh2_mini with the real cave.
"""

from width_class import WIDTH_CAVE_ADDR

LOOP_OFF = 0x4CF2
POOL_OFF = 0x4D68

_NEW_LOOP = bytes.fromhex(
    "E300" "6045" "88FF" "8907" "470B" "7301" "89F9" "AFF8" "7301"
    "0009" "0009" "0009"
)
assert len(_NEW_LOOP) == 24

A0LANG_CENTERED_BOX_WIDTH = {
    "A0LANG.BIN": [
        (LOOP_OFF, _NEW_LOOP),
        (POOL_OFF, WIDTH_CAVE_ADDR.to_bytes(4, "big")),
    ],
}

JP_BASELINE = {
    LOOP_OFF: bytes.fromhex(
        "6141" "611D" "3170" "8D07" "E300" "6273"
        "7402" "6141" "611D" "3120" "8FFA" "7302"
    ),
    POOL_OFF: bytes.fromhex("0000FFFF"),
}
