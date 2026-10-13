"""tools/prog4_name_trim_space.py — the name trim knows the 8px space.

PROG_4 FUN_06092348 (load 0x06092348) runs on END and when the name screen
resumes: it counts the name up to FFFF (cap 16, prog4_name_cap16) and turns
trailing blanks into FFFF, keeping index 0, and returns the length. JP only
trims tile 0 (the 16px blank). The EN space key types the band space
(font_tools.HANKAKU_TILE_MAP[' '], via the '_' keyboard cells), so a name
like "Diehärte  " was saved with its spaces (Ralf, 2026-10-13).

Owned bytes over the JP:
1. Prologue, file 0x9348: `mov.l r14,@-r15 ; mov r15,r14` (a frame pointer
   nothing reads) -> `mov.w SPACE,r5 ; nop`. r5 is free in the whole
   function. The epilogue that popped r14 is gone with it.
2. Trim, file 0x936C..0x939F (load 0x0609236C..), after the count loop
   (r3 = count, untouched JP at 0x934C..0x936A), rewritten:
     - while count > 1 and the last letter is tile 0 (JP) or the 8px space
       (new): write FFFF over it, count - 1;
     - a lone 8px space left at index 0 becomes tile 0, the JP blank, so
       END's non-empty scan (0x06091C1E, tile 0 only) refuses a name made
       of spaces (Ralf, 2026-10-13);
     - an empty name (BAK can delete every letter) returns 0 and writes
       nothing. JP read index 255 there and, if it held 0, filled the 255
       words after the name with FFFF (over the CD directory tables);
     - returns the count (extu.b), as JP.
   SPACE rides the JP padding word 0x0609239E. The name pointer stays in
   the JP pool word 0x060923A0 (name_buffer_home site).
   Same results as JP for every non-empty name without a band space.

Guard: tests/test_name_trim_space.py (executed on the real bytes: trailing
8px spaces and mixed blanks trimmed, inner spaces kept, a name of spaces
empty for END, the empty name safe, JP-identical otherwise).
"""
from a0lang_save_name_pack import _Asm
from font_tools import HANKAKU_TILE_MAP

PROLOGUE_OFF = 0x9348
TRIM_OFF = 0x936C
SPACE_OFF = 0x939E               # JP padding word before the pool
NAME_POOL_OFF = 0x93A0           # name_buffer_home site, not touched here


def _trim(a):
    a.labels['NAME'] = NAME_POOL_OFF - TRIM_OFF
    a.movl_pc(6, 'NAME')         # r6 = name
    a.w(0xE7FF)                  # mov #-1,r7       ; FFFF
    a.mark('LOOP')
    a.w(0xE001)                  # mov #1,r0
    a.w(0x3306)                  # cmp/hi r0,r3     ; count > 1
    a.bf('LAST')
    a.w(0x6033)                  # mov r3,r0
    a.w(0x300C)                  # add r0,r0
    a.w(0x70FE)                  # add #-2,r0       ; offset of the last letter
    a.w(0x016D)                  # mov.w @(r0,r6),r1
    a.w(0x2118)                  # tst r1,r1        ; tile 0 (JP)
    a.bt('TRIM')
    a.w(0x3150)                  # cmp/eq r5,r1     ; the 8px space
    a.bf('DONE')
    a.mark('TRIM')
    a.w(0x0675)                  # mov.w r7,@(r0,r6)
    a.bra('LOOP')
    a.w(0x73FF)                  # (delay) add #-1,r3
    a.mark('LAST')
    a.w(0x2338)                  # tst r3,r3        ; empty name: nothing to do
    a.bt('DONE')
    a.w(0x6161)                  # mov.w @r6,r1
    a.w(0x3150)                  # cmp/eq r5,r1     ; a lone 8px space
    a.bf('DONE')
    a.w(0xE100)                  # mov #0,r1
    a.w(0x2611)                  # mov.w r1,@r6     ; = the JP blank, END sees no name
    a.mark('DONE')
    a.w(0x000B)                  # rts
    a.w(0x603C)                  # (delay) extu.b r3,r0
    while a.here() < SPACE_OFF - TRIM_OFF:
        a.w(0x0009)
    a.word('SPACE', HANKAKU_TILE_MAP[' '])


def trim_blob() -> bytes:
    labels = {}
    _trim(_Asm(labels, False))
    second = _Asm(labels, True)
    _trim(second)
    blob = second.blob()
    assert TRIM_OFF + len(blob) == NAME_POOL_OFF, len(blob)
    return blob


_SPACE_DISP = (0x06089000 + SPACE_OFF - (0x06089000 + PROLOGUE_OFF + 4)) // 2

PROG4_NAME_TRIM_SPACE = {
    "LANG/PROG_4.BIN": [
        (PROLOGUE_OFF, bytes([0x95, _SPACE_DISP]) + bytes.fromhex("0009")),
        (TRIM_OFF, trim_blob()),
    ],
}

PROG4_NAME_TRIM_SPACE_JP_BASELINE = {
    PROLOGUE_OFF: bytes.fromhex("2fe66ef3"),
    TRIM_OFF: bytes.fromhex(
        "73ff613c21188d0ee7ffd60a311c6213326c6121611d21188f06613373ff613c"
        "21188ff3227161337101" "6fe36ef6000b601c" "0000"),
}
