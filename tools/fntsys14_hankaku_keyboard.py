"""tools/fntsys14_hankaku_keyboard.py — hankaku name-entry keyboard (v0.8 gate #2).

Rewrites the name-entry keyboard grid (fntsys14 = FNT_SYS pair 13, 21 records
x 5 BE16 tile cells) so uppercase, lowercase and digits are ALL hankaku band
tiles instead of the zenkaku set (UC 17-42, legacy lc singles 1585-1610,
digits 7-16).

WHY: the name composer appends the CELL'S OWN tile code to the protagonist
name buffer — character cells are content-driven (the 2026-06-11 canary
proved POSITIONAL semantics for button actions/cursor snapping only; the EN
keyboard has always worked through nothing but fntsys14 cell swaps, and no
game binary carries a Latin position->tile table). So swapping the grid to
the hankaku band converts the keyboard VISUAL and the STORED NAME in one
data change: a typed name becomes hankaku tiles, and the `<$F600><$0000>`
token then renders it per-glyph 8px in dialogue through the width-class
dispatch (balloon_zenkaku_cave) — the v0.8 north-star: the player's name
blends seamlessly into hankaku prose.

Layout (same key POSITIONS as the JP/zenkaku grid — cursor/actions are
positional, so occupied cells must not move):
  recs 0-5   A-Z, 5 per row
  rec  6     blank
  recs 7-12  a-z
  rec  13    blank
  rec  14    [empty] ! ? [empty] [empty]
  recs 15-16 blank
  recs 17-18 1 2 3 4 5 / 6 7 8 9 0
  recs 19-20 PRESERVED VERBATIM from the script (ADV/BAK/END buttons
             1488-1490 — our arrow/END art; actions are positional)

Deferred: germanic keys (ä ö ü are already in the band) — the empty cells
are likely positionally UNREACHABLE by the cursor (engine-side valid-cell
map); needs a one-cell reachability canary before shipping.

Declarative: rows resolve through font_tools.HANKAKU_TILE_MAP at encode
time, so hankaku band moves are followed automatically. Toggleable via
patch_registry ('fntsys14_hankaku_keyboard'); disabled -> scripts/en/
fntsys14E.txt ships as-is (the zenkaku keyboard).

SPACING HISTORY (2026-07-14/15, archive/docs/20260714_name_entry_freeze_bug.md):
v1 (drawn space after every key) FROZE the screen — the field-UI staging
ring caps a screen at 192 glyphs and 21x10 drawn cells overflowed it.
v3 (early-FFFF + fetch padding, 9 drawn cells/row) fit the ring but
CORRUPTED the screen anyway: the name-entry STAGING SLOT LAYOUT is an
implicit ABI — the prompt/name redraw expects the keyboard content to
occupy exactly 21 rows x 5 uniform glyphs (slots 7..111); more drawn
cells per row shift the slots and the per-keystroke name redraw
re-rasterizes over the key art (dump 2026-07-15 00:03: prompt slots 0-6,
name AND keyboard row 0 both at slot 7+). CONCLUSION: no record-shaped
change can deliver the 16px columns. Rows are LOCKED at 5 drawn cells;
the 16px-column aesthetic needs a RENDERER-side grid mode (Phase-2 flag,
candidate (c) of the postmortem). '_' empties are the hankaku space
(selecting one appends an 8px space; tile 0 would append a 16px blank).
Guard: tests/test_prog4_name_entry_hankaku.py (row shape + slot count).
"""
import struct

# '_' = empty cell (hankaku space). Rows for records 0-18; 19-20 passthrough.
KEYBOARD_ROWS = [
    "ABCDE", "FGHIJ", "KLMNO", "PQRST", "UVWXY", "Z____",
    "_____",
    "abcde", "fghij", "klmno", "pqrst", "uvwxy", "z____",
    "_____",
    "_!?__",
    "_____", "_____",
    "12345", "67890",
]

def hankaku_keyboard_records(button_records: list) -> list:
    """The 21 fntsys14 records: 19 generated 5-cell rows (SLOT-LOCKED,
    see SPACING HISTORY) + the 2 button records (passed through verbatim
    — our arrow/END art, positional actions)."""
    from font_tools import HANKAKU_TILE_MAP
    assert len(button_records) == 2, "expected the 2 button records (recs 19-20)"
    space = HANKAKU_TILE_MAP[' ']
    recs = []
    for row in KEYBOARD_ROWS:
        cells = [space if ch == "_" else HANKAKU_TILE_MAP[ch] for ch in row]
        recs.append(b"".join(struct.pack(">H", c) for c in cells) + b"\xff\xff")
    recs.extend(button_records)
    return recs
