"""The hidden sound test (PROG_2) shows English names.

Red state: tools/prog2_sound_test.py does not exist; the built PROG_2 keeps
the JP labels TokinoKoe / Himei and ~160 half-width katakana names.

The screen: PROG_2 title program, reached with a button code at PRESS START
BUTTON (FUN_060537ac compares the last 7 presses with the table at
0x06053790: C, Right, X, Left, Y, A, Z, order in the buffer not yet
confirmed). FUN_060535ce prints it with A0LANG FUN_0600F604, whose font is
the small 8x8 ASCII bank (128 glyphs, no kana, no umlauts:
archive/docs/20261012_name_check_and_ram_re.md section 7). So every byte
the English text uses must be printable ASCII. Names with umlauts lose them
(Ralf 2026-10-14: Dieharte, Altemuller, Boser, Riguler).

Tables (PROG_2 base 0x06052800):
  0x0580 + 12*i  six 10-char labels (BGM, SE, TokinoKoe, Himei, PCM Scen, PCM No)
  0x2B88         94 sound effects, 36 bytes: u16 id + 34-byte name
  0x38C0         6 war cries, 32-byte names
  0x3980         60 screams, 32-byte names
"""
import os
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

try:
    import prog2_sound_test as ST
except ImportError:  # RED
    ST = None

JP_DIR = os.environ.get('LANG3_JP_DIR')
PROG2 = 'LANG/PROG_2.BIN'
NAME_COLUMN_CHARS = 14     # names start at x 208 on a 320 px screen, 8 px glyphs


def _read(img_path, path):
    from iso_tools import build_file_index, extract_file_data
    img = Path(img_path).read_bytes()
    e = build_file_index(img)[path]
    return extract_file_data(img, e.extent, e.size)


def _jp():
    cands = sorted(Path(JP_DIR).glob('*rack*01*.bin')) or sorted(Path(JP_DIR).glob('*.bin'))
    return _read(cands[0], PROG2)


def _built():
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        raise unittest.SkipTest('no build/*/track01.bin (run build.py first)')
    return _read(max(builds, key=lambda p: p.stat().st_mtime), PROG2)


def _fields(data):
    """(kind, index, raw field bytes) for every text field of the screen."""
    out = []
    for i in range(6):
        out.append(('label', i, data[0x580 + 12 * i:0x580 + 12 * i + 11]))
    for i in range(94):
        o = 0x2B88 + 36 * i
        out.append(('sfx', i, data[o + 2:o + 36]))
    for i in range(6):
        out.append(('cry', i, data[0x38C0 + 32 * i:0x38C0 + 32 * (i + 1)]))
    for i in range(60):
        out.append(('scream', i, data[0x3980 + 32 * i:0x3980 + 32 * (i + 1)]))
    return out


def _text(field):
    return field.split(b'\0')[0]


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestSoundTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if ST is None:
            raise AssertionError('RED: tools/prog2_sound_test.py missing')
        cls.jp = _jp()

    def test_jp_baseline(self):
        for off, want in ST.PROG2_SOUND_TEST_JP_BASELINE.items():
            self.assertEqual(self.jp[off:off + len(want)], want, hex(off))

    def test_edits_only_touch_text_fields(self):
        """Each edit replaces exactly one JP field of the same size."""
        for off, data in ST.PROG2_SOUND_TEST['LANG/PROG_2.BIN']:
            self.assertEqual(len(data), len(ST.PROG2_SOUND_TEST_JP_BASELINE[off]), hex(off))

    def test_built_screen_is_english_ascii(self):
        built = _built()
        for (kind, i, field), (_, _, jp_field) in zip(_fields(built), _fields(self.jp)):
            text = _text(field)
            self.assertTrue(text, (kind, i))
            self.assertTrue(all(0x20 <= b < 0x7F for b in text), (kind, i, text))
            self.assertIn(b'\0', field, (kind, i))                      # terminated in its slot
            limit = max(len(_text(jp_field)), NAME_COLUMN_CHARS)
            if kind != 'label':
                self.assertLessEqual(len(text), limit, (kind, i, text))
        labels = [_text(f) for k, _, f in _fields(built) if k == 'label']
        self.assertTrue(all(len(t) == 10 for t in labels), labels)

    def test_sound_ids_are_kept(self):
        built = _built()
        for i in range(94):
            o = 0x2B88 + 36 * i
            self.assertEqual(built[o:o + 2], self.jp[o:o + 2], i)

    def test_canon_names_without_umlauts(self):
        screams = [_text(f).decode() for k, _, f in _fields(_built()) if k == 'scream']
        for name in ('Dieharte', 'Altemuller', 'Boser', 'Jugler', 'Do Kahni', 'Galshook'):
            self.assertIn(name, screams)


if __name__ == '__main__':
    unittest.main()
