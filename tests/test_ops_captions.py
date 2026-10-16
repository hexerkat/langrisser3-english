"""The opening's staff and cast captions (LANG/OPS.DAT group 0) in English.

Red state (2026-10-15, Ralf's playtest, Ymir dump of the opening shown at the
start of SCENARIO 3): the captions stayed Japanese. The dump's LWRAM held the
JP caption blocks at 0x00200000 and 0x00209000; tools/ops_captions.py does
not exist.

How the game shows a caption (PROG_2 FUN_0605461c, load base 0x06052800):
both blocks are unpacked by A0LANG FUN_0600FA88 (block 1 = staff to LWRAM
0x00200000, block 2 = cast to 0x00209000; OPS.DAT itself sits at 0x00212000).
Caption k starts at the sum of w8 * h8 * 32 over the size-table entries
before it (entry 0 is an 8x8 dummy) and is copied alone to VDP1 VRAM
0x25C18C00, drawn at (x, 88) from the position table. Tables, 4 bytes per
entry: staff sizes 0x060579F8 and x 0x060579BC, cast sizes 0x06057974 and
x 0x0605792C.

The English captions come from assets/ops_captions (drawn by the separate
langrisser3-graphics-extractor repo, no Japanese art). The build swaps the
two blocks, writes the new widths, and moves each x so the caption keeps the
JP center.
"""
import json
import os
import struct
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

import png_indexed  # noqa: E402
import staff_roll  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

try:
    import ops_captions
except ImportError:  # RED
    ops_captions = None

JP_DIR = os.environ.get('LANG3_JP_DIR')
ASSET = PROJ / 'assets' / 'ops_captions'
PROG2 = 0x06052800
TABLES = [(0x060579F8, 0x060579BC, 15), (0x06057974, 0x0605792C, 18)]   # sizes, x, entries
A0LANG_BASE, DECOMPRESS = 0x0600E000, 0x0600FA88
HISTORY = 0x0604E92F
TABLE, SRC, DST = 0x00300000, 0x00310000, 0x00200000


def _files(img, *paths):
    from iso_tools import build_file_index, extract_file_data
    idx = build_file_index(img)
    return [extract_file_data(img, idx[p].extent, idx[p].size) for p in paths]


def _jp(*paths):
    cands = sorted(Path(JP_DIR).glob('*rack*01*.bin'))
    return _files(cands[0].read_bytes(), *paths)


def _built(*paths):
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        raise unittest.SkipTest('no build/*/track01.bin (run build.py first)')
    return _files(max(builds, key=lambda p: p.stat().st_mtime).read_bytes(), *paths)


def _tables(prog2):
    """Per block: [(w8, h8, x), ...] including the dummy entry 0."""
    out = []
    for sizes, xs, n in TABLES:
        out.append([(prog2[sizes - PROG2 + 4 * i], prog2[sizes - PROG2 + 4 * i + 1],
                     struct.unpack_from('b', prog2, xs - PROG2 + 4 * i)[0]) for i in range(n)])
    return out


def _game_unpack(a0lang, table, blob, size):
    vm = Sh2({A0LANG_BASE: a0lang, HISTORY: bytearray(0x20), TABLE: bytearray(table),
              SRC: bytearray(blob), DST: bytearray(size + 0x100)})
    vm.call(DECOMPRESS, {4: TABLE, 5: SRC, 6: DST}, max_steps=60_000_000)
    return bytes(vm.rb(DST + i) for i in range(size + 0x100))


def _asset_sprites():
    meta = json.loads((ASSET / 'ops_captions_en.json').read_text())
    blocks = []
    for b, widths in enumerate(meta['widths'], 1):
        w, h, px = png_indexed.read_indexed_png(str(ASSET / f'ops_captions{b}_en.png'))
        sprites = []
        for i, sw in enumerate(widths):
            vals = [px[x, 40 * i + y] & 15 for y in range(40) for x in range(sw)]
            sprites.append(bytes((vals[k] << 4) | vals[k + 1] for k in range(0, len(vals), 2)))
        blocks.append(sprites)
    return meta['widths'], blocks


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestModule(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if ops_captions is None:
            raise AssertionError('RED: tools/ops_captions.py missing')
        cls.ops, cls.prog2 = _jp('LANG/OPS.DAT', 'LANG/PROG_2.BIN')

    def test_jp_baseline_matches_the_disc(self):
        self.assertEqual(_tables(self.prog2), ops_captions.JP_TABLES)

    def test_nested_container_round_trips(self):
        top = staff_roll.parse_container(self.ops)
        self.assertEqual(staff_roll.pack_container(top), self.ops)
        self.assertEqual(staff_roll.pack_container(staff_roll.parse_container(top[0])), top[0])


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestBuiltCaptions(unittest.TestCase):
    """What the player gets: the built disc's OPS.DAT and PROG_2."""

    @classmethod
    def setUpClass(cls):
        if ops_captions is None:
            raise AssertionError('RED: tools/ops_captions.py missing')
        cls.jp_ops, cls.jp_prog2, cls.a0lang = _jp('LANG/OPS.DAT', 'LANG/PROG_2.BIN',
                                                   'A0LANG.BIN')
        cls.ops, cls.prog2 = _built('LANG/OPS.DAT', 'LANG/PROG_2.BIN')
        cls.widths, cls.sprites = _asset_sprites()
        top = staff_roll.parse_container(cls.ops)
        g0 = staff_roll.parse_container(top[0])
        cls.top, cls.tree, cls.blobs = top, g0[0], g0[1:]
        jp_g0 = staff_roll.parse_container(staff_roll.parse_container(cls.jp_ops)[0])
        cls.jp_blocks = [staff_roll.decompress(jp_g0[0], b) for b in jp_g0[1:]]

    def test_portraits_are_the_players(self):
        jp_top = staff_roll.parse_container(self.jp_ops)
        self.assertEqual(self.top[1:], jp_top[1:])

    def test_tables_hold_the_english_widths_and_keep_the_centers(self):
        for jp, en, widths in zip(_tables(self.jp_prog2), _tables(self.prog2), self.widths):
            self.assertEqual(en[0], jp[0])                       # the dummy
            self.assertEqual([w8 * 8 for w8, _, _ in en[1:]], widths)
            for (jw, jh, jx), (ew, eh, ex) in zip(jp[1:], en[1:]):
                self.assertEqual(eh, jh)
                self.assertEqual(2 * ex + ew * 8, 2 * jx + jw * 8)

    def test_game_shows_each_english_caption(self):
        """Unpack each block with the game's routine and walk it the way
        FUN_0605461c does, with the built tables."""
        for b, (blob, table, sprites, jp_block) in enumerate(
                zip(self.blobs, _tables(self.prog2), self.sprites, self.jp_blocks)):
            size = sum(w8 * h8 * 32 for w8, h8, _ in table)
            block = _game_unpack(self.a0lang, self.tree, blob, size)
            self.assertEqual(block[:32], jp_block[:32])           # the dummy
            off = 32
            for (w8, h8, _), sprite in zip(table[1:], sprites):
                self.assertEqual(block[off:off + w8 * h8 * 32], sprite, (b, off))
                off += w8 * h8 * 32

    def test_memory_limits(self):
        """Each caption fits the VDP1 slot the largest JP caption uses
        (200x40 = 4000 bytes); each block stays within its JP size (LWRAM
        0x00200000 / 0x00209000, OPS.DAT at 0x00212000); OPS.DAT does not
        grow."""
        for table, jp_block in zip(_tables(self.prog2), self.jp_blocks):
            self.assertTrue(all(w8 * h8 * 32 <= 4000 for w8, h8, _ in table))
            self.assertLessEqual(sum(w8 * h8 * 32 for w8, h8, _ in table), len(jp_block))
        self.assertLessEqual(len(self.ops), len(self.jp_ops))
