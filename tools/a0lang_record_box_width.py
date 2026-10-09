"""tools/a0lang_record_box_width.py — width-class MEASURE for the A0LANG
single-record box (FUN_060127A0).

Owned byte patch over the **JP** `A0LANG.BIN` (load base 0x0600E000).

WHY (2026-10-08, archive/docs/20261008_hybrid_fntsys_surfaces_re.md):
FUN_060127A0 takes an fntsys1 record index, measures the record at a FIXED
2 cells per word and hands the count to FUN_06012AF4, the centred box builder
the location labels use (X = 18 - cells/2, W = cells + 4). With hybrid
FNT_SYS records an odd word tail is one 8px cell, so the JP count made the box
one cell too wide.

THE REWRITE (in place, 0x47C0..0x47D5, the JP loop's exact 11 words): the
pool long 0x4814 (JP 0x0000FFFF, the terminator constant) now holds the
address of the shared width-class cave (tools/width_class.py):

    47C0 D314  mov.l @(0x4814),r3  ; r3 = &is_narrow
  loop:
    47C2 6025  mov.w @r2+,r0       ; word (sign-extended)
    47C4 88FF  cmp/eq #-1,r0       ; terminator?
    47C6 8906  bt 0x47D6           ; -> untouched JP code (mov #0x23,r1 ...)
    47C8 430B  jsr @r3             ; is_narrow(r0) -> T, keeps r1-r14
    47CA 7501  add #1,r5           ; (delay) every word >= 1 cell
    47CC 89F9  bt loop
    47CE AFF8  bra loop
    47D0 7501  add #1,r5           ; (delay) wide: second cell
    47D2 0009  nop x2              ; pad to the region end

Safe because (verified on the JP bytes): the function saves PR at entry
(4F22 @0x47A2), no branch lands inside the region from outside, the pool long
0x4814 is read only by 0x47C0, and after the loop the JP code reads r5 (cells),
r4 (record index) and r6 (arg), all kept; r0-r3 are reloaded.

Guard: tests/test_a0lang_record_box_width.py (JP and patched bytes executed on
tools/sh2_mini with the real cave).
"""

from width_class import WIDTH_CAVE_ADDR

LOOP_OFF = 0x47C0
POOL_OFF = 0x4814

_NEW_LOOP = bytes.fromhex(
    "D314" "6025" "88FF" "8906" "430B" "7501" "89F9" "AFF8" "7501" "0009" "0009"
)
assert len(_NEW_LOOP) == 22

A0LANG_RECORD_BOX_WIDTH = {
    "A0LANG.BIN": [
        (LOOP_OFF, _NEW_LOOP),
        (POOL_OFF, WIDTH_CAVE_ADDR.to_bytes(4, "big")),
    ],
}

JP_BASELINE = {
    LOOP_OFF: bytes.fromhex(
        "D314" "A002" "6121" "6121" "7502" "611D" "3130" "8FFA" "7202" "72FE" "655D"
    ),
    POOL_OFF: bytes.fromhex("0000FFFF"),
}
