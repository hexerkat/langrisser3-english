"""tools/prog4_name_entry_hankaku.py — name-entry width-class fixes (v0.8).

THREE owned byte patches over the **JP** `LANG/PROG_4.BIN` (load base
0x06089000 — PROG_4 drives the name-entry screen; pinned 2026-07-14 by the
Ymir wram dump: PROG_3 at 0x06052800 + PROG_4 keyboard state at 0x60954xx).

WHY (branch font-hankaku-per-glyph, playtest 2026-07-14): with the v0.8
hankaku keyboard the typed name registers per-glyph 8px, but two PROG_4
sites still assume 16px/glyph, and the spaced keyboard grid (see
tools/fntsys14_hankaku_keyboard.py) needs its fetch stride doubled:

1. (WITHDRAWN TWICE — see archive/docs/20260714_name_entry_freeze_bug.md)
   The 16px-column grid cannot be delivered by record shapes: v1 (drawn
   spacers) overflowed the 192-glyph staging ring and froze the screen;
   v3 (early-FFFF + fetch padding, 9 drawn cells/row) fit the ring but
   shifted the STAGING SLOT LAYOUT — an implicit ABI: the per-keystroke
   prompt/name redraw re-stages slots computed for the JP-uniform
   21 rows x 5 glyphs (kbd = slots 7..111), so the name art overwrote
   the key art (dump 2026-07-15 00:03). Rows are LOCKED at 5 drawn
   cells and the key fetch at file 0x8D30 stays JP (`add r1,r1`,
   col*2). The column aesthetic needs a RENDERER-side grid mode.

2. NAME CURSOR STEP (file 0x908A, `FUN_06092070`): the insertion cursor is
   a VDP1 sprite at `X = 0xB0 + pos*16` (`shll2; shll2`). The name is
   hankaku-only by construction (the keyboard offers nothing else), so the
   correct step is a flat 8px: `shll2; add r1,r1` (pos*8).

3. PARKED X (pool word file 0x911E): past the cap the JP code parks the
   cursor ON the last slot (0x120 = 0xB0 + 7*16). Same rule at 8px with
   the 16-letter cap: 0x128 = 0xB0 + 15*8 (0xE8 = 0xB0 + 7*8 until
   2026-10-12).

NOT HERE: the cap itself (16 entries) and the park test `mov #15` live in
prog4_name_cap16; the buffer move in name_buffer_home; the save format in
a0lang_save_name_pack.

The grid SELECTOR (blockX + col*16px, positional JP semantics) needs no
patch: with the spaced records the key columns land exactly under it.

Guard: tests/test_prog4_name_entry_hankaku.py (JP baseline truth-lock +
patched-byte locks + the geometry model of what the player sees).
"""

# ── Engine geometry constants (FUN_06092070 / keyboard state disasm) ────────
NAME_CAP = 16           # entries (prog4_name_cap16)
FIELD_BASE_PX = 0xB0    # typed-name field base X
BLOCK_X_CELLS = (3, 14, 25)   # keyboard block origins (8px cells)

# ── Patch site bookkeeping ──────────────────────────────────────────────────
PROG4_LOAD_BASE = 0x06089000
FETCH_OFF = 0x8D30      # add r1,r1 (col*2) — JP, NOT patched (5-cell rows)
CURSOR_MUL_OFF = 0x908A  # shll2; shll2 (pos*16) -> shll2; add r1,r1 (pos*8)
PARKED_X_OFF = 0x911E   # pool 0x0120            -> 0x0128

PROG4_NAME_ENTRY_HANKAKU = {
    "LANG/PROG_4.BIN": [
        (CURSOR_MUL_OFF, bytes.fromhex("4108311C")),  # shll2 r1; add r1,r1
        (PARKED_X_OFF, bytes.fromhex("0128")),       # 0xB0 + 15*8
    ],
}

# JP baseline at every site — truth-locked against the pristine JP disc
# by tests/test_prog4_name_entry_hankaku.py before any build.
PROG4_NAME_ENTRY_HANKAKU_JP_BASELINE = {
    CURSOR_MUL_OFF: bytes.fromhex("41084108"),       # shll2 r1; shll2 r1
    PARKED_X_OFF: bytes.fromhex("0120"),             # 0xB0 + 7*16
}


# ── Python geometry model (the requirement the bytes implement) ─────────────
def cursor_x_px(pos: int) -> int:
    """Typed-name insertion cursor X the player sees (8px hankaku step;
    past the cap it parks on the last slot, the JP rule)."""
    if pos > NAME_CAP - 1:
        return FIELD_BASE_PX + (NAME_CAP - 1) * 8
    return FIELD_BASE_PX + pos * 8


def key_cell_index(col: int) -> int:
    """Record cell the append fetches for column N (JP 5-cell rows)."""
    return col


def selector_x_cells(block: int, col: int) -> int:
    """Grid selector X (8px cells) — positional, unchanged from JP."""
    return BLOCK_X_CELLS[block] + col * 2
