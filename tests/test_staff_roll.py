"""The English staff roll (LANG/STAFF.DAT) built from the player's own disc.

Red state: tools/staff_roll.py does not exist and the build ships the JP
staff roll.

STAFF.DAT = container of 3: a Huffman tree, the roll (6-byte header, 16
colors, 320x1536 at 4 bpp) and the katakana name font, both compressed. The
game unpacks them with A0LANG FUN_0600FA88; the codec here is checked
against that routine run on tools/sh2_mini.py. The English text comes from
assets/staff_roll/ (made by the separate langrisser3-graphics-extractor
repo): an overlay PNG and the rectangles it replaces. No Japanese art is in
git; the rest of the roll comes from the player's disc.
"""
import json
import os
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

import png_indexed  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

try:
    import staff_roll
except ImportError:  # RED: module not written yet
    staff_roll = None

JP_DIR = os.environ.get('LANG3_JP_DIR')
ASSET = PROJ / 'assets' / 'staff_roll'
A0LANG_BASE, DECOMPRESS = 0x0600E000, 0x0600FA88
HISTORY = 0x0604E92F                       # FUN_0600FA48's 16-byte history - 1
TABLE, SRC, DST = 0x00200000, 0x00210000, 0x00220000
LOAD_AT, FNT_SYS_AT = 0x00217000, 0x00246000


def _jp(*paths):
    from iso_tools import build_file_index, extract_file_data
    cands = sorted(Path(JP_DIR).glob('*rack*01*.bin')) or sorted(Path(JP_DIR).glob('*.bin'))
    img = cands[0].read_bytes()
    idx = build_file_index(img)
    return [extract_file_data(img, idx[p].extent, idx[p].size) for p in paths]


def _built(path):
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        raise unittest.SkipTest('no build/*/track01.bin (run build.py first)')
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    return extract_file_data(img, idx[path].extent, idx[path].size)


def _game_unpack(a0lang, table, data, size):
    vm = Sh2({A0LANG_BASE: a0lang, HISTORY: bytearray(0x20), TABLE: bytearray(table),
              SRC: bytearray(data), DST: bytearray(size + 0x100)})
    vm.call(DECOMPRESS, {4: TABLE, 5: SRC, 6: DST}, max_steps=20_000_000)
    return bytes(vm.rb(DST + i) for i in range(size))


def _nibbles(data):
    return [v for b in data for v in (b >> 4, b & 15)]


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestCodec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if staff_roll is None:
            raise AssertionError('RED: tools/staff_roll.py missing')
        cls.staff, cls.a0lang = _jp('LANG/STAFF.DAT', 'A0LANG.BIN')

    def test_unpacks_like_the_game(self):
        table, roll, font = staff_roll.parse_container(self.staff)
        ours = staff_roll.decompress(table, font)
        self.assertEqual(_game_unpack(self.a0lang, table, font, len(ours) + 64),
                         ours + bytes(64))

    def test_game_unpacks_what_we_pack(self):
        table, roll, font = staff_roll.parse_container(self.staff)
        plain = [staff_roll.decompress(table, roll), staff_roll.decompress(table, font)]
        new_table, blobs = staff_roll.compress_group(plain)
        self.assertEqual([staff_roll.decompress(new_table, b) for b in blobs], plain)
        self.assertEqual(_game_unpack(self.a0lang, new_table, blobs[1], len(plain[1]) + 64),
                         plain[1] + bytes(64))

    def test_container_round_trip(self):
        self.assertEqual(staff_roll.pack_container(staff_roll.parse_container(self.staff)),
                         self.staff)


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestBuiltStaffRoll(unittest.TestCase):
    """What the player gets: the built disc's STAFF.DAT."""

    @classmethod
    def setUpClass(cls):
        if staff_roll is None:
            raise AssertionError('RED: tools/staff_roll.py missing')
        (jp,) = _jp('LANG/STAFF.DAT')
        cls.built = _built('LANG/STAFF.DAT')
        t, r, f = staff_roll.parse_container(jp)
        cls.jp_roll, cls.jp_font = staff_roll.decompress(t, r), staff_roll.decompress(t, f)
        t, r, f = staff_roll.parse_container(cls.built)
        cls.roll, cls.font = staff_roll.decompress(t, r), staff_roll.decompress(t, f)
        cls.rects = json.loads((ASSET / 'staff_roll_en_rects.json').read_text())
        w, h, cls.overlay = png_indexed.read_indexed_png(str(ASSET / 'staff_roll_en.png'))

    def test_header_palette_and_font_are_the_players(self):
        self.assertEqual(self.roll[:38], self.jp_roll[:38])
        self.assertEqual(self.font, self.jp_font)

    def test_roll_is_the_jp_roll_with_the_english_overlay(self):
        jp, en = _nibbles(self.jp_roll[38:]), _nibbles(self.roll[38:])
        self.assertEqual(len(en), 320 * 1536)
        inside = set()
        for x0, y0, x1, y1 in self.rects:
            for y in range(y0, y1):
                for x in range(x0, x1):
                    inside.add(y * 320 + x)
                    self.assertEqual(en[y * 320 + x], self.overlay[x, y], (x, y))
        self.assertTrue(all(en[i] == jp[i] for i in range(len(en)) if i not in inside))

    def test_english_text_is_there(self):
        self.assertNotEqual(self.roll, self.jp_roll)

    def test_fits_its_load_window(self):
        """PROG_2 reads STAFF.DAT at LWRAM 0x00217000; the same program loads
        the 393 KB OPS.DAT at 0x00212000, so that LWRAM is its scratch
        (inferred from the code). Stay below FNT_SYS at 0x00246000."""
        self.assertLessEqual(LOAD_AT + len(self.built), FNT_SYS_AT)


if __name__ == '__main__':
    unittest.main()
