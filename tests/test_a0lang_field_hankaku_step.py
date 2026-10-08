#!/usr/bin/env python3
"""
test_a0lang_field_hankaku_step.py — RED guard for the v0.8 A0LANG FIELD-UI
width-class step (tools/a0lang_field_hankaku_step.py, NOT YET BUILT).

════════════════════════════════════════════════════════════════════════════
RED STATE (2026-07-11) — went GREEN 2026-07-12 with the module built.
════════════════════════════════════════════════════════════════════════════
Location labels (`<$FFFF>`-terminated field strings) and field menus render
through the A0LANG VDP2 tilemap renderer `FUN_06016d94` (@0x0600E000, file
offset 0x8D94), NOT the PROG_3 VDP1 balloon path. After the v0.8 hankaku
conversion the label strings are full of narrow (8px) hankaku tiles, but this
renderer steps a FIXED 16px/glyph — so a hankaku label draws with a blank
8px gap after every glyph ("holes"). The scaffold that routed labels back to
bigram was rejected by Ralf (v0.8 must KILL bigram) and `git restore`d, so the
current working tree is the honest Red: labels render hankaku-with-holes.

The fix makes Phase 2 of `FUN_06016d94` WIDTH-CLASS aware: a hankaku-band tile
(1265..1419, the same class PROG_3 Piece C uses) draws ONE cell and steps ONE
cell; every other tile (kanji / zenkaku digit / UI icon) keeps the 2-cell 16px
step so menus/stats do not break.

DECISION PINNED BY THIS TEST — RE-READ, not stash (2026-07-11, Opus, from the
sh-elf-objdump disasm of 0x8E30..0x8EB8):
  Phase 2 writes `pattern_name = 0x5000 + base + g*4 + subtile`, iterating a
  COUNT (r10); it never holds the tile codes (those were consumed in Phase 1's
  `mov.w @r9+,r4`). The width class lives ONLY in the tile string. The cave
  RE-READS tile[g] from the original string pointer, recovered with no scratch
  RAM as `r9 - r10*2` (both live at Phase-2 entry). Stash was rejected: it
  needs a `count`-byte buffer in "free" RAM — the exact trap of the citizen-
  portrait staging-ring bug (archive/docs/20260708_citizen_portrait_staging_
  ring_bug.md). Re-read = zero RAM, ground-truth width, and the same render-
  time range test PROG_3 already uses.

TDD: this file is RED because tools/a0lang_field_hankaku_step.py does not exist
yet. The render-model assertions below are the requirement; GREEN = build the
module (Python width-class model + the byte patch/cave) so its
`simulate_field_row` matches the reference model encoded here.

Faithful-model note (feedback_tdd_effective_behavior): the model mirrors the
ENGINE math traced from the disassembly, so a passing model means the patched
placement the player sees is correct, not just an intermediate byte.

Phase-2 engine facts (sh-elf-objdump, SH-2 BE, A0LANG.BIN @ load 0x0600E000):
  entry  0x6016E30  r7 = *0x0604EE94 (VDP2 tilemap write ptr)
                    r5 = 0x5000       (pattern-name attribute base)
                    r4 = x + 0x100    (per-draw pattern-name base = `base_pn`)
  top    0x6016E60  loop, r3 steps +4/glyph (4 pattern-names per 16x16 glyph):
           0x6016E6A  mov.w r1,@r7   cell A  = 0x5000+base+g*4+0  (top-left)
           0x6016E6C  add #2,r7
           0x6016E74  mov.w r1,@r7   cell B  = 0x5000+base+g*4+1  (top-right)
           0x6016E76  add #4,r3
           0x6016E7E  add #2,r7      (delay slot)  -> +4 bytes = 2 cells/glyph
  jump   0x6016E80  r7 += (64 - count*2)*2   -> next tilemap row (assumes 2/glyph)
  bottom 0x6016E9A  identical, sub-tile offset +2/+3 (bottom-left/right)
"""

import os
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

from font_tools import (                                            # noqa: E402
    HANKAKU_TILE_MAP,
    HANKAKU_TILES,
    HANKAKU_BASE,
    V08_RESERVED_TILES,
    BIGRAM_TILE_MAP,
)

# ── Engine constants (from the disassembly) ─────────────────────────────────
ATTR_BASE = 0x5000       # r5: pattern-name attribute base
SUBTILE_PER_GLYPH = 4    # r3 step: 4 pattern-names per 16x16 staging char

# Hankaku width class = the v0.8 narrow band, identical to PROG_3 Piece C's
# class boundary (font_tools.py:104 "hankaku class range [1265..1419]").
NARROW_LO = HANKAKU_BASE   # 1265
NARROW_HI = 1419           # cave/nakaguro start at 1420 -> those stay 16px


# ── Reference render model (the REQUIREMENT) ────────────────────────────────
# This is the source of truth the module must reproduce. It mirrors the
# Phase-2 loop: pattern names are per-glyph (g*4 + subtile), but the tilemap
# CELL cursor accumulates by WIDTH CLASS, not a fixed 2 cells.
def _ref_is_narrow(tile):
    return NARROW_LO <= tile <= NARROW_HI


def _ref_field_row(tiles, base_pn, row, width_aware):
    """Return {cell_col: pattern_name} for one tilemap row.

    row='top'    -> sub-tile offset 0 (left) / 1 (right)
    row='bottom' -> sub-tile offset 2 (left) / 3 (right)
    width_aware=False models the JP binary (every glyph 2 cells / 16px).
    width_aware=True  models the fix (narrow band tile -> 1 cell / 8px).
    """
    sub_left = 0 if row == 'top' else 2
    col = 0
    out = {}
    for g, t in enumerate(tiles):
        pn_left = ATTR_BASE + base_pn + g * SUBTILE_PER_GLYPH + sub_left
        out[col] = pn_left
        wide = (not width_aware) or (not _ref_is_narrow(t))
        if wide:
            out[col + 1] = pn_left + 1
            col += 2
        else:
            col += 1
    return out


def _ref_row_cells(tiles, width_aware):
    """Total cells consumed by one row = the value the inter-row jump needs."""
    if not width_aware:
        return 2 * len(tiles)
    return sum(1 if _ref_is_narrow(t) else 2 for t in tiles)


def _label_tiles(text):
    """Encode a plain field label to hankaku tile codes (all in-band)."""
    return [HANKAKU_TILE_MAP[c] for c in text]


# ── Attempt to import the (not-yet-built) module ────────────────────────────
try:
    import a0lang_field_hankaku_step as MOD  # noqa: E402
    MODULE_PRESENT = True
    IMPORT_ERROR = None
except Exception as exc:                      # ModuleNotFoundError while RED
    MOD = None
    MODULE_PRESENT = False
    IMPORT_ERROR = exc


class TestModuleExists(unittest.TestCase):
    """RED sentinel — names the Red state so Red->Green intent is legible."""

    def test_module_is_built(self):
        self.assertTrue(
            MODULE_PRESENT,
            "RED: tools/a0lang_field_hankaku_step.py not built yet "
            f"({IMPORT_ERROR}). GREEN = create it with is_narrow_tile / "
            "simulate_field_row / field_row_cells matching the reference model "
            "in this test, plus the A0LANG cave byte patch + JP baseline.")

    def test_module_exposes_api(self):
        if not MODULE_PRESENT:
            self.skipTest("module absent — covered by test_module_is_built")
        for name in ('is_narrow_tile', 'simulate_field_row', 'field_row_cells',
                     'A0LANG_FIELD_HANKAKU_STEP',
                     'A0LANG_FIELD_HANKAKU_STEP_JP_BASELINE'):
            self.assertTrue(hasattr(MOD, name), f"module missing {name}")


class TestWidthClassPredicate(unittest.TestCase):
    """The narrow class is exactly the v0.8 hankaku glyph band [1265..1419]."""

    def test_reference_band_matches_source_of_truth(self):
        # Every composed hankaku glyph is inside the narrow range...
        self.assertTrue(HANKAKU_TILES, "no hankaku tiles composed")
        for t in HANKAKU_TILES:
            self.assertTrue(NARROW_LO <= t <= NARROW_HI,
                            f"hankaku tile {t} outside narrow class")
        # ...and the range stays within the reserved band (no engine-fixed
        # tile ever tests narrow).
        for t in range(NARROW_LO, NARROW_HI + 1):
            self.assertIn(t, V08_RESERVED_TILES)

    def test_zenkaku_and_bigram_tiles_are_wide(self):
        # a stat digit (engine tiles 7..16) is zenkaku -> wide
        self.assertFalse(_ref_is_narrow(7))
        # the cave/nakaguro tiles above the class -> wide (16px)
        self.assertFalse(_ref_is_narrow(1420))
        self.assertFalse(_ref_is_narrow(1428))   # ・ nakaguro
        # a common bigram tile -> wide
        some_bigram = min(BIGRAM_TILE_MAP.values())
        self.assertFalse(_ref_is_narrow(some_bigram))

    @unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
    def test_module_predicate_matches_reference(self):
        for t in [7, 16, NARROW_LO, NARROW_HI, NARROW_LO - 1, NARROW_HI + 1,
                  1428, min(BIGRAM_TILE_MAP.values())]:
            self.assertEqual(MOD.is_narrow_tile(t), _ref_is_narrow(t),
                             f"is_narrow_tile({t}) disagrees with reference")


class TestFieldRowModel(unittest.TestCase):
    """The heart of the requirement: hankaku labels step 1 cell/glyph."""

    def test_jp_model_is_the_broken_16px_step(self):
        """Documents the CURRENT binary: every glyph writes 2 cells. The odd
        cells hold the glyph's RIGHT sub-tile, which is BLANK for a hankaku
        glyph (art lives in the left 8px only) — that blank is the 8px 'hole'
        the player sees. 6 glyphs -> all 12 cells written, cursor = 12."""
        tiles = _label_tiles("Castle")           # all narrow
        jp = _ref_field_row(tiles, base_pn=0, row='top', width_aware=False)
        self.assertEqual(sorted(jp), list(range(12)))        # both halves written
        # odd cells = the blank right sub-tiles = the visible holes
        for g in range(6):
            self.assertEqual(jp[2 * g], ATTR_BASE + g * 4)       # left = real glyph
            self.assertEqual(jp[2 * g + 1], ATTR_BASE + g * 4 + 1)  # right = blank
        self.assertEqual(_ref_row_cells(tiles, width_aware=False), 12)

    def test_hankaku_label_renders_contiguous_narrow(self):
        """THE FIX: a hankaku label packs into contiguous cells, no holes."""
        tiles = _label_tiles("Castle")
        hk = _ref_field_row(tiles, base_pn=0, row='top', width_aware=True)
        self.assertEqual(sorted(hk), [0, 1, 2, 3, 4, 5])   # no gaps
        self.assertEqual(_ref_row_cells(tiles, width_aware=True), 6)
        # pattern names stay per-glyph g*4 (staging layout unchanged)
        self.assertEqual(hk[0], ATTR_BASE + 0)             # glyph 0 top-left
        self.assertEqual(hk[1], ATTR_BASE + 4)             # glyph 1 top-left
        self.assertEqual(hk[5], ATTR_BASE + 5 * 4)         # glyph 5 top-left

    def test_bottom_row_uses_lower_subtiles(self):
        tiles = _label_tiles("Fort")
        hk = _ref_field_row(tiles, base_pn=0, row='bottom', width_aware=True)
        self.assertEqual(sorted(hk), [0, 1, 2, 3])
        self.assertEqual(hk[0], ATTR_BASE + 2)             # glyph 0 bottom-left
        self.assertEqual(hk[1], ATTR_BASE + 4 + 2)         # glyph 1 bottom-left

    def test_mixed_width_accumulates(self):
        """A zenkaku tile mid-string costs 2 cells; neighbours cost 1 — the
        cursor must accumulate, never assume uniform width."""
        # H(narrow) 7(zenkaku digit) P(narrow)
        tiles = [HANKAKU_TILE_MAP['H'], 7, HANKAKU_TILE_MAP['P']]
        hk = _ref_field_row(tiles, base_pn=0, row='top', width_aware=True)
        # widths 1,2,1 -> cols {0} {1,2} {3}
        self.assertEqual(sorted(hk), [0, 1, 2, 3])
        self.assertEqual(hk[0], ATTR_BASE + 0)             # H top-left
        self.assertEqual(hk[1], ATTR_BASE + 4)             # digit top-left
        self.assertEqual(hk[2], ATTR_BASE + 5)             # digit top-right (wide)
        self.assertEqual(hk[3], ATTR_BASE + 8)             # P top-left
        self.assertEqual(_ref_row_cells(tiles, width_aware=True), 4)

    def test_base_pn_offsets_pattern_names(self):
        tiles = _label_tiles("Ab")
        hk = _ref_field_row(tiles, base_pn=0x40, row='top', width_aware=True)
        self.assertEqual(hk[0], ATTR_BASE + 0x40 + 0)
        self.assertEqual(hk[1], ATTR_BASE + 0x40 + 4)

    @unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
    def test_module_row_matches_reference(self):
        for text, row, wa in [("Castle", 'top', True), ("Castle", 'top', False),
                              ("Fort", 'bottom', True), ("Village", 'top', True)]:
            tiles = _label_tiles(text)
            self.assertEqual(
                MOD.simulate_field_row(tiles, base_pn=0, row=row, width_aware=wa),
                _ref_field_row(tiles, base_pn=0, row=row, width_aware=wa),
                f"simulate_field_row mismatch for {text!r} row={row} wa={wa}")
            self.assertEqual(
                MOD.field_row_cells(tiles, width_aware=wa),
                _ref_row_cells(tiles, width_aware=wa),
                f"field_row_cells mismatch for {text!r} wa={wa}")


# ── JP baseline truth-lock at the Phase-2 patch region ──────────────────────
# The exact JP words the GREEN cave/patch will neutralise or redirect. Pinning
# them anchors the patch site and catches any drift in the source binary.
# (word offset in A0LANG.BIN -> big-endian 16-bit value, from the disasm.)
JP_PHASE2_BASELINE = {
    0x8E30: 0xD132,   # mov.l @(disp,pc),r1   Phase-2 entry: load VDP2 tilemap ptr
    0x8E6A: 0x2711,   # mov.w r1,@r7          top-row cell A (left half)
    0x8E6C: 0x7702,   # add #2,r7             -> cell B
    0x8E74: 0x2711,   # mov.w r1,@r7          top-row cell B (RIGHT half = 16px)
    0x8E76: 0x7304,   # add #4,r3             glyph-index step (4 pn/glyph)
    0x8E7E: 0x7702,   # add #2,r7 (delay)     -> next glyph cell A (total +4B=2 cells)
    0x8E80: 0x62A3,   # mov r10,r2            inter-row: r2 = glyph count
    0x8E82: 0x322C,   # add r2,r2             count*2  (assumes uniform 2 cells/glyph)
    0x8E84: 0xE140,   # mov #64,r1            tilemap row stride (64 cells)
    0x8E86: 0x3128,   # sub r2,r1             64 - count*2 = cells to skip
    0x8EB0: 0x7304,   # add #4,r3             bottom-row glyph-index step
    0x8EB8: 0x7702,   # add #2,r7 (delay)     bottom-row step
}

A0LANG_PATH = 'A0LANG.BIN'
A0LANG_SIZE = 158288
JP_DIR = os.environ.get('LANG3_JP_DIR')


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestPhase2JPBaseline(unittest.TestCase):
    """Lock the JP bytes at the Phase-2 loop the fix will patch."""

    @classmethod
    def setUpClass(cls):
        from iso_tools import build_file_index, extract_file_data
        jp = Path(JP_DIR)
        cands = list(jp.glob('*rack*01*.bin')) or list(jp.glob('*.bin'))
        image = bytearray(cands[0].read_bytes())
        idx = build_file_index(image)
        e = idx[A0LANG_PATH]
        cls.jp = extract_file_data(image, e.extent, e.size)

    def test_jp_size(self):
        self.assertEqual(len(self.jp), A0LANG_SIZE)

    def test_phase2_baseline_words_match(self):
        for off, word in JP_PHASE2_BASELINE.items():
            got = (self.jp[off] << 8) | self.jp[off + 1]
            self.assertEqual(got, word,
                             f"A0LANG[0x{off:X}] = {got:#06x}, expected {word:#06x} "
                             "— Phase-2 layout drifted; re-verify the disasm")

    def test_the_16px_step_is_where_we_think(self):
        """The two `add #2,r7` steps (0x8E6C top / 0x8E7E delay) are what make a
        glyph occupy 2 cells; the cave suppresses the second for narrow tiles."""
        self.assertEqual((self.jp[0x8E6C] << 8) | self.jp[0x8E6D], 0x7702)
        self.assertEqual((self.jp[0x8E7E] << 8) | self.jp[0x8E7F], 0x7702)


# ═════════════════════════════════════════════════════════════════════════
# GREEN-side locks (2026-07-12): patch declaration, band<->bytes coupling,
# and an SH-2 mini-interpreter that EXECUTES the patched byte stream against
# the reference render model. Byte-locks alone let the cf3c scroll bug slip
# (semantics wrong, bytes "verified"); execution closes that class.
# ═════════════════════════════════════════════════════════════════════════

REGION_OFF = 0x8E58          # rewritten Phase-2 stream (file offset)
REGION_LEN = 0x62            # 49 words, ends right before the exit code
POOL_OFF = 0x8EE6            # pool pad word -> 0x04F1
EXIT_OFF = 0x8EBA            # first untouched exit-code word


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestPatchDeclaration(unittest.TestCase):
    """Lock the patch shape — runs without the JP disc."""

    def test_touches_only_a0lang(self):
        self.assertEqual(list(MOD.A0LANG_FIELD_HANKAKU_STEP), ['A0LANG.BIN'])

    def test_exact_region_and_pool(self):
        edits = dict(MOD.A0LANG_FIELD_HANKAKU_STEP['A0LANG.BIN'])
        self.assertEqual(set(edits), {REGION_OFF, POOL_OFF})
        self.assertEqual(len(edits[REGION_OFF]), REGION_LEN)
        # the stream must NOT reach the exit code at 0x8EBA
        self.assertEqual(REGION_OFF + len(edits[REGION_OFF]), EXIT_OFF)
        self.assertEqual(edits[POOL_OFF], b'\x04\xF1')       # 1265

    def test_baseline_covers_same_offsets_same_lengths(self):
        edits = dict(MOD.A0LANG_FIELD_HANKAKU_STEP['A0LANG.BIN'])
        base = MOD.A0LANG_FIELD_HANKAKU_STEP_JP_BASELINE
        self.assertEqual(set(base), set(edits))
        for off in edits:
            self.assertEqual(len(base[off]), len(edits[off]),
                             f"baseline length mismatch at 0x{off:X}")

    def test_baseline_matches_pinned_phase2_words(self):
        """The module's own region baseline agrees with the JP words this test
        pinned from the disasm (same source of truth, two encodings)."""
        region = MOD.A0LANG_FIELD_HANKAKU_STEP_JP_BASELINE[REGION_OFF]
        for off, word in JP_PHASE2_BASELINE.items():
            if REGION_OFF <= off < REGION_OFF + REGION_LEN:
                rel = off - REGION_OFF
                got = (region[rel] << 8) | region[rel + 1]
                self.assertEqual(got, word, f"baseline drift at 0x{off:X}")

    def test_band_constants_track_font_tools(self):
        """The renderer's narrow class must equal the composed hankaku band —
        the pool word (1265) and the in-stream 77*2 (=154) encode it."""
        self.assertEqual(MOD.NARROW_LO, HANKAKU_BASE)          # 1265 = 0x4F1
        self.assertEqual(MOD.NARROW_HI - MOD.NARROW_LO, 154)   # mov #77; add
        self.assertEqual(MOD.NARROW_HI, NARROW_HI)             # 1419, this test
        for t in HANKAKU_TILES:
            self.assertTrue(MOD.is_narrow_tile(t))
        self.assertFalse(MOD.is_narrow_tile(1420))             # cave = zenkaku
        self.assertFalse(MOD.is_narrow_tile(1428))             # nakaguro

    def test_registered_in_build(self):
        import build
        self.assertIn('a0lang_field_hankaku_step', build.ENGINE_MODULE_DICTS)
        self.assertIs(build.ENGINE_MODULE_DICTS['a0lang_field_hankaku_step'],
                      MOD.A0LANG_FIELD_HANKAKU_STEP)

    def test_disjoint_from_other_a0lang_modules(self):
        import build
        ours = set()
        for off, chunk in MOD.A0LANG_FIELD_HANKAKU_STEP['A0LANG.BIN']:
            ours |= set(range(off, off + len(chunk)))
        for name, module in build.ENGINE_MODULE_DICTS.items():
            if name == 'a0lang_field_hankaku_step':
                continue
            for off, chunk in module.get('A0LANG.BIN', []):
                theirs = set(range(off, off + len(chunk)))
                self.assertFalse(ours & theirs,
                                 f"offset collision with {name}")


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestLabelsStayHankakuInD00(unittest.TestCase):
    """Regression guard: the rejected scaffold routed labels back to bigram.
    v0.8 keeps ALL entries (labels included) on the hankaku encoder; the
    renderer, not the encoding, is what this branch fixes."""

    def test_routing_is_all_hankaku(self):
        from d00_tools import is_hankaku_entry
        self.assertTrue(is_hankaku_entry(5, 'Castle of Larcuss'))

    def test_label_text_encodes_into_the_band(self):
        import struct
        from hankaku_encoder import encode_hankaku
        data = encode_hankaku('Castle')
        tiles = [t for (t,) in struct.iter_unpack('>H', data)]
        self.assertEqual(len(tiles), 6)
        for t in tiles:
            self.assertTrue(MOD.is_narrow_tile(t),
                            f"label tile {t} not in the hankaku band")


# ── SH-2 mini-interpreter (subset used by both Phase-2 streams) ─────────────
def _sx8(v):
    return v - 0x100 if v & 0x80 else v


def _sx16(v):
    return v - 0x10000 if v & 0x8000 else v


class _Sh2Phase2:
    """Executes Phase 2 (from REGION_OFF to EXIT_OFF) over a synthetic image.

    Faithful-model note (feedback_tdd_effective_behavior): this runs the REAL
    patch bytes (and the REAL JP bytes), so the assertions pin the effective
    engine behavior, not a transcription of it.
    """
    STR = 0x100000        # synthetic tile-string address
    TM = 0x200000         # synthetic VDP2 tilemap row-0 address

    def __init__(self, image):
        self.image = image

    def run(self, tiles, base_pn):
        ram = {}
        for i, t in enumerate(tiles):
            ram[self.STR + 2 * i] = t & 0xFFFF
        ram[self.STR + 2 * len(tiles)] = 0xFFFF
        R = [0] * 16
        R[4] = base_pn
        R[5] = ATTR_BASE
        R[6] = len(tiles)                      # count (pre-shll2, as at 0x8E58)
        R[7] = self.TM
        R[9] = self.STR + 2 * len(tiles)       # terminator ptr (Phase-1 exit)
        R[10] = len(tiles)
        self.R, self.ram, self.T = R, ram, 0
        self.writes = {}
        pc, steps = REGION_OFF, 0
        while pc != EXIT_OFF:
            steps += 1
            if steps > 100000:
                raise AssertionError('interpreter runaway (bad branch?)')
            pc = self._step(pc)
        # split the recorded writes into the two tilemap rows
        top, bottom = {}, {}
        for addr, val in self.writes.items():
            if self.TM <= addr < self.TM + 0x80:
                top[(addr - self.TM) // 2] = val
            elif self.TM + 0x80 <= addr < self.TM + 0x100:
                bottom[(addr - self.TM - 0x80) // 2] = val
            else:
                raise AssertionError(f'write outside both rows: 0x{addr:X}')
        return top, bottom

    def _rw(self, addr):
        if addr in self.ram:
            return self.ram[addr]
        return (self.image[addr] << 8) | self.image[addr + 1]

    def _exec(self, pc):
        """One non-branch instruction at pc. Returns nothing."""
        R, w = self.R, (self.image[pc] << 8) | self.image[pc + 1]
        n, m = (w >> 8) & 0xF, (w >> 4) & 0xF
        M = 0xFFFFFFFF
        if w == 0x0009:                                    # nop
            pass
        elif (w & 0xF00F) == 0x6003:                       # mov Rm,Rn
            R[n] = R[m]
        elif (w & 0xF000) == 0xE000:                       # mov #imm8,Rn
            R[n] = _sx8(w & 0xFF) & M
        elif (w & 0xF00F) == 0x6005:                       # mov.w @Rm+,Rn
            R[n] = _sx16(self._rw(R[m])) & M
            R[m] = (R[m] + 2) & M
        elif (w & 0xF00F) == 0x2001:                       # mov.w Rm,@Rn
            addr = R[n]
            self.writes[addr] = R[m] & 0xFFFF
            self.ram[addr] = R[m] & 0xFFFF
        elif (w & 0xF000) == 0x9000:                       # mov.w @(d,PC),Rn
            R[n] = _sx16(self._rw(pc + 4 + (w & 0xFF) * 2)) & M
        elif (w & 0xF00F) == 0x300C:                       # add Rm,Rn
            R[n] = (R[n] + R[m]) & M
        elif (w & 0xF000) == 0x7000:                       # add #imm,Rn
            R[n] = (R[n] + _sx8(w & 0xFF)) & M
        elif (w & 0xF00F) == 0x3008:                       # sub Rm,Rn
            R[n] = (R[n] - R[m]) & M
        elif (w & 0xF0FF) == 0x4000:                       # shll Rn
            self.T = (R[n] >> 31) & 1
            R[n] = (R[n] << 1) & M
        elif (w & 0xF0FF) == 0x4008:                       # shll2 Rn
            R[n] = (R[n] << 2) & M
        elif (w & 0xF00F) == 0x600D:                       # extu.w Rm,Rn
            R[n] = R[m] & 0xFFFF
        elif (w & 0xF00F) == 0x3002:                       # cmp/hs Rm,Rn
            self.T = 1 if R[n] >= R[m] else 0
        elif (w & 0xF00F) == 0x3006:                       # cmp/hi Rm,Rn
            self.T = 1 if R[n] > R[m] else 0
        else:
            raise AssertionError(f'unimplemented opcode {w:04X} @0x{pc:X}')

    def _step(self, pc):
        """Execute at pc (handling branches + delay slots); return next pc."""
        w = (self.image[pc] << 8) | self.image[pc + 1]
        hi = w >> 8
        if hi in (0x89, 0x8B):                             # bt / bf
            taken = self.T == (1 if hi == 0x89 else 0)
            return pc + 4 + _sx8(w & 0xFF) * 2 if taken else pc + 2
        if hi in (0x8D, 0x8F):                             # bt/s / bf/s
            taken = self.T == (1 if hi == 0x8D else 0)
            self._exec(pc + 2)                             # delay slot always
            return pc + 4 + _sx8(w & 0xFF) * 2 if taken else pc + 4
        if (w & 0xF000) == 0xA000:                         # bra
            d = w & 0xFFF
            if d & 0x800:
                d -= 0x1000
            self._exec(pc + 2)
            return pc + 4 + d * 2
        self._exec(pc)
        return pc + 2


def _make_image(stream, pool_word):
    """Synthetic A0LANG slice: the given Phase-2 stream + pool constant."""
    img = bytearray(0x9000)
    img[REGION_OFF:REGION_OFF + len(stream)] = stream
    img[POOL_OFF] = pool_word >> 8
    img[POOL_OFF + 1] = pool_word & 0xFF
    return bytes(img)


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestExecutePatchedBytes(unittest.TestCase):
    """Run the ACTUAL patched stream and compare cell-for-cell to the model."""

    @classmethod
    def setUpClass(cls):
        edits = dict(MOD.A0LANG_FIELD_HANKAKU_STEP['A0LANG.BIN'])
        pool = (edits[POOL_OFF][0] << 8) | edits[POOL_OFF][1]
        cls.vm = _Sh2Phase2(_make_image(edits[REGION_OFF], pool))
        jp = MOD.A0LANG_FIELD_HANKAKU_STEP_JP_BASELINE[REGION_OFF]
        cls.jp_vm = _Sh2Phase2(_make_image(jp, 0x0000))

    def _check(self, vm, tiles, width_aware, base_pn=0x140):
        top, bottom = vm.run(tiles, base_pn)
        self.assertEqual(
            top, _ref_field_row(tiles, base_pn, 'top', width_aware))
        self.assertEqual(
            bottom, _ref_field_row(tiles, base_pn, 'bottom', width_aware))

    def test_all_narrow_label(self):
        self._check(self.vm, _label_tiles('Castle'), width_aware=True)

    def test_longer_label_with_space(self):
        self._check(self.vm, _label_tiles('Castle of Larcuss'),
                    width_aware=True)

    def test_mixed_narrow_zenkaku_narrow(self):
        tiles = [HANKAKU_TILE_MAP['H'], 7, HANKAKU_TILE_MAP['P'], 1428]
        self._check(self.vm, tiles, width_aware=True)

    def test_all_wide_menu_string_is_jp_identical(self):
        """Menus/kanji/stat digits: the patched stream must write the exact
        cells the JP code writes — behavior-identical outside the band."""
        tiles = [7, 8, 9, 500, 1200, 1690]
        top_p, bot_p = self.vm.run(tiles, 0x140)
        top_j, bot_j = self.jp_vm.run(tiles, 0x140)
        self.assertEqual(top_p, top_j)
        self.assertEqual(bot_p, bot_j)

    def test_band_edges(self):
        tiles = [NARROW_LO, NARROW_HI, NARROW_LO - 1, NARROW_HI + 1]
        self._check(self.vm, tiles, width_aware=True)

    def test_empty_string_writes_nothing(self):
        top, bottom = self.vm.run([], 0x140)
        self.assertEqual(top, {})
        self.assertEqual(bottom, {})

    def test_exit_registers_preserved(self):
        """The untouched exit code needs r10 (count); r4/r5 sanity too."""
        tiles = _label_tiles('Fort')
        self.vm.run(tiles, 0x140)
        self.assertEqual(self.vm.R[10], len(tiles))
        self.assertEqual(self.vm.R[5], ATTR_BASE)
        self.assertEqual(self.vm.R[4], 0x140)

    def test_jp_stream_matches_uniform_model(self):
        """Interpreter + baseline sanity: the pristine JP bytes reproduce the
        width-blind model exactly (both rows, inter-row jump included)."""
        for text in ('Castle', 'Fort'):
            self._check(self.jp_vm, _label_tiles(text), width_aware=False)
        self._check(self.jp_vm, [7, 1690, 500], width_aware=False)


if __name__ == '__main__':
    unittest.main()
