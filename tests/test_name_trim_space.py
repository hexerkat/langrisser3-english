"""The name trim drops trailing 8px spaces too (2026-10-13).

PROG_4 FUN_06092348 measures the name and turns trailing blanks into FFFF.
JP only knows tile 0 (the 16px blank); the EN space key types the band space
(font_tools.HANKAKU_TILE_MAP[' ']), so "Diehärte  " was saved with its two
spaces. Ralf (2026-10-13): the trim must work with the 8px space.

Red state: on the JP bytes (and the build before this change) a trailing
band space is kept and counted.

Executed on the real bytes: JP PROG_4 + every enabled engine overlay.
"""
import os
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))
sys.path.insert(0, str(PROJ / 'tests'))

import font_tools as ft  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

try:
    import prog4_name_trim_space as TRIM
except ImportError:  # RED: module not written yet
    TRIM = None

JP_DIR = os.environ.get('LANG3_JP_DIR')
PROG4, P4_BASE = 'LANG/PROG_4.BIN', 0x06089000
LENGTH_FN = 0x06092348
NAME_HOME, JP_NAME = 0x06034D5C, 0x06034D90
SP = ft.HANKAKU_TILE_MAP[' ']


def _t(text):
    return [ft.HANKAKU_TILE_MAP[c] for c in text]


def _run(prog4, name_addr, words):
    ram = bytearray(0x1000)
    for i, w in enumerate(words + [0xFFFF]):
        o = name_addr - 0x06034000 + 2 * i
        ram[o:o + 2] = w.to_bytes(2, 'big')
    vm = Sh2({P4_BASE: bytearray(prog4) + bytearray(0x1000), 0x06034000: ram})
    vm.call(LENGTH_FN)
    name = [vm.rw(name_addr + 2 * i) for i in range(len(words) + 1)]
    return vm.R[0], name


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestTrim(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from test_name_cap16 import _jp_files, _patched
        cls.jp = _jp_files()[PROG4]
        cls.p4 = _patched(cls.jp, PROG4)

    def test_module_exists(self):
        self.assertIsNotNone(TRIM, 'RED: tools/prog4_name_trim_space.py missing')

    def test_jp_baseline(self):
        if TRIM is None:
            self.fail('module absent (RED)')
        for off, want in TRIM.PROG4_NAME_TRIM_SPACE_JP_BASELINE.items():
            self.assertEqual(self.jp[off:off + len(want)], want, hex(off))

    def test_trailing_8px_spaces_are_dropped(self):
        for tail in (1, 2, 8):
            words = _t('Diehärte') + [SP] * tail
            n, name = _run(self.p4, NAME_HOME, words)
            self.assertEqual(n, 8, f'tail {tail}')
            self.assertEqual(name[:8], _t('Diehärte'))
            self.assertEqual(name[8:], [0xFFFF] * (tail + 1))

    def test_mixed_tail_of_both_blanks(self):
        n, name = _run(self.p4, NAME_HOME, _t('Elwin') + [SP, 0, SP])
        self.assertEqual((n, name[5:]), (5, [0xFFFF] * 4))

    def test_inner_spaces_stay(self):
        n, name = _run(self.p4, NAME_HOME, _t('Do Kahni'))
        self.assertEqual((n, name[:8]), (8, _t('Do Kahni')))

    def test_a_name_of_only_8px_spaces_becomes_blank(self):
        """Ralf (2026-10-13): END must not accept a name of spaces. JP keeps
        index 0 and END's non-empty scan only knows tile 0, so the lone
        8px space left at index 0 becomes tile 0 (the JP blank).
        Red state: [SP, FFFF] was kept and END accepted it."""
        for k in (1, 2, 5):
            n, name = _run(self.p4, NAME_HOME, [SP] * k)
            self.assertEqual((n, name[:2]), (1, [0, 0xFFFF]), f'{k} spaces')

    def test_end_treats_a_name_of_spaces_as_empty(self):
        """Trim then the END non-empty scan (0x06091C10..0x06091C46, r3 = 1
        when the name has a letter), on one RAM, as END runs them."""
        for words, has_letter in (([SP] * 3, 0), ([SP, SP] + _t('A'), 1),
                                  (_t('Elwin') + [SP], 1)):
            ram = bytearray(0x1000)
            for i, w in enumerate(words + [0xFFFF]):
                o = NAME_HOME - 0x06034000 + 2 * i
                ram[o:o + 2] = w.to_bytes(2, 'big')
            vm = Sh2({P4_BASE: bytearray(self.p4) + bytearray(0x1000), 0x06034000: ram})
            vm.call(LENGTH_FN)
            vm.R = [0] * 16
            vm.R[15] = 0x060FFF00
            pc = 0x06091C10
            while pc != 0x06091C46:
                pc = vm._step(pc)
            self.assertEqual(vm.R[3], has_letter, words)

    def test_empty_name_returns_0_and_writes_nothing(self):
        """BAK can empty the name. JP then reads index 255 and, if it is 0,
        floods 255 words of RAM after the name with FFFF (up to the CD
        directory tables). Red state: the flood in the zeroed test RAM."""
        ram = bytearray(0x1000)
        o = NAME_HOME - 0x06034000
        ram[o:o + 2] = b'\xff\xff'
        vm = Sh2({P4_BASE: bytearray(self.p4) + bytearray(0x1000), 0x06034000: ram})
        vm.call(LENGTH_FN)
        self.assertEqual(vm.R[0], 0)
        self.assertEqual(bytes(ram[o + 2:]), bytes(len(ram) - o - 2))

    def test_same_as_jp_without_8px_spaces(self):
        cases = [_t('A'), _t('Elwin'), _t('Elwin') + [0, 0], [0] + _t('B') + [0],
                 _t('ABCDEFGH'), _t('ABCDEFG') + [0]]
        for words in cases:
            a = _run(self.p4, NAME_HOME, words)
            b = _run(self.jp, JP_NAME, words)
            self.assertEqual(a, b, words)


if __name__ == '__main__':
    unittest.main()
