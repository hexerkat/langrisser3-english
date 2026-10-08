#!/usr/bin/env python3
"""
test_a0lang_label_box_width.py — RED guard for the v0.8 location-label BOX
width fix (tools/a0lang_label_box_width.py, NOT YET BUILT).

════════════════════════════════════════════════════════════════════════════
RED STATE (2026-07-14): the module does not exist; the built ISO still runs
the JP width-blind measurer, so the label box is ~2x as wide as its text.
════════════════════════════════════════════════════════════════════════════
The field location-label BOX (yellow 9-piece frame around e.g. "Church of
Laffel") is measured by A0LANG `FUN_06012A98` (@0x0600E000, file 0x4A98):
it walks the `<$FFFF>`-terminated tile string counting a FIXED 2 tilemap
cells (16px) per word (`add #2,r5` @0x6012AAC), rejects the label when the
sum exceeds 35 cells, then `FUN_06012AF4` builds a STACK descriptor with
    box W = cells + 4          (frame + margin)
    box X = 18 - cells/2       (screen-centred; screen = 40 cells)
and the box grow/close animations run against that stack descriptor. This
is why no static writer for a "label width" was ever found in RAM: the
hugging geometry never lives at a fixed address.

Proven in Ymir (2026-07-14, /tmp/uidbg_jp.log + wram-hi dump): JP church
label ラフェルの都・教会 (9 zenkaku = 18 cells) -> grow session target W=22,
X=9, on-screen tilemap box rows 14..17 cols 9..30 — the box HUGS the text.
The EN v0.8 build renders the same label text hankaku (1 cell/glyph via
a0lang_field_hankaku_step) but this measurer still counts 2 cells/word:
"Church of Laffel" (16 narrow glyphs = 16 cells) measures 32 -> box W=36 at
X=2 — the reported "caixa 2x a largura do texto".

THE FIX: make the measurer width-class aware — a hankaku-band tile
(1265..1419, the SAME class a0lang_field_hankaku_step patched into the
renderer at file 0x8E58) counts 1 cell; every other word keeps 2 cells.
Renderer and measurer then agree cell-for-cell, so the box hugs the text
exactly like JP. The 35-cell cap keeps its JP meaning (fits the screen);
it now caps hankaku labels at ~31 chars instead of ~16.

TDD: RED because tools/a0lang_label_box_width.py does not exist. GREEN =
build the module (Python geometry model + in-place byte rewrite of the
measure loop + JP baseline) and register it in build.py/patch_registry.

Faithful-model note (feedback_tdd_effective_behavior): the model here pins
the geometry the player sees (box X/W on the tilemap), and the SH-2 mini-
interpreter runs the REAL patch bytes against it.

Measure-loop engine facts (sh-elf-objdump, SH-2 BE, A0LANG.BIN @0x0600E000):
  entry 0x6012A98  r4 = tile-string ptr, r5 = arg copied to r6
  0x6012A9E  mov r5,r6 / mov #0,r5 / mov r4,r2 / mov.l 0x6012ADC,r3 (=0xFFFF)
  loop 0x6012AAA..0x6012AB4:  r1 = @r2 word; r5 += 2; until r1 == 0xFFFF
  0x6012AB6  add #-2,r2  (r2 unused afterwards)
  0x6012ABA  mov #35,r1 / cmp/hi r1,r5 / bt reject   <- the label cap
  0x6012AC2  jsr FUN_06012AF4 (r4=string, r5=cells, r6=arg)
  pool 0x6012ADA = 0x0000 (alignment pad), 0x6012ADC = 0x0000FFFF (long,
  referenced ONLY by the mov.l above — both freed by the rewrite).
  No branch from anywhere in A0LANG targets inside 0x4A9E..0x4AB8.
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
)

# ── Engine constants (from the disassembly + Ymir captures) ─────────────────
NARROW_LO = HANKAKU_BASE   # 1265 — same band as a0lang_field_hankaku_step
NARROW_HI = 1419
CAP_CELLS = 35             # JP reject threshold (mov #35 @0x6012ABA, kept)
BOX_PAD = 4                # descriptor W = cells + 4 (FUN_06012AF4 @0x6012B42)
CENTER = 18                # descriptor X = 18 - cells/2 (@0x6012B80)

MEASURE_OFF = 0x4A9E       # file offset of the rewritten measure loop
MEASURE_LEN = 0x1C         # 14 words: 0x4A9E..0x4AB9, cap @0x4ABA untouched
POOL_NARROW_OFF = 0x4ADA   # pad word            -> 0x04F1 (1265)
POOL_BAND_OFF = 0x4ADC     # freed FFFF-long hi  -> 0x009A (154 = HI-LO)
CAP_OFF = 0x4ABA           # first untouched word (mov #35,r1)


# ── Reference geometry model (the REQUIREMENT) ──────────────────────────────
def _ref_is_narrow(tile):
    return NARROW_LO <= tile <= NARROW_HI


def _ref_cells(tiles):
    """Tilemap cells the label text occupies = what the renderer draws."""
    return sum(1 if _ref_is_narrow(t) else 2 for t in tiles)


def _ref_geometry(tiles):
    """(accepted, box_x, box_w) as the player sees it.

    Mirrors FUN_06012A98 (cap) + FUN_06012AF4 (stack descriptor build).
    """
    cells = _ref_cells(tiles)
    if cells > CAP_CELLS:
        return (False, None, None)
    return (True, CENTER - (cells >> 1), cells + BOX_PAD)


def _jp_ref_cells(tiles):
    """The JP width-blind measure: 2 cells per word, no exceptions."""
    return 2 * len(tiles)


def _label_tiles(text):
    return [HANKAKU_TILE_MAP[c] for c in text]


# ── Attempt to import the (not-yet-built) module ────────────────────────────
try:
    import a0lang_label_box_width as MOD  # noqa: E402
    MODULE_PRESENT = True
    IMPORT_ERROR = None
except Exception as exc:                   # ModuleNotFoundError while RED
    MOD = None
    MODULE_PRESENT = False
    IMPORT_ERROR = exc


class TestModuleExists(unittest.TestCase):
    """RED sentinel — names the Red state so Red->Green intent is legible."""

    def test_module_is_built(self):
        self.assertTrue(
            MODULE_PRESENT,
            "RED: tools/a0lang_label_box_width.py not built yet "
            f"({IMPORT_ERROR}). GREEN = create it with label_box_cells / "
            "label_box_geometry matching the reference model in this test, "
            "plus the in-place A0LANG measure-loop rewrite + JP baseline.")

    def test_module_exposes_api(self):
        if not MODULE_PRESENT:
            self.skipTest("module absent — covered by test_module_is_built")
        for name in ('label_box_cells', 'label_box_geometry',
                     'A0LANG_LABEL_BOX_WIDTH',
                     'A0LANG_LABEL_BOX_WIDTH_JP_BASELINE'):
            self.assertTrue(hasattr(MOD, name), f"module missing {name}")


class TestGeometryModel(unittest.TestCase):
    """The heart of the requirement: the box hugs the width-class sum."""

    def test_church_of_laffel_box_hugs(self):
        """THE BUG, pinned: 16 hankaku glyphs must give a 20-cell box at
        X=10 (centred), not the width-blind 36-cell box at X=2."""
        tiles = _label_tiles('Church of Laffel')
        self.assertEqual(len(tiles), 16)
        self.assertEqual(_ref_cells(tiles), 16)
        self.assertEqual(_ref_geometry(tiles), (True, 10, 20))
        # the JP width-blind measure is what the broken build computes today
        self.assertEqual(_jp_ref_cells(tiles), 32)     # -> W=36 @X=2 (the bug)

    def test_jp_zenkaku_label_geometry_unchanged(self):
        """A JP-style all-wide string measures exactly as the JP binary did:
        ラフェルの都・教会 = 9 zenkaku glyphs -> 18 cells -> W=22 @X=9, the
        values captured live in the JP Ymir run (uidbg_jp.log + wram dump)."""
        tiles = [500] * 9                       # any out-of-band tile is wide
        self.assertEqual(_ref_cells(tiles), _jp_ref_cells(tiles))
        self.assertEqual(_ref_geometry(tiles), (True, 9, 22))

    def test_mixed_width_accumulates(self):
        tiles = [HANKAKU_TILE_MAP['H'], 7, HANKAKU_TILE_MAP['P']]   # 1+2+1
        self.assertEqual(_ref_cells(tiles), 4)
        self.assertEqual(_ref_geometry(tiles), (True, 16, 8))

    def test_cap_is_on_cells_not_glyphs(self):
        """The 35-cell cap keeps its JP meaning (fits on screen). 31 narrow
        glyphs (31 cells) now fit; 36 cells still reject."""
        ok = [NARROW_LO] * 31
        self.assertEqual(_ref_geometry(ok), (True, 3, 35))
        at_cap = [500] * 17 + [NARROW_LO]                    # 35 cells
        self.assertEqual(_ref_geometry(at_cap), (True, 1, 39))
        over = [500] * 18                                    # 36 cells
        self.assertEqual(_ref_geometry(over), (False, None, None))

    def test_empty_label(self):
        self.assertEqual(_ref_geometry([]), (True, 18, 4))

    @unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
    def test_module_model_matches_reference(self):
        cases = [
            _label_tiles('Church of Laffel'),
            _label_tiles('Castle of Larcuss'),
            [500] * 9,
            [HANKAKU_TILE_MAP['H'], 7, HANKAKU_TILE_MAP['P']],
            [NARROW_LO, NARROW_HI, NARROW_LO - 1, NARROW_HI + 1],
            [NARROW_LO] * 31,
            [500] * 18,
            [],
        ]
        for tiles in cases:
            self.assertEqual(MOD.label_box_cells(tiles), _ref_cells(tiles),
                             f"label_box_cells mismatch for {tiles}")
            self.assertEqual(MOD.label_box_geometry(tiles),
                             _ref_geometry(tiles),
                             f"label_box_geometry mismatch for {tiles}")

    @unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
    def test_measure_agrees_with_renderer_model(self):
        """Measurer and renderer MUST share one width class: the box hugs
        only if both count the same cells (single source of truth)."""
        import a0lang_field_hankaku_step as STEP
        for text in ('Church of Laffel', 'Castle', 'Village of Zare'):
            tiles = _label_tiles(text)
            self.assertEqual(MOD.label_box_cells(tiles),
                             STEP.field_row_cells(tiles, width_aware=True))
        for t in [7, NARROW_LO, NARROW_HI, NARROW_LO - 1, NARROW_HI + 1,
                  1420, 1428]:
            self.assertEqual(MOD.is_narrow_tile(t), STEP.is_narrow_tile(t))


# ── JP baseline truth-lock at the measure loop ──────────────────────────────
# (file offset in A0LANG.BIN -> big-endian words, from the disasm.)
JP_MEASURE_BASELINE = bytes.fromhex(
    "6653"   # 4A9E mov r5,r6
    "e500"   # 4AA0 mov #0,r5
    "6243"   # 4AA2 mov r4,r2
    "d30d"   # 4AA4 mov.l 0x6012ADC,r3      ; 0xFFFF (its ONLY reference)
    "a002"   # 4AA6 bra 0x6012AAE
    "6141"   # 4AA8 mov.w @r4,r1            ; (delay) first word
    "6121"   # 4AAA mov.w @r2,r1            ; loop head
    "7502"   # 4AAC add #2,r5               ; THE width-blind 16px step
    "611d"   # 4AAE extu.w r1,r1
    "3130"   # 4AB0 cmp/eq r3,r1
    "8ffa"   # 4AB2 bf.s 0x6012AAA
    "7202"   # 4AB4 add #2,r2               ; (delay)
    "72fe"   # 4AB6 add #-2,r2
    "655d"   # 4AB8 extu.w r5,r5
)
JP_POOL_BASELINE = {POOL_NARROW_OFF: b'\x00\x00', POOL_BAND_OFF: b'\x00\x00'}
JP_CAP_WORD = 0xE123        # 4ABA mov #35,r1 — stays untouched

A0LANG_PATH = 'A0LANG.BIN'
A0LANG_SIZE = 158288
JP_DIR = os.environ.get('LANG3_JP_DIR')


@unittest.skipUnless(JP_DIR, "LANG3_JP_DIR not set — skipping JP-baseline checks")
class TestMeasureJPBaseline(unittest.TestCase):
    """Lock the JP bytes at the measure loop the fix rewrites."""

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

    def test_measure_loop_baseline(self):
        got = bytes(self.jp[MEASURE_OFF:MEASURE_OFF + MEASURE_LEN])
        self.assertEqual(got, JP_MEASURE_BASELINE,
                         "measure loop drifted; re-verify the disasm")

    def test_pool_words_are_free(self):
        for off, val in JP_POOL_BASELINE.items():
            self.assertEqual(bytes(self.jp[off:off + 2]), val,
                             f"pool word at 0x{off:X} not the expected pad")
        # the FFFF half of the freed long is left in place
        self.assertEqual(bytes(self.jp[0x4ADE:0x4AE0]), b'\xff\xff')

    def test_cap_untouched_word(self):
        got = (self.jp[CAP_OFF] << 8) | self.jp[CAP_OFF + 1]
        self.assertEqual(got, JP_CAP_WORD)


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestPatchDeclaration(unittest.TestCase):
    """Lock the patch shape — runs without the JP disc."""

    def test_touches_only_a0lang(self):
        self.assertEqual(list(MOD.A0LANG_LABEL_BOX_WIDTH), ['A0LANG.BIN'])

    def test_exact_region_and_pools(self):
        edits = dict(MOD.A0LANG_LABEL_BOX_WIDTH['A0LANG.BIN'])
        self.assertEqual(set(edits),
                         {MEASURE_OFF, POOL_NARROW_OFF, POOL_BAND_OFF})
        self.assertEqual(len(edits[MEASURE_OFF]), MEASURE_LEN)
        # the stream must NOT touch the cap test at 0x4ABA
        self.assertEqual(MEASURE_OFF + len(edits[MEASURE_OFF]), CAP_OFF)
        self.assertEqual(edits[POOL_NARROW_OFF], b'\x04\xF1')    # 1265
        self.assertEqual(edits[POOL_BAND_OFF], b'\x00\x9A')     # 154

    def test_baseline_covers_same_offsets_same_lengths(self):
        edits = dict(MOD.A0LANG_LABEL_BOX_WIDTH['A0LANG.BIN'])
        base = MOD.A0LANG_LABEL_BOX_WIDTH_JP_BASELINE
        self.assertEqual(set(base), set(edits))
        for off in edits:
            self.assertEqual(len(base[off]), len(edits[off]),
                             f"baseline length mismatch at 0x{off:X}")

    def test_baseline_matches_pinned_words(self):
        base = MOD.A0LANG_LABEL_BOX_WIDTH_JP_BASELINE
        self.assertEqual(base[MEASURE_OFF], JP_MEASURE_BASELINE)
        for off, val in JP_POOL_BASELINE.items():
            self.assertEqual(base[off], val)

    def test_band_constants_track_font_tools(self):
        self.assertEqual(MOD.NARROW_LO, HANKAKU_BASE)           # 1265
        self.assertEqual(MOD.NARROW_HI - MOD.NARROW_LO, 154)
        for t in HANKAKU_TILES:
            self.assertTrue(MOD.is_narrow_tile(t))
        self.assertFalse(MOD.is_narrow_tile(1420))
        self.assertFalse(MOD.is_narrow_tile(1428))

    def test_registered_in_build(self):
        import build
        self.assertIn('a0lang_label_box_width', build.ENGINE_MODULE_DICTS)
        self.assertIs(build.ENGINE_MODULE_DICTS['a0lang_label_box_width'],
                      MOD.A0LANG_LABEL_BOX_WIDTH)

    def test_registered_in_patch_registry(self):
        import patch_registry
        self.assertIn('a0lang_label_box_width',
                      patch_registry.ENGINE_PATCH_MODULES)

    def test_disjoint_from_other_a0lang_modules(self):
        import build
        ours = set()
        for off, chunk in MOD.A0LANG_LABEL_BOX_WIDTH['A0LANG.BIN']:
            ours |= set(range(off, off + len(chunk)))
        for name, module in build.ENGINE_MODULE_DICTS.items():
            if name == 'a0lang_label_box_width':
                continue
            for off, chunk in module.get('A0LANG.BIN', []):
                theirs = set(range(off, off + len(chunk)))
                self.assertFalse(ours & theirs,
                                 f"offset collision with {name}")


# ── SH-2 mini-interpreter (subset used by both measure loops) ───────────────
def _sx8(v):
    return v - 0x100 if v & 0x80 else v


def _sx16(v):
    return v - 0x10000 if v & 0x8000 else v


class _Sh2Measure:
    """Executes the measure loop (MEASURE_OFF until CAP_OFF) over a synthetic
    image and returns the register state at the cap test.

    Faithful-model note: this runs the REAL patch bytes (and the REAL JP
    bytes), so the assertions pin effective engine behavior."""
    STR = 0x100000

    def __init__(self, image):
        self.image = image

    def run(self, tiles, arg=0x12):
        ram = {}
        for i, t in enumerate(tiles):
            ram[self.STR + 2 * i] = t & 0xFFFF
        ram[self.STR + 2 * len(tiles)] = 0xFFFF
        R = [0] * 16
        R[4] = self.STR
        R[5] = arg
        self.R, self.ram, self.T = R, ram, 0
        pc, steps = MEASURE_OFF, 0
        while pc != CAP_OFF:
            steps += 1
            if steps > 100000:
                raise AssertionError('interpreter runaway (bad branch?)')
            pc = self._step(pc)
        return R

    def _rw(self, addr):
        if addr in self.ram:
            return self.ram[addr]
        return (self.image[addr] << 8) | self.image[addr + 1]

    def _rl(self, addr):
        return (self._rw(addr) << 16) | self._rw(addr + 2)

    def _exec(self, pc):
        R, w = self.R, (self.image[pc] << 8) | self.image[pc + 1]
        n, m = (w >> 8) & 0xF, (w >> 4) & 0xF
        M = 0xFFFFFFFF
        if w == 0x0009:                                    # nop
            pass
        elif (w & 0xF00F) == 0x6003:                       # mov Rm,Rn
            R[n] = R[m]
        elif (w & 0xF000) == 0xE000:                       # mov #imm8,Rn
            R[n] = _sx8(w & 0xFF) & M
        elif (w & 0xF00F) == 0x6001:                       # mov.w @Rm,Rn
            R[n] = _sx16(self._rw(R[m])) & M
        elif (w & 0xF00F) == 0x6005:                       # mov.w @Rm+,Rn
            R[n] = _sx16(self._rw(R[m])) & M
            R[m] = (R[m] + 2) & M
        elif (w & 0xF000) == 0x9000:                       # mov.w @(d,PC),Rn
            R[n] = _sx16(self._rw(pc + 4 + (w & 0xFF) * 2)) & M
        elif (w & 0xF000) == 0xD000:                       # mov.l @(d,PC),Rn
            R[n] = self._rl(((pc + 4) & ~3) + (w & 0xFF) * 4) & M
        elif (w & 0xF000) == 0x7000:                       # add #imm,Rn
            R[n] = (R[n] + _sx8(w & 0xFF)) & M
        elif (w & 0xF00F) == 0x3008:                       # sub Rm,Rn
            R[n] = (R[n] - R[m]) & M
        elif (w & 0xF00F) == 0x600D:                       # extu.w Rm,Rn
            R[n] = R[m] & 0xFFFF
        elif (w & 0xFF00) == 0x8800:                       # cmp/eq #imm,r0
            self.T = 1 if R[0] == (_sx8(w & 0xFF) & M) else 0
        elif (w & 0xF00F) == 0x3000:                       # cmp/eq Rm,Rn
            self.T = 1 if R[n] == R[m] else 0
        elif (w & 0xF00F) == 0x3006:                       # cmp/hi Rm,Rn
            self.T = 1 if R[n] > R[m] else 0
        else:
            raise AssertionError(f'unimplemented opcode {w:04X} @0x{pc:X}')

    def _step(self, pc):
        w = (self.image[pc] << 8) | self.image[pc + 1]
        hi = w >> 8
        if hi in (0x89, 0x8B):                             # bt / bf
            taken = self.T == (1 if hi == 0x89 else 0)
            return pc + 4 + _sx8(w & 0xFF) * 2 if taken else pc + 2
        if hi in (0x8D, 0x8F):                             # bt/s / bf/s
            taken = self.T == (1 if hi == 0x8D else 0)
            self._exec(pc + 2)
            return pc + 4 + _sx8(w & 0xFF) * 2 if taken else pc + 4
        if (w & 0xF000) == 0xA000:                         # bra
            d = w & 0xFFF
            if d & 0x800:
                d -= 0x1000
            self._exec(pc + 2)
            return pc + 4 + d * 2
        self._exec(pc)
        return pc + 2


def _make_image(stream, pools):
    img = bytearray(0x5000)
    img[MEASURE_OFF:MEASURE_OFF + len(stream)] = stream
    for off, val in pools.items():
        img[off:off + 2] = val
    # the cap word (first untouched instruction) as the stop sentinel
    img[CAP_OFF] = JP_CAP_WORD >> 8
    img[CAP_OFF + 1] = JP_CAP_WORD & 0xFF
    return bytes(img)


@unittest.skipUnless(MODULE_PRESENT, "module absent (RED)")
class TestExecutePatchedBytes(unittest.TestCase):
    """Run the ACTUAL patched measure loop and compare to the model."""

    @classmethod
    def setUpClass(cls):
        edits = dict(MOD.A0LANG_LABEL_BOX_WIDTH['A0LANG.BIN'])
        cls.vm = _Sh2Measure(_make_image(
            edits[MEASURE_OFF],
            {POOL_NARROW_OFF: edits[POOL_NARROW_OFF],
             POOL_BAND_OFF: edits[POOL_BAND_OFF]}))
        cls.jp_vm = _Sh2Measure(_make_image(
            JP_MEASURE_BASELINE,
            {POOL_NARROW_OFF: b'\x00\x00',
             POOL_BAND_OFF: b'\x00\x00',
             0x4ADE: b'\xff\xff'}))

    def _cells(self, vm, tiles):
        return vm.run(tiles)[5]        # r5 = measured cells at the cap test

    def test_hankaku_label_measures_narrow(self):
        tiles = _label_tiles('Church of Laffel')
        self.assertEqual(self._cells(self.vm, tiles), 16)

    def test_all_wide_string_is_jp_identical(self):
        for tiles in ([500] * 9, [7, 8, 9, 1200, 1690], [1420, 1428]):
            self.assertEqual(self._cells(self.vm, tiles),
                             self._cells(self.jp_vm, tiles),
                             f"wide-only string diverged from JP: {tiles}")

    def test_band_edges(self):
        tiles = [NARROW_LO, NARROW_HI, NARROW_LO - 1, NARROW_HI + 1]
        self.assertEqual(self._cells(self.vm, tiles), 1 + 1 + 2 + 2)

    def test_mixed_string(self):
        tiles = _label_tiles('Church of Laffel') + [7, 1428]
        self.assertEqual(self._cells(self.vm, tiles), 16 + 2 + 2)

    def test_control_words_stay_wide_like_jp(self):
        """Any non-terminator control word (e.g. 0xF600) counted 2 cells in
        JP; the patch must classify it wide too (sign-extension safe)."""
        tiles = [0xF600, 0x0000]
        self.assertEqual(self._cells(self.vm, tiles),
                         self._cells(self.jp_vm, tiles))

    def test_empty_string(self):
        self.assertEqual(self._cells(self.vm, []), 0)

    def test_call_registers_preserved(self):
        """FUN_06012AF4 is called with r4=string ptr and r6=the arg copy;
        both must survive the rewritten loop."""
        R = self.vm.run(_label_tiles('Castle'), arg=0x77)
        self.assertEqual(R[4], _Sh2Measure.STR)
        self.assertEqual(R[6], 0x77)

    def test_jp_stream_measures_width_blind(self):
        for tiles in (_label_tiles('Church of Laffel'), [500] * 9, []):
            self.assertEqual(self._cells(self.jp_vm, tiles),
                             _jp_ref_cells(tiles))

    def test_model_agrees_with_executed_bytes(self):
        for tiles in (_label_tiles('Church of Laffel'),
                      _label_tiles('Castle of Larcuss'),
                      [500] * 9,
                      [NARROW_LO, 7, NARROW_HI, 1420],
                      []):
            self.assertEqual(self._cells(self.vm, tiles),
                             MOD.label_box_cells(tiles))


if __name__ == '__main__':
    unittest.main()
