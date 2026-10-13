#!/usr/bin/env python3
"""test_name_entry_twin_glyphs.py — v4 "display twins" name-entry keyboard
(TDD guard for the whole 3-piece design, NOT YET BUILT).

════════════════════════════════════════════════════════════════════════════
RED STATE (2026-07-15): the v2 keyboard (validated, commit b776e8c) types
correctly but draws the keys bunched at 8px under a 16px positional
selector. Ralf's spec: "desenhar as letras do teclado no passo 16px mas
registrar os caracteres no passo 8px", with the key art being the HANKAKU
letterform CENTERED in the 16px tile (NOT the eagleIII-centered zenkaku
art). Both record-shaped attempts at 16px columns were withdrawn
(archive/docs/20260714_name_entry_freeze_bug.md): v1 overflowed the
192-glyph staging ring, v3 broke the 21x5 staging-slot ABI. v4 changes
NEITHER record shape NOR renderer flow — the 16px step comes from the
tile's WIDTH CLASS, and the 8px registration from a -K conversion in the
append path.
════════════════════════════════════════════════════════════════════════════

THE DESIGN (archive/docs/20260715_name_entry_twin_glyphs_handoff.md, amended
by this session's recon — the original "twins at 1435+" premise was FALSE:
1435/1436 are packed fresh bigrams and 1437+ has only 59 fragmented free
tiles. The corrected geometry keeps everything inside V08_RESERVED_TILES):

  Piece 1 — the narrow band DECLARED top shrinks 1419 -> 1349 (content ends
    at 1344; the headroom tiles were blank and unreferenced), and the freed
    wide-class range hosts the TWIN BAND: twin(c) = hankaku(c) + TWIN_K,
    one fixed K for all 65 keyboard chars (A-Z a-z 0-9 ! ? space), art =
    the hankaku 8px letterform shifted 4px right (centered in the 16px
    tile). Wide class => the field-UI renderer steps 16px per key with
    ZERO code change; slot ABI intact (still 5 drawn glyphs/row).
  Piece 2 — fntsys14 records swap HANKAKU_TILE_MAP -> TWIN_TILE_MAP.
  Piece 3 — the append fetch block (PROG_4 file 0x8D2A..0x8D35) becomes a
    jmp-stub into a FONT.BIN code cave that redoes the fetch and subtracts
    TWIN_K, so the NAME BUFFER receives hankaku tiles (8px render, F600 and
    save untouched); the now-redundant fetch at 0x8D56 becomes a nop.

ENGINE FACTS (sh-elf-objdump over the JP PROG_4, load 0x06089000, this
session — cross-locked below by TestJPBaseline when LANG3_JP_DIR is set):

  0x8D2A d127  mov.l @(pc),r1 ! 0x6095609 (col)   ┐ the fetch-address block
  0x8D2C 6110  mov.b @r1,r1                       │ r2 = keyboard-list entry
  0x8D2E 5223  mov.l @(12,r2),r2  ; record ptr    │ (computed at 0x8D14..28,
  0x8D30 311c  add r1,r1          ; col*2         │  untouched)
  0x8D32 6613  mov r1,r6                          │
  0x8D34 362c  add r2,r6          ; r6=&rec[col]  ┘
  0x8D36 344c  add r4,r4          ; r4 = pos*2 (r4/r5 LIVE across the block)
  ...    (r6 untouched 0x8D36..0x8D55; verified in the full disasm)
  0x8D56 6661  mov.w @r6,r6       ; THE fetch
  0x8D5A 0365  mov.w r6,@(r0,r3)  ; name[pos] = r6
  No branch in PROG_4 targets inside 0x8D2A..0x8D35 or 0x8D56 (scanned).
  Free regs across the block: r0,r1,r2,r6 (r3/r7 reloaded after; r4=pos and
  r5=&posvar must be preserved). Button rows never reach the append (block-2
  row-5 dispatch at 0x8C94/0x8CCE) — but the incondicional -K still demands
  every FETCHABLE cell (records 0-18) be a twin, guarded here.

Faithful-model note (feedback_tdd_effective_behavior): the append test
EXECUTES the real patched bytes (stub + cave + untouched JP tail) and pins
what reaches the name buffer — the tile the player's F600 will render.
"""
import struct
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / 'tools'))

import font_tools as ft  # noqa: E402

# ── The spec's fixed points (everything else derives) ───────────────────────
KEYBOARD_CHARS = (
    [chr(c) for c in range(ord('A'), ord('Z') + 1)]
    + [chr(c) for c in range(ord('a'), ord('z') + 1)]
    + [str(d) for d in range(10)]
    + ['!', '?', ' ']
    + ['ä', 'ö', 'ü']               # 2026-10-12: Diehärte, Böser, Rigüler
    + ['Ä', 'Ö', 'Ü']
    + ['-']                         # 2026-10-13: hyphen key
)                                   # the exact fetchable key set (72 chars)
TWIN_BLOCK = range(1350, 1435)      # band + TWIN_K, for every band slot
CAVE_BLOCK = range(1454, 1470)      # font caves, scratch and nakaguro
PROG4_PATH = 'LANG/PROG_4.BIN'
PROG4_LOAD_BASE = 0x06089000
STUB_OFF = 0x8D2A                   # 6-word fetch block -> jmp stub
FETCH_OFF = 0x8D56                  # mov.w @r6,r6 -> nop
STUB_JP = bytes.fromhex('d127 6110 5223 311c 6613 362c'.replace(' ', ''))
FETCH_JP = bytes.fromhex('6661')
COL_VAR = 0x06095609                # keyboard col (byte)
POS_VAR = 0x0609560B                # name insert pos (byte)
NAME_BUF = 0x06034D90               # 8 tiles + FFFF
RETURN_ADDR = PROG4_LOAD_BASE + 0x8D36   # where the cave must come back

# JP bytes 0x8D36..0x8D5F (the untouched tail the executor runs through) and
# the two pool longs it reads (0x8D9C: name buffer, 0x8DA0: 0xFFFF) — engine
# facts from the disasm, disc-locked by TestJPBaseline.
TAIL_JP = bytes.fromhex(
    '344c d318 d219 6043 013d 611d 3120 8f03 6723 6133 7102 0175'
    '6150 621c 6023 300c 6661 7101 0365 a07d 2510'.replace(' ', ''))
TAIL_OFF = 0x8D36
# 0x8D9C/0x8DA0: name buffer + FFFF (read by the tail); 0x8DC8: &col var
# (read by the JP 0x8D2A `mov.l @(pc),r1` — only the unpatched run needs it).
POOL_JP = {0x8D9C: 0x06034D90, 0x8DA0: 0x0000FFFF, 0x8DC8: COL_VAR}

# ── Attempt the (not-yet-built) modules ──────────────────────────────────────
CAVE_ERR = CONV_ERR = None
try:
    import name_twin_cave as CAVE
except Exception as exc:
    CAVE, CAVE_ERR = None, exc
try:
    import prog4_name_twin_convert as CONV
except Exception as exc:
    CONV, CONV_ERR = None, exc
TWIN_PRESENT = hasattr(ft, 'TWIN_TILE_MAP')

from a0lang_field_hankaku_step import (      # noqa: E402
    NARROW_LO, NARROW_HI, is_narrow_tile)
import balloon_zenkaku_cave as BALLOON       # noqa: E402


class TestModulesExist(unittest.TestCase):
    """RED sentinels — name the Red state."""

    def test_twin_map_is_built(self):
        self.assertTrue(
            TWIN_PRESENT,
            'RED: font_tools.TWIN_TILE_MAP not built. GREEN = twin band '
            '(hankaku + fixed K, centered art) above the shrunk narrow band.')

    def test_cave_module_is_built(self):
        self.assertIsNotNone(
            CAVE, f'RED: tools/name_twin_cave.py not built ({CAVE_ERR}).')

    def test_convert_module_is_built(self):
        self.assertIsNotNone(
            CONV, 'RED: tools/prog4_name_twin_convert.py not built '
            f'({CONV_ERR}).')


@unittest.skipUnless(TWIN_PRESENT, 'twin map absent (RED)')
class TestTwinBandGeometry(unittest.TestCase):
    """Piece 1a — the twin band layout: parallel to hankaku, wide class."""

    def test_covers_exactly_the_keyboard_set(self):
        self.assertEqual(set(ft.TWIN_TILE_MAP), set(KEYBOARD_CHARS))

    def test_one_fixed_k_for_every_char(self):
        for ch, t in ft.TWIN_TILE_MAP.items():
            self.assertEqual(t - ft.HANKAKU_TILE_MAP[ch], ft.TWIN_K,
                             f'twin({ch!r}) must be hankaku + TWIN_K')

    def test_twin_base_sits_right_above_the_narrow_band(self):
        self.assertEqual(ft.TWIN_BASE, ft.HANKAKU_BASE + ft.TWIN_K)
        self.assertEqual(ft.TWIN_BASE, NARROW_HI + 1)

    def test_twins_are_wide_class_for_both_renderers(self):
        for ch, t in ft.TWIN_TILE_MAP.items():
            self.assertFalse(is_narrow_tile(t),
                             f'twin({ch!r})={t} must draw 16px (field UI)')
            self.assertTrue(t > BALLOON.HANKAKU_HI,
                            f'twin({ch!r})={t} must be wide for the balloon')

    def test_the_twin_block_holds_only_twins(self):
        """Red state 2026-10-12: the caves, the balloon scratch and the
        nakaguro sat at 1417..1434, so the twins of the band slots 67..84
        (ä ö ü among them) had nowhere to go. Every band slot now owns
        band + TWIN_K; the rest moved to CAVE_BLOCK."""
        self.assertEqual(TWIN_BLOCK.start, ft.HANKAKU_BASE + ft.TWIN_K)
        self.assertEqual(len(TWIN_BLOCK), ft.TWIN_K)
        others = {BALLOON.SCRATCH_TILE, ft.NAKAGURO_TILE}
        others |= set(range(BALLOON.CAVE_TILE, BALLOON.CAVE_TILE + BALLOON.CAVE_TILES))
        others |= set(range(CAVE.NAME_TWIN_CAVE_TILE,
                            CAVE.NAME_TWIN_CAVE_TILE + CAVE.NAME_TWIN_CAVE_TILES))
        import width_class as WC
        import a0lang_save_name_pack as NP
        others |= set(range(WC.WIDTH_CAVE_TILE, WC.WIDTH_CAVE_TILE + WC.WIDTH_CAVE_TILES))
        others |= set(range(NP.PACK_TILE, NP.PACK_TILE + NP.PACK_TILES))
        others |= set(range(NP.UNPACK_TILE, NP.UNPACK_TILE + NP.UNPACK_TILES))
        self.assertFalse(others & set(TWIN_BLOCK))
        self.assertTrue(others <= set(CAVE_BLOCK), sorted(others - set(CAVE_BLOCK)))
        self.assertTrue(set(CAVE_BLOCK) <= ft.V08_RESERVED_TILES)

    def test_the_packer_never_lands_on_the_cave_block(self):
        layout = ft.build_bigram_layout()
        self.assertFalse(set(layout.values()) & set(CAVE_BLOCK))

    def test_twins_inside_the_packer_exclusion(self):
        twins = set(ft.TWIN_TILE_MAP.values())
        self.assertTrue(twins <= ft.V08_RESERVED_TILES,
                        'twin band must be packer-excluded (spill lesson)')

    def test_no_collision_with_any_composed_tile(self):
        twins = set(ft.TWIN_TILE_MAP.values())
        for name, used in (
                ('bigram map', set(ft.BIGRAM_TILE_MAP.values())),
                ('char map', set(ft.CHAR_TILE_MAP.values())),
                ('preserved', set(ft.PRESERVED_TILES)),
                ('hankaku band', set(ft.HANKAKU_TILE_MAP.values())),
                ('nakaguro', {ft.NAKAGURO_TILE}),
                ('balloon cave', set(range(BALLOON.SCRATCH_TILE,
                                           BALLOON.CAVE_TILE
                                           + BALLOON.CAVE_TILES)))):
            self.assertFalse(twins & used, f'twin band collides with {name}')

    def test_hankaku_content_still_fits_the_shrunk_band(self):
        self.assertLessEqual(max(ft.HANKAKU_TILE_MAP.values()), NARROW_HI,
                             'shrinking the band must not evict content')


class TestBandShrinkConsistency(unittest.TestCase):
    """Piece 1b — every module that encodes the class bound agrees. The
    narrow band is [1265..1349]: content tops at 1344, +5 growth slots."""

    def test_new_band_top(self):
        self.assertEqual(NARROW_HI, 1349)
        self.assertEqual(NARROW_LO, ft.HANKAKU_BASE)

    def test_balloon_cave_agrees(self):
        self.assertEqual(BALLOON.HANKAKU_HI, NARROW_HI)
        self.assertEqual(BALLOON.HANKAKU_LO, NARROW_LO)

    def test_label_box_calls_the_cave_that_encodes_the_same_band(self):
        # since 2026-10-08 the measurers ask tools/width_class.py's font cave
        import a0lang_label_box_width as LB
        import width_class as WC
        edits = dict(LB.A0LANG_LABEL_BOX_WIDTH['A0LANG.BIN'])
        self.assertEqual(edits[LB.POOL_LONG_OFF],
                         WC.WIDTH_CAVE_ADDR.to_bytes(4, 'big'))
        self.assertEqual((WC.NARROW_LO, WC.NARROW_HI), (NARROW_LO, NARROW_HI))
        blob = WC.cave_blob()
        self.assertTrue(blob.endswith(NARROW_LO.to_bytes(2, 'big')
                                      + (NARROW_HI - NARROW_LO + 1).to_bytes(2, 'big')))

    def test_field_step_stream_encodes_the_same_size(self):
        """The rewrite loads the size as `mov #imm; add r1,r1` — the size
        must stay even and imm*2 must equal NARROW_HI - NARROW_LO."""
        size = NARROW_HI - NARROW_LO
        self.assertEqual(size % 2, 0)
        import a0lang_field_hankaku_step as FS
        edits = dict(FS.A0LANG_FIELD_HANKAKU_STEP['A0LANG.BIN'])
        stream = edits[FS.PHASE2_REWRITE_OFF]
        want = (0xE100 | (size // 2)).to_bytes(2, 'big') + b'\x31\x1c'
        self.assertIn(want, stream,
                      'mov #size/2; add r1,r1 not found in the Phase-2 stream')


JP_DIR = None
import os                                    # noqa: E402
JP_DIR = os.environ.get('LANG3_JP_DIR')


def _jp_font():
    from iso_tools import build_file_index, extract_file_data
    cands = (list(Path(JP_DIR).glob('*rack*01*.bin'))
             or list(Path(JP_DIR).glob('*.bin')))
    image = cands[0].read_bytes()
    e = build_file_index(image)['LANG/FONT.BIN']
    return extract_file_data(image, e.extent, e.size)


@unittest.skipUnless(TWIN_PRESENT and JP_DIR, 'twin map or JP disc absent')
class TestTwinArt(unittest.TestCase):
    """Piece 1c — the GENERATED font carries the centered-4px transform of
    the hankaku art (Ralf: hankaku letterform centered, NOT eagleIII)."""

    @classmethod
    def setUpClass(cls):
        cls.font = ft.generate_english_font(_jp_font())

    def _tile(self, idx):
        return self.font[idx * 32:(idx + 1) * 32]

    def test_twin_art_is_the_centered_hankaku_letterform(self):
        for ch, twin in sorted(ft.TWIN_TILE_MAP.items()):
            hk = self._tile(ft.HANKAKU_TILE_MAP[ch])
            got = self._tile(twin)
            for r in range(16):
                half = hk[r * 2]          # hankaku art: left byte, right 0
                self.assertEqual(hk[r * 2 + 1], 0,
                                 f'hankaku {ch!r} row {r} not left-packed')
                self.assertEqual(got[r * 2], (half >> 4) & 0x0F,
                                 f'twin {ch!r} row {r} left half')
                self.assertEqual(got[r * 2 + 1], (half << 4) & 0xF0,
                                 f'twin {ch!r} row {r} right half')

    def test_twin_letters_have_pixels(self):
        for ch in 'AZaz09!?':
            twin = ft.TWIN_TILE_MAP[ch]
            pixels = sum(bin(b).count('1') for b in self._tile(twin))
            self.assertGreater(pixels, 5, f'twin {ch!r} looks blank')

    def test_twin_space_is_blank(self):
        self.assertEqual(self._tile(ft.TWIN_TILE_MAP[' ']), bytes(32))

    def test_cave_blob_rides_the_font(self):
        blob = CAVE.cave_blob()
        base = CAVE.NAME_TWIN_CAVE_TILE * 32
        self.assertEqual(self.font[base:base + len(blob)], blob)


@unittest.skipUnless(TWIN_PRESENT, 'twin map absent (RED)')
class TestKeyboardRecordsUseTwins(unittest.TestCase):
    """Piece 2 — records swap to twins; slot ABI untouched (5 cells+FFFF);
    every FETCHABLE cell is a twin (the incondicional -K contract)."""

    @classmethod
    def setUpClass(cls):
        from fntsys14_hankaku_keyboard import (hankaku_keyboard_records,
                                               KEYBOARD_ROWS)
        cls.buttons = [b'\x05\xd0\x00\x00\x05\xd1\x00\x00\x05\xd2\xff\xff'] * 2
        cls.recs = hankaku_keyboard_records(cls.buttons)
        cls.rows = KEYBOARD_ROWS

    @staticmethod
    def _cells(rec):
        return [w for (w,) in struct.iter_unpack('>H', rec)]

    def test_rows_carry_twin_tiles_at_jp_positions(self):
        space = ft.TWIN_TILE_MAP[' ']
        for i, row in enumerate(self.rows):
            cells = self._cells(self.recs[i])
            for col, ch in enumerate(row):
                want = space if ch == '_' else ft.TWIN_TILE_MAP[ch]
                self.assertEqual(cells[col], want,
                                 f'rec {i} col {col}: twin cell wrong')

    def test_rows_stay_slot_locked(self):
        for i in range(19):
            self.assertEqual(len(self.recs[i]), 12,
                             f'rec {i}: 5 cells + FFFF (slot ABI)')
            self.assertEqual(self.recs[i][-2:], b'\xff\xff')

    def test_every_fetchable_cell_is_a_twin(self):
        """The cave subtracts K UNCONDITIONALLY: any non-twin fetchable
        cell would register a corrupt tile."""
        twins = set(ft.TWIN_TILE_MAP.values())
        for i in range(19):
            for col, cell in enumerate(self._cells(self.recs[i])[:5]):
                self.assertIn(cell, twins,
                              f'rec {i} col {col}: fetchable cell not a twin')

    def test_buttons_pass_through(self):
        self.assertEqual(self.recs[19:], self.buttons)


@unittest.skipIf(CAVE is None, 'cave module absent (RED)')
class TestConvertCave(unittest.TestCase):
    """Piece 3a — the cave: placement, size and pool contract."""

    def test_cave_tiles_sit_in_the_cave_block(self):
        self.assertEqual(CAVE.NAME_TWIN_CAVE_TILE, 1467)
        self.assertEqual(CAVE.NAME_TWIN_CAVE_TILES, 2)

    def test_cave_addr_is_the_font_lwram_slot(self):
        self.assertEqual(CAVE.NAME_TWIN_CAVE_ADDR, 0x00288000 + 1467 * 32)
        self.assertEqual(CAVE.NAME_TWIN_CAVE_ADDR % 4, 0)

    def test_cave_inside_the_packer_exclusion(self):
        tiles = set(range(CAVE.NAME_TWIN_CAVE_TILE,
                          CAVE.NAME_TWIN_CAVE_TILE + CAVE.NAME_TWIN_CAVE_TILES))
        self.assertTrue(tiles <= ft.V08_RESERVED_TILES)
        self.assertFalse(tiles & set(ft.PRESERVED_TILES))
        self.assertFalse(tiles & set(ft.BIGRAM_TILE_MAP.values()))
        self.assertNotIn(ft.NAKAGURO_TILE, tiles)

    def test_blob_fits_its_tiles(self):
        blob = CAVE.cave_blob()
        self.assertLessEqual(len(blob), CAVE.NAME_TWIN_CAVE_TILES * 32)

    def test_pool_constants(self):
        """The cave's data: col var, return address, and K = font_tools'."""
        blob = CAVE.cave_blob()
        self.assertIn(COL_VAR.to_bytes(4, 'big'), blob)
        self.assertIn(RETURN_ADDR.to_bytes(4, 'big'), blob)
        self.assertEqual(CAVE.TWIN_K, ft.TWIN_K)
        self.assertIn(ft.TWIN_K.to_bytes(2, 'big'), blob)


@unittest.skipIf(CONV is None, 'convert module absent (RED)')
class TestProg4Patch(unittest.TestCase):
    """Piece 3b — the call-site patch shape."""

    def setUp(self):
        self.edits = dict(CONV.PROG4_NAME_TWIN_CONVERT[PROG4_PATH])

    def test_touches_only_prog4(self):
        self.assertEqual(list(CONV.PROG4_NAME_TWIN_CONVERT), [PROG4_PATH])

    def test_exact_sites(self):
        self.assertEqual(set(self.edits), {STUB_OFF, FETCH_OFF})

    def test_stub_layout(self):
        """6 words: mov.l pool,r0 / jmp @r0 / nop / <cave addr> / nop.
        The pool long rides the DEAD words after the jmp delay slot —
        nothing executes it (the cave returns straight to 0x8D36)."""
        stub = self.edits[STUB_OFF]
        self.assertEqual(len(stub), 12, 'stub must fill 0x8D2A..0x8D35 exactly')
        self.assertEqual(stub[0:2], bytes.fromhex('d001'))   # mov.l @(1,pc),r0
        self.assertEqual(stub[2:4], bytes.fromhex('402b'))   # jmp @r0
        self.assertEqual(stub[4:6], bytes.fromhex('0009'))   # (delay) nop
        self.assertEqual(stub[6:10],
                         CAVE.NAME_TWIN_CAVE_ADDR.to_bytes(4, 'big'))
        self.assertEqual(stub[10:12], bytes.fromhex('0009'))  # dead filler

    def test_stub_pool_alignment(self):
        """mov.l @(1,pc) at load 0x06091D2A reads ((pc+4)&~3)+4 = 0x8D30."""
        ea = ((PROG4_LOAD_BASE + STUB_OFF + 4) & ~3) + 1 * 4
        self.assertEqual(ea, PROG4_LOAD_BASE + STUB_OFF + 6)

    def test_fetch_becomes_nop(self):
        self.assertEqual(self.edits[FETCH_OFF], bytes.fromhex('0009'))

    def test_baseline_covers_same_offsets_same_lengths(self):
        base = CONV.PROG4_NAME_TWIN_CONVERT_JP_BASELINE
        self.assertEqual(set(base), set(self.edits))
        for off in self.edits:
            self.assertEqual(len(base[off]), len(self.edits[off]))
        self.assertEqual(base[STUB_OFF], STUB_JP)
        self.assertEqual(base[FETCH_OFF], FETCH_JP)

    def test_model_helpers(self):
        for ch, t in ft.TWIN_TILE_MAP.items():
            self.assertTrue(CONV.is_twin_tile(t))
            self.assertEqual(CONV.twin_to_hankaku(t), ft.HANKAKU_TILE_MAP[ch])

    def test_registered_in_build(self):
        import build
        self.assertIn('prog4_name_twin_convert', build.ENGINE_MODULE_DICTS)
        self.assertIs(build.ENGINE_MODULE_DICTS['prog4_name_twin_convert'],
                      CONV.PROG4_NAME_TWIN_CONVERT)

    def test_registered_in_patch_registry(self):
        import patch_registry
        self.assertIn('prog4_name_twin_convert',
                      patch_registry.ENGINE_PATCH_MODULES)

    def test_disjoint_from_other_prog4_modules(self):
        import build
        ours = set()
        for off, chunk in CONV.PROG4_NAME_TWIN_CONVERT[PROG4_PATH]:
            ours |= set(range(off, off + len(chunk)))
        for name, module in build.ENGINE_MODULE_DICTS.items():
            if name == 'prog4_name_twin_convert':
                continue
            for off, chunk in module.get(PROG4_PATH, []):
                theirs = set(range(off, off + len(chunk)))
                self.assertFalse(ours & theirs,
                                 f'offset collision with {name}')

    def test_cap_and_cursor_sites_untouched(self):
        for off in (0x8D06, 0x908A, 0x911E):
            for site, chunk in self.edits.items():
                self.assertNotIn(off, range(site, site + len(chunk)))


# ── SH-2 mini-interpreter (sparse memory; runs stub + cave + JP tail) ────────
def _sx8(v):
    return v - 0x100 if v & 0x80 else v


def _sx16(v):
    return v - 0x10000 if v & 0x8000 else v


class _Sh2Append:
    """Executes the append path from load 0x06091D2A until the JP `bra` at
    0x06091D5C hands off (its delay slot — the pos++ writeback — included).

    Faithful-model note: this runs the REAL patch bytes (stub + assembled
    cave + the untouched JP tail), so the assertions pin what actually
    lands in the name buffer."""
    ENTRY = PROG4_LOAD_BASE + STUB_OFF
    STOP = 0x06091E5A                 # the bra target (outside our region)
    REC = 0x06060000                  # synthetic record ptr
    ENTRY_ADDR = 0x06095500           # synthetic keyboard-list entry

    def __init__(self, prog4_region, cave_blob):
        self.mem = {}
        for i, b in enumerate(prog4_region):
            self.mem[PROG4_LOAD_BASE + STUB_OFF + i] = b
        for off, val in POOL_JP.items():
            for i, b in enumerate(val.to_bytes(4, 'big')):
                self.mem[PROG4_LOAD_BASE + off + i] = b
        if cave_blob is not None:
            for i, b in enumerate(cave_blob):
                self.mem[CAVE.NAME_TWIN_CAVE_ADDR + i] = b

    def run(self, cells, col, pos, name=()):
        m = dict(self.mem)
        for i, c in enumerate(cells):
            m[self.REC + 2 * i] = c >> 8
            m[self.REC + 2 * i + 1] = c & 0xFF
        for i, b in enumerate(self.REC.to_bytes(4, 'big')):
            m[self.ENTRY_ADDR + 12 + i] = b
        m[COL_VAR] = col
        m[POS_VAR] = pos
        buf = list(name) + [0xFFFF]
        for i, w in enumerate(buf):
            m[NAME_BUF + 2 * i] = w >> 8
            m[NAME_BUF + 2 * i + 1] = w & 0xFF
        R = [0] * 16
        R[2] = self.ENTRY_ADDR        # contract at 0x8D2A (set at 0x8D26-28)
        R[4] = pos                    # set at 0x8D0E (mov r3,r4)
        R[5] = POS_VAR                # set at 0x8D02
        self.R, self.m, self.T = R, m, 0
        pc, steps = self.ENTRY, 0
        while pc != self.STOP:
            steps += 1
            if steps > 1000:
                raise AssertionError(f'interpreter runaway at 0x{pc:X}')
            pc = self._step(pc)
        return {
            'name': [self._rw(NAME_BUF + 2 * i) for i in range(len(buf) + 1)],
            'pos': self.m[POS_VAR],
            'r4': R[4], 'r5': R[5],
        }

    def _rb(self, a):
        if a not in self.m:
            raise AssertionError(f'read of unmapped byte 0x{a:X}')
        return self.m[a]

    def _rw(self, a):
        return (self._rb(a) << 8) | self._rb(a + 1)

    def _rl(self, a):
        return (self._rw(a) << 16) | self._rw(a + 2)

    def _wb(self, a, v):
        self.m[a] = v & 0xFF

    def _ww(self, a, v):
        self._wb(a, v >> 8)
        self._wb(a + 1, v)

    def _exec(self, pc):
        R, w = self.R, self._rw(pc)
        n, m = (w >> 8) & 0xF, (w >> 4) & 0xF
        M = 0xFFFFFFFF
        if w == 0x0009:                                    # nop
            pass
        elif (w & 0xF00F) == 0x6003:                       # mov Rm,Rn
            R[n] = R[m]
        elif (w & 0xF000) == 0xE000:                       # mov #imm8,Rn
            R[n] = _sx8(w & 0xFF) & M
        elif (w & 0xF00F) == 0x6000:                       # mov.b @Rm,Rn
            R[n] = _sx8(self._rb(R[m])) & M
        elif (w & 0xF00F) == 0x6001:                       # mov.w @Rm,Rn
            R[n] = _sx16(self._rw(R[m])) & M
        elif (w & 0xF000) == 0x5000:                       # mov.l @(d,Rm),Rn
            R[n] = self._rl(R[m] + (w & 0xF) * 4) & M
        elif (w & 0xF000) == 0x9000:                       # mov.w @(d,PC),Rn
            R[n] = _sx16(self._rw(pc + 4 + (w & 0xFF) * 2)) & M
        elif (w & 0xF000) == 0xD000:                       # mov.l @(d,PC),Rn
            R[n] = self._rl(((pc + 4) & ~3) + (w & 0xFF) * 4) & M
        elif (w & 0xF000) == 0x7000:                       # add #imm,Rn
            R[n] = (R[n] + _sx8(w & 0xFF)) & M
        elif (w & 0xF00F) == 0x300C:                       # add Rm,Rn
            R[n] = (R[n] + R[m]) & M
        elif (w & 0xF00F) == 0x3008:                       # sub Rm,Rn
            R[n] = (R[n] - R[m]) & M
        elif (w & 0xF00F) == 0x600C:                       # extu.b Rm,Rn
            R[n] = R[m] & 0xFF
        elif (w & 0xF00F) == 0x600D:                       # extu.w Rm,Rn
            R[n] = R[m] & 0xFFFF
        elif (w & 0xF00F) == 0x3000:                       # cmp/eq Rm,Rn
            self.T = 1 if R[n] == R[m] else 0
        elif (w & 0xF00F) == 0x000D:                       # mov.w @(R0,Rm),Rn
            R[n] = _sx16(self._rw(R[0] + R[m])) & M
        elif (w & 0xF00F) == 0x0005:                       # mov.w Rm,@(R0,Rn)
            self._ww(R[0] + R[n], R[m] & 0xFFFF)
        elif (w & 0xF00F) == 0x2000:                       # mov.b Rm,@Rn
            self._wb(R[n], R[m])
        else:
            raise AssertionError(f'unimplemented opcode {w:04X} @0x{pc:X}')

    def _step(self, pc):
        w = self._rw(pc)
        if (w & 0xF0FF) == 0x402B:                         # jmp @Rn
            target = self.R[(w >> 8) & 0xF]
            self._exec(pc + 2)                             # delay slot
            return target
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


def _prog4_region(edits):
    """0x8D2A..0x8D5F: JP bytes with the module's edits applied."""
    region = bytearray(STUB_JP + TAIL_JP)
    for off, chunk in edits.items():
        region[off - STUB_OFF:off - STUB_OFF + len(chunk)] = chunk
    return bytes(region)


@unittest.skipIf(CONV is None or CAVE is None or not TWIN_PRESENT,
                 'v4 modules absent (RED)')
class TestExecutePatchedAppend(unittest.TestCase):
    """Run the ACTUAL patched bytes: a twin key press must register the
    HANKAKU tile (8px), preserve r4/r5, and keep the JP terminator dance."""

    @classmethod
    def setUpClass(cls):
        edits = dict(CONV.PROG4_NAME_TWIN_CONVERT[PROG4_PATH])
        cls.vm = _Sh2Append(_prog4_region(edits), CAVE.cave_blob())
        cls.jp_vm = _Sh2Append(_prog4_region({}), None)

    def test_every_key_registers_its_hankaku_tile(self):
        for ch in 'AZaz09!? äöüÄÖÜ':
            cells = [ft.TWIN_TILE_MAP[c] for c in 'ABCDE']
            cells[3] = ft.TWIN_TILE_MAP[ch]
            out = self.vm.run(cells, col=3, pos=0)
            self.assertEqual(out['name'][0], ft.HANKAKU_TILE_MAP[ch],
                             f'key {ch!r} must append the hankaku tile')

    def test_all_five_columns_fetch_their_own_cell(self):
        cells = [ft.TWIN_TILE_MAP[c] for c in 'FGHIJ']
        for col in range(5):
            out = self.vm.run(cells, col=col, pos=0)
            self.assertEqual(out['name'][0],
                             ft.HANKAKU_TILE_MAP['FGHIJ'[col]])

    def test_terminator_and_pos_follow_jp_semantics(self):
        name = [ft.HANKAKU_TILE_MAP[c] for c in 'Ar']
        cells = [ft.TWIN_TILE_MAP[c] for c in 'klmno']
        out = self.vm.run(cells, col=2, pos=2, name=name)
        self.assertEqual(out['name'][:3],
                         name + [ft.HANKAKU_TILE_MAP['m']])
        self.assertEqual(out['name'][3], 0xFFFF, 'terminator must move up')
        self.assertEqual(out['pos'], 3, 'pos writeback (the bra delay slot)')

    def test_r4_r5_survive_the_cave(self):
        cells = [ft.TWIN_TILE_MAP[c] for c in 'ABCDE']
        out = self.vm.run(cells, col=0, pos=1,
                          name=[ft.HANKAKU_TILE_MAP['A']])
        self.assertEqual(out['r4'], 2, 'r4 = pos*2 (0x8D36 ran on real pos)')
        self.assertEqual(out['r5'], POS_VAR)

    def test_jp_bytes_would_register_the_raw_twin(self):
        """Why the cave MUST ship with the twin records: the unpatched JP
        append stores the cell verbatim — a 16px twin in the name buffer."""
        cells = [ft.TWIN_TILE_MAP[c] for c in 'ABCDE']
        out = self.jp_vm.run(cells, col=1, pos=0)
        self.assertEqual(out['name'][0], ft.TWIN_TILE_MAP['B'])


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set — skipping disc checks')
class TestJPBaseline(unittest.TestCase):
    """Truth-lock every embedded JP byte against the pristine disc."""

    @classmethod
    def setUpClass(cls):
        from iso_tools import build_file_index, extract_file_data
        cands = (list(Path(JP_DIR).glob('*rack*01*.bin'))
                 or list(Path(JP_DIR).glob('*.bin')))
        image = bytearray(cands[0].read_bytes())
        e = build_file_index(image)[PROG4_PATH]
        cls.jp = extract_file_data(image, e.extent, e.size)

    def test_stub_site(self):
        self.assertEqual(bytes(self.jp[STUB_OFF:STUB_OFF + 12]), STUB_JP)

    def test_fetch_site(self):
        self.assertEqual(bytes(self.jp[FETCH_OFF:FETCH_OFF + 2]), FETCH_JP)

    def test_tail_and_pools(self):
        self.assertEqual(bytes(self.jp[TAIL_OFF:TAIL_OFF + len(TAIL_JP)]),
                         TAIL_JP)
        for off, val in POOL_JP.items():
            self.assertEqual(bytes(self.jp[off:off + 4]),
                             val.to_bytes(4, 'big'))


if __name__ == '__main__':
    unittest.main()
