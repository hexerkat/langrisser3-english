"""tools/prog3_balloon_zenkaku_dispatch.py — mixed 8/16px steps (v0.8 width classes).

ONE owned DATA patch over the **JP** `LANG/PROG_3.BIN` (load base 0x06052800):
the balloon per-char dispatcher FUN_0607d168 calls the layout fn FUN_0607cf80
through the pool pointer at 0x0607D220 (`mov.l @(0x607d220,pc),r1; jsr @r1` —
the ONLY 0x0607CF80 reference in any game binary, value-exact sweep 2026-07-07).
This module repoints that literal to the width-class dispatcher cave that
tools/balloon_zenkaku_cave.py embeds in free FONT.BIN tiles (LWRAM, resident
whenever text renders — the reachable-cave answer to PROG_3 having no free
code bytes within bra/pc-rel range).

Effect (see balloon_zenkaku_cave for the cave itself):
  - hankaku band tile [1265..1339] -> the real cf80, 1 column (8px);
  - ANY other tile (kanji/kana, bigram, ellipsis 906, full-width space 0,
    zenkaku specials) -> drawn as two adjacent 8px cells (left half + a
    <<8-shifted scratch-glyph right half) and the row cursor advances 2
    columns = 16px. FUN_0607d168's own post-call increment is a memory
    read-modify-write, so the cave's extra +1 composes to +2.

Restores v0.7 rendering for all not-yet-converted bigram content (dialogue,
nameplates, vertical menus) while hankaku prose renders 8px — mixed widths,
the pre-0.4 uppercase-16px/lowercase-8px experiment done properly.

REQUIRES: prog3_dialogue_hankaku_step (8px column step),
prog3_balloon_hankaku_grid (34/26-col grid + 8px-wide textures), and the
`font` encoder module (carries the cave). Disabling `font` while this is
enabled would jump to a zeroed tile — keep them together.

Patch site: file offset 0x0607D220 - 0x06052800 = 0x2AA20.
"""

from balloon_zenkaku_cave import CAVE_ADDR

_POOL_OFFSET = 0x0002AA20

PROG3_BALLOON_ZENKAKU_DISPATCH = {
    "LANG/PROG_3.BIN": [
        (_POOL_OFFSET, CAVE_ADDR.to_bytes(4, "big")),
    ],
}

# JP baseline — verified against the pristine JP PROG_3 by
# tests/test_prog3_balloon_zenkaku_dispatch.py before any build.
JP_BASELINE = {
    _POOL_OFFSET: (0x0607CF80).to_bytes(4, "big"),
}
