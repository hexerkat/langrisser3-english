"""tools/prog5_orientation_toggle_refresh.py: the Unit Orientation toggle redraws.

Owned byte patch over the **JP** `LANG/PROG_5.BIN` (load base 0x06089000).

WHY (user playtest 2026-10-18, RE 2026-10-23): in the battle menu "Unit
Orientation" (fntsys1 rec 21) the two options rec 160 "Allies" and rec 156
"Enemies" broke apart when the cursor moved: "Enemie" / "s Allie".
PROG_5 FUN_0608e5c4 case 2 (the toggle) SWAPS the two texts between the text
nodes 0x060926C0 (X 2) and 0x060926D0 (X 13), restores the background
(A0LANG 0x06018240) and redraws the group 0x06092710 (A0LANG 0x06017EF8).
The redraw writes the new tilemap into the RAM buffer (0x0604EE94 ->
0x0604F8B0) and sends the new glyphs to VDP2, but nothing copies the RAM
tilemap to VDP2: that is A0LANG FUN_060186e8, which every other PROG_5
redraw calls right after 0x06017EF8 (0x0608E392 -> 0x0608E39A, 0x0608E9A2 ->
0x0608E9B6). JP never showed it: both options are 4 equal kanji, so the old
tilemap shape still fits. EN "Allies" = 3 wide glyphs, "Enemies" = 3 wide +
1 narrow, so the old shape cut "Enemies" after 3 glyphs and drew "Allies"
in the "Enemies" shape. Proof: Ymir dump ymir-dumps/facing-menu/split, VDP2
tilemap row 10 old shape, RAM buffer row 10 new shape.

THE REWRITE (in place, file 0x56F0..0x5756, the end of case 2):
  1. The order bytes (0x06092ADC: [1,2] when the flag 0x060396E3 is zero,
     else [2,1]) were picked with two branches and 16 words. Now 11 words,
     no branch: T = (flag == 0); r2 = 2 - T; byte0 = r2; byte1 = 3 - r2.
  2. The node text writes (JP 0x0608E710..0x0608E74B) move up 10 bytes
     unchanged; their PC-relative loads are re-encoded to the SAME literals.
  3. After the redraw call, `mov.l @(pc),r1 ; jsr @r1 ; nop` calls
     0x060186E8. The literal is borrowed from the neighbour pool of
     FUN_0608e81c at 0x0608E9FC (676 bytes ahead, in mov.l range); the guard
     test locks it.
  4. `bra 0x0608E7F4 ; mov r14,r15` (the JP exit) as before, then nop pad.
Registers: r0 is now T after step 1; JP sets r0 (mov r6,r0) before reading
it, and r1/r2 are rewritten before use, as in JP.

Guard: tests/test_prog5_orientation_toggle_refresh.py (built and JP bytes
on tools/sh2_mini: the copy follows the redraw; order, texts, flag, return
value and every other call equal JP for flag 0, 1, 0xFF).
"""
PROG5_BASE = 0x06089000
START = 0x0608E6F0               # first replaced instruction (order pick)
END = 0x0608E756                 # literal pool of FUN_0608e5c4 starts here
JP_MOVED = (0x0608E710, 0x0608E74C)   # node text writes, moved up as is
ORDER_LIT = 0x0608E77C           # pool: 0x06092ADC
REDRAW_LIT = 0x0608E7B4          # pool: 0x06017EF8
TILEMAP_LIT = 0x0608E9FC         # pool of FUN_0608e81c: 0x060186E8
EXIT = 0x0608E7F4                # JP epilogue after `mov r14,r15`
TILEMAP_TO_VDP2 = 0x060186E8

# JP bytes of 0x0608E6F0..0x0608E755 (file 0x56F0..0x5755), truth-locked by
# the guard test against the JP disc.
JP_BASELINE = bytes.fromhex(
    "6180611c21188d05e202d12021207101"
    "a005e201d11de20121207101e2022120"
    "d517d31ad7176234d1146612d4196772"
    "622c4208420891176063011d325c611d"
    "311c317c12136230910f011d622c4208"
    "4208325c611d311c317c1213d119410b"
    "e501a04f6fe3"
)


def _off(addr):
    return addr - PROG5_BASE


def _movl_pc(rn, at, target):
    disp = target - ((at + 4) & ~3)
    assert disp % 4 == 0 and 0 <= disp // 4 <= 0xFF, hex(at)
    return 0xD000 | rn << 8 | disp // 4


def _movw_pc(rn, at, target):
    disp = target - (at + 4)
    assert disp % 2 == 0 and 0 <= disp // 2 <= 0xFF, hex(at)
    return 0x9000 | rn << 8 | disp // 2


def _bra(at, target):
    disp = (target - (at + 4)) // 2
    assert -0x800 <= disp < 0x800
    return 0xA000 | disp & 0xFFF


def _jp_word(addr):
    o = addr - START
    return int.from_bytes(JP_BASELINE[o:o + 2], "big")


def _relocate(word, old_at, new_at):
    """Re-encode a moved instruction so it reads the same literal."""
    rn = (word >> 8) & 0xF
    if word >> 12 == 0xD:
        target = ((old_at + 4) & ~3) + (word & 0xFF) * 4
        return _movl_pc(rn, new_at, target)
    if word >> 12 == 0x9:
        target = old_at + 4 + (word & 0xFF) * 2
        return _movw_pc(rn, new_at, target)
    assert word >> 12 not in (0x8, 0xA, 0xB, 0xC), f"branch at {old_at:#x}"
    return word


def rewrite():
    words = []

    def at():
        return START + 2 * len(words)

    words += [0x6180,            # mov.b @r8,r1      flag
              0x2118,            # tst r1,r1
              0x0029,            # movt r0           T = (flag == 0)
              0xE202,            # mov #2,r2
              0x3208]            # sub r0,r2         r2 = 1 or 2
    words.append(_movl_pc(1, at(), ORDER_LIT))
    words += [0x2120,            # mov.b r2,@r1      order[0]
              0x622B,            # neg r2,r2
              0x7203,            # add #3,r2         3 - r2
              0x7101,            # add #1,r1
              0x2120]            # mov.b r2,@r1      order[1]
    for old in range(*JP_MOVED, 2):
        words.append(_relocate(_jp_word(old), old, at()))
    words.append(_movl_pc(1, at(), REDRAW_LIT))
    words += [0x410B, 0xE501]    # jsr @r1 ; mov #1,r5   redraw(group, 1)
    words.append(_movl_pc(1, at(), TILEMAP_LIT))
    words += [0x410B, 0x0009]    # jsr @r1 ; nop         tilemap -> VDP2
    words.append(_bra(at(), EXIT))
    words.append(0x6FE3)         # mov r14,r15 (delay slot)
    size = (END - START) // 2
    assert len(words) <= size, f"{len(words)} words > {size}"
    words += [0x0009] * (size - len(words))
    return b"".join(w.to_bytes(2, "big") for w in words)


PROG5_ORIENTATION_TOGGLE_REFRESH = {
    "LANG/PROG_5.BIN": [(_off(START), rewrite())],
}
