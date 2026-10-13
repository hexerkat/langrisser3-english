#!/usr/bin/env python3
"""
test_prog4_name_entry_hankaku.py — RED guard for the v0.8 name-entry hankaku
fixes (tools/prog4_name_entry_hankaku.py + the fntsys14 spaced grid, NOT YET
BUILT).

════════════════════════════════════════════════════════════════════════════
RED STATE (2026-07-14): playtest screenshot 20260714T213436 shows (1) the
keyboard keys bunched at 8px while the positional selector slides a 16px
grid, and (2) the typed-name insertion cursor advancing 16px while the
glyphs register at 8px. Both are width-blind sites left over from the
zenkaku era, pinned in the PROG_4 disasm this session
(archive/docs/20260714_name_entry_hankaku_triage.md).
════════════════════════════════════════════════════════════════════════════

ENGINE FACTS (sh-elf-objdump, SH-2 BE, PROG_4 @ load 0x06089000; live RAM
confirmed in the 2026-07-14 21:34 wram-hi dump):

  Keyboard rows = fntsys14 (pair 13) records; the name-entry driver fills a
  21-entry list at 0x06095404 (16 B each: +0 record ptr via the pair's
  OFFSET TABLE — records may be ANY length; +8/+9 X/Y in 8px cells: blocks
  at X=3/14/25). Each row draws as ONE run through the width-class renderer
  (a0lang_field_hankaku_step), so hankaku keys pack at 8px — that is the
  bunching. The grid SELECTOR positions at blockX + col*16px (positional
  semantics, unchanged since JP).

  Key append (block,col 0-4,row): FUN_06091C94.. reads the key tile at
    record_ptr + col*2   (`add r1,r1` @0x06091D30, file 0x8D30)
  and stores it to the name buffer 0x06034D90 (8 tiles + FFFF; the 8-entry
  cap is `mov #7; cmp/hi` @0x06091D06 — NOT touched by this fix: the
  buffer and the save block at 0x0604BF58 hold exactly 9 words).

  Typed-name insertion cursor = a VDP1 sprite, FUN_06092070(pos):
    X = 0xB0 + pos*16   (`shll2; shll2` @0x0609208A, file 0x908A)
    pos > 7 -> parked at X = 0x120 (pool word file 0x911E)
  The glyphs it tracks are hankaku (8px) since the v0.8 keyboard swap.

THE FIX (final, after TWO withdrawn spacing attempts — postmortem in
archive/docs/20260714_name_entry_freeze_bug.md):
  The name-entry STAGING SLOT LAYOUT is an implicit ABI: the prompt/name
  redraw (every keystroke) re-stages glyph slots computed against the
  JP-uniform keyboard content — 21 rows x EXACTLY 5 drawn glyphs
  (slots 7..111). v1 (drawn spacers) overflowed the 192-glyph ring and
  froze the screen; v3 (early-FFFF + fetch padding) fit the ring but
  shifted the slots and the name redraw overwrote the key art (dump
  2026-07-15 00:03: prompt slots 0-6, name AND keyboard row 0 both at
  slot 7+). So: rows LOCKED at 5 drawn cells, fetch stays JP, and only
  the width-blind cursor sites ship:
     - name cursor pos*16 -> pos*8: file 0x908A `shll2;shll2` ->
       `shll2; add r1,r1`
     - parked X 0x120 -> 0xE8 (0xB0 + 7*8): pool file 0x911E
  The 16px-column aesthetic needs a RENDERER-side grid mode (candidate
  (c) of the postmortem) — a separate, gated task.

Faithful-model note (feedback_tdd_effective_behavior): the geometry model
pins what the player sees — key columns, selector alignment, cursor X.
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from font_tools import TWIN_TILE_MAP  # noqa: E402

# ── Engine constants (from the disassembly + dump) ──────────────────────────
# v4 (2026-07-15): cells carry DISPLAY TWINS (wide class, 16px columns);
# the append cave converts them back to hankaku (test_name_entry_twin_glyphs).
TWIN_SPACE = TWIN_TILE_MAP[' ']
BLOCK_X_CELLS = (3, 14, 25)        # row records +8 (8px cells) per block
FIELD_BASE_PX = 0xB0               # typed-name field base X (FUN_06092070)
NAME_CAP = 16                      # entries (prog4_name_cap16, 2026-10-12)

FETCH_OFF = 0x8D30                 # add r1,r1 (col*2) — JP, slot-locked
CURSOR_MUL_OFF = 0x908A            # shll2; shll2 (pos*16 px)
PARKED_X_OFF = 0x911E              # pool 0x0120 (JP: pos>7 parked X)
CAP_OFF = 0x8D06                   # mov #7 — must stay byte-identical

PROG4_PATH = 'LANG/PROG_4.BIN'


# ── Reference geometry model (the REQUIREMENT) ──────────────────────────────
def _ref_key_visual_x_cells(block, col):
    """Where a key's glyph starts with the spaced 10-cell rows: each key
    is key+space = 2 cells, so keys sit on the 16px grid."""
    return BLOCK_X_CELLS[block] + col * 2


def _ref_selector_x_cells(block, col):
    """The positional selector (JP semantics, unchanged): 16px columns."""
    return BLOCK_X_CELLS[block] + col * 2


def _ref_cursor_x_px(pos, width_aware):
    """Typed-name insertion cursor X. width_aware=False = the JP 16px
    step (the bug); True = the fix (8px hankaku step)."""
    step = 8 if width_aware else 16
    cap = NAME_CAP if width_aware else 8      # JP: 8 zenkaku
    if pos > cap - 1:
        # parks the sprite ON the last slot (JP: 0x120 = 0xB0 + 7*16)
        return FIELD_BASE_PX + (cap - 1) * step
    return FIELD_BASE_PX + pos * step


# ── Attempt to import the (not-yet-built) module ────────────────────────────
try:
    import prog4_name_entry_hankaku as MOD  # noqa: E402
    MODULE_PRESENT = True
    IMPORT_ERROR = None
except Exception as exc:
    MOD = None
    MODULE_PRESENT = False
    IMPORT_ERROR = exc

from fntsys14_hankaku_keyboard import (      # noqa: E402
    KEYBOARD_ROWS,
    hankaku_keyboard_records,
)


class TestModuleExists(unittest.TestCase):
    """RED sentinel — names the Red state so Red->Green intent is legible."""

    def test_module_is_built(self):
        self.assertTrue(
            MODULE_PRESENT,
            "RED: tools/prog4_name_entry_hankaku.py not built yet "
            f"({IMPORT_ERROR}). GREEN = create it with the key-fetch stride, "
            "cursor step and parked-X patches + JP baseline, and interleave "
            "the fntsys14 rows with hankaku spaces.")


def _words(rec):
    import struct
    return [t for (t,) in struct.iter_unpack('>H', rec)]


def _drawn(rec):
    """Cells the engine actually draws/stages: everything before FFFF."""
    out = []
    for w in _words(rec):
        if w == 0xFFFF:
            return out
        out.append(w)
    raise AssertionError('record without FFFF terminator')


class TestSlotLockedKeyboardRows(unittest.TestCase):
    """THE SLOT-ABI GUARD: the prompt/name redraw expects the keyboard
    content at slots 7..111 = 21 rows x exactly 5 drawn glyphs. Any row
    that draws more/fewer glyphs shifts every later slot and the
    per-keystroke redraw corrupts the key art (2026-07-15 postmortem)."""

    @classmethod
    def setUpClass(cls):
        buttons = [b'\x05\xd0\x00\x00\x05\xd1\x00\x00\x05\xd2\xff\xff'] * 2
        cls.recs = hankaku_keyboard_records(buttons)
        cls.buttons = buttons

    def test_every_row_draws_exactly_five_glyphs(self):
        for i, rec in enumerate(self.recs):
            self.assertEqual(len(_drawn(rec)), 5,
                             f'rec {i}: slot ABI = 5 drawn glyphs/row')

    def test_screen_slot_layout_is_jp_uniform(self):
        total = sum(len(_drawn(r)) for r in self.recs)
        self.assertEqual(total, 105, 'keyboard content must own slots 7..111')

    def test_keys_at_jp_positions(self):
        for i, row in enumerate(KEYBOARD_ROWS):
            words = _words(self.recs[i])
            for col, ch in enumerate(row):
                want = TWIN_SPACE if ch == '_' else TWIN_TILE_MAP[ch]
                self.assertEqual(words[col], want,
                                 f'rec {i} col {col}: key cell wrong')

    def test_buttons_pass_through(self):
        self.assertEqual(self.recs[19:], self.buttons)


class TestCursorModel(unittest.TestCase):
    """Typed-name cursor tracks the 8px hankaku glyphs."""

    def test_jp_cursor_is_the_bug(self):
        # 2nd letter lands at +8px but the JP cursor points +16px
        self.assertEqual(_ref_cursor_x_px(1, width_aware=False), 0xC0)
        self.assertEqual(_ref_cursor_x_px(1, width_aware=True), 0xB8)

    def test_parked_position_follows_the_field(self):
        # JP pool 0x120 = 0xB0 + 7*16 (parks on the last slot)
        self.assertEqual(_ref_cursor_x_px(8, width_aware=False), 0x120)
        self.assertEqual(_ref_cursor_x_px(16, width_aware=True), 0x128)

    @unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
    def test_module_model_matches_reference(self):
        for pos in range(18):
            self.assertEqual(MOD.cursor_x_px(pos),
                             _ref_cursor_x_px(pos, width_aware=True))


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestPatchDeclaration(unittest.TestCase):
    """Lock the patch shape — runs without the JP disc."""

    def test_touches_only_prog4(self):
        self.assertEqual(list(MOD.PROG4_NAME_ENTRY_HANKAKU), [PROG4_PATH])

    def test_exact_sites(self):
        edits = dict(MOD.PROG4_NAME_ENTRY_HANKAKU[PROG4_PATH])
        self.assertEqual(set(edits), {CURSOR_MUL_OFF, PARKED_X_OFF})
        # cursor: pos*16 -> pos*8 (shll2 ; add r1,r1)
        self.assertEqual(edits[CURSOR_MUL_OFF], bytes.fromhex('4108311c'))
        # parked X: 0xB0 + 15*8 = 0x128 (the JP last-slot rule, 16 cells;
        # 2026-10-12 red state: 0xE8 = the 8-letter cell)
        self.assertEqual(edits[PARKED_X_OFF], bytes.fromhex('0128'))

    def test_fetch_stays_jp(self):
        """col*2 must match the 5-cell records — and the records are
        slot-locked at 5 cells (see TestSlotLockedKeyboardRows)."""
        edits = dict(MOD.PROG4_NAME_ENTRY_HANKAKU[PROG4_PATH])
        self.assertNotIn(FETCH_OFF, edits)

    def test_baseline_covers_same_offsets_same_lengths(self):
        edits = dict(MOD.PROG4_NAME_ENTRY_HANKAKU[PROG4_PATH])
        base = MOD.PROG4_NAME_ENTRY_HANKAKU_JP_BASELINE
        self.assertEqual(set(base), set(edits))
        for off in edits:
            self.assertEqual(len(base[off]), len(edits[off]))

    def test_baseline_words(self):
        base = MOD.PROG4_NAME_ENTRY_HANKAKU_JP_BASELINE
        self.assertEqual(base[CURSOR_MUL_OFF], bytes.fromhex('41084108'))
        self.assertEqual(base[PARKED_X_OFF], bytes.fromhex('0120'))

    def test_cap_is_not_touched(self):
        """The cap itself belongs to prog4_name_cap16 (16 entries since
        2026-10-12); this module only owns the cursor step and park X."""
        edits = dict(MOD.PROG4_NAME_ENTRY_HANKAKU[PROG4_PATH])
        for off in edits:
            span = range(off, off + len(edits[off]))
            self.assertNotIn(CAP_OFF, span)
            self.assertNotIn(CAP_OFF + 1, span)
        self.assertEqual(MOD.NAME_CAP, NAME_CAP)

    def test_registered_in_build(self):
        import build
        self.assertIn('prog4_name_entry_hankaku', build.ENGINE_MODULE_DICTS)
        self.assertIs(build.ENGINE_MODULE_DICTS['prog4_name_entry_hankaku'],
                      MOD.PROG4_NAME_ENTRY_HANKAKU)

    def test_registered_in_patch_registry(self):
        import patch_registry
        self.assertIn('prog4_name_entry_hankaku',
                      patch_registry.ENGINE_PATCH_MODULES)

    def test_disjoint_from_other_prog4_modules(self):
        import build
        ours = set()
        for off, chunk in MOD.PROG4_NAME_ENTRY_HANKAKU[PROG4_PATH]:
            ours |= set(range(off, off + len(chunk)))
        for name, module in build.ENGINE_MODULE_DICTS.items():
            if name == 'prog4_name_entry_hankaku':
                continue
            for off, chunk in module.get(PROG4_PATH, []):
                theirs = set(range(off, off + len(chunk)))
                self.assertFalse(ours & theirs,
                                 f'offset collision with {name}')


JP_DIR = os.environ.get('LANG3_JP_DIR')


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestJPBaseline(unittest.TestCase):
    """Truth-lock the JP bytes at every patch site against the real disc."""

    @classmethod
    def setUpClass(cls):
        from iso_tools import build_file_index, extract_file_data
        jp = Path(JP_DIR)
        cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
        image = bytearray(cands[0].read_bytes())
        idx = build_file_index(image)
        e = idx[PROG4_PATH]
        cls.jp = extract_file_data(image, e.extent, e.size)

    def test_fetch_site(self):
        self.assertEqual(bytes(self.jp[FETCH_OFF:FETCH_OFF + 2]),
                         bytes.fromhex('311c'))          # add r1,r1

    def test_cursor_site(self):
        self.assertEqual(bytes(self.jp[CURSOR_MUL_OFF:CURSOR_MUL_OFF + 4]),
                         bytes.fromhex('41084108'))      # shll2; shll2

    def test_parked_pool(self):
        self.assertEqual(bytes(self.jp[PARKED_X_OFF:PARKED_X_OFF + 2]),
                         bytes.fromhex('0120'))

    def test_cap_site(self):
        self.assertEqual(bytes(self.jp[CAP_OFF:CAP_OFF + 2]),
                         bytes.fromhex('e207'))          # mov #7 (the cap)


if __name__ == '__main__':
    unittest.main()
