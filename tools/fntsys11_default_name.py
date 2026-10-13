"""tools/fntsys11_default_name.py — the default protagonist name in 8px letters.

The name screen (PROG_4 state 0, load 0x06091A12) copies FNT_SYS pair 10
(fntsys11) record 0 into the name buffer through A0LANG 0x06016D04, then the
player edits it with the keyboard. The keyboard only types hankaku band
letters (8px), but the hybrid encoder writes "Diehärte" as 4 bigram tiles.
With the 16-letter cap a kept default plus typed letters would mix 16px tiles
into a 128px field (up to 160px) and could not be packed into the save
(a0lang_save_name_pack packs band letters only).

So record 0 is written in the band, one tile per letter: the same pixels and
the same 8 cells of width, and every name the screen can produce is 8px only.
The copy cap rises to 16 words in prog4_name_cap16 (JP passes 6).

Guard: tests/test_name_cap16.py (record bytes, the copy executed on the real
A0LANG function, the built FNT_SYS).
"""
import struct

from font_tools import HANKAKU_TILE_MAP

DEFAULT_NAME_PAIR = 10           # fntsys11E.txt
DEFAULT_NAME_RECORD = 0


def default_name_record(line: str) -> bytes:
    """`Diehärte<$FFFF>` -> one hankaku band tile per letter + FFFF."""
    text = line[:-len("<$FFFF>")] if line.endswith("<$FFFF>") else line
    missing = [c for c in text if c not in HANKAKU_TILE_MAP]
    if missing:
        raise ValueError(f"default name has letters outside the 8px band: {missing}")
    return b"".join(struct.pack(">H", HANKAKU_TILE_MAP[c]) for c in text) + b"\xff\xff"
