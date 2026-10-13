"""The name check: END refuses the name of a character (2026-10-13).

JP (PROG_4 FUN_060923A8, archive/docs/20261012_name_check_and_ram_re.md, 1)
compares the typed name with the FNT_SYS name records. In the EN build those
records are bigram tiles and the typed name is 8px band tiles, so the check
never matches and every name passes.

Settled with Ralf (2026-10-13):
  - refuse only characters with a name (fntsys11 minus the generic people,
    army commanders and nations) plus the swords Langrisser and Alhazard;
  - ignore letter case ("ELWIN", "elwin");
  - the default name Diehärte stays allowed.

Red state: on the pre-change build "Elwin" passes (r0 = 1) and the
tools/name_check module does not exist.

Executed on the real bytes: the built PROG_4 function runs on sh2_mini with
the built FNT_SYS mapped at its load address 0x00246000.
"""
import os
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

import font_tools as ft  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

try:
    import name_check as NC
    IMPORT_ERROR = None
except ImportError as exc:  # RED: module not written yet
    NC = None
    IMPORT_ERROR = exc

JP_DIR = os.environ.get('LANG3_JP_DIR')
PROG4, FNTSYS = 'LANG/PROG_4.BIN', 'LANG/FNT_SYS.BIN'
P4_BASE, FNTSYS_BASE = 0x06089000, 0x00246000
CHECK = 0x060923A8
NAME_HOME = 0x06034D5C
EN = PROJ / 'scripts' / 'en'


def _records(n):
    from fnt_sys_tools import _parse_script_records
    return [r.replace('<$FFFF>', '') for r in _parse_script_records(EN / f'fntsys{n}E.txt')]


def _built(*paths):
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        raise unittest.SkipTest('no build/*/track01.bin (run build.py first)')
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    return {p: extract_file_data(img, idx[p].extent, idx[p].size) for p in paths}


def _jp(path):
    from iso_tools import build_file_index, extract_file_data
    cands = (sorted(Path(JP_DIR).glob('*rack*01*.bin'))
             or sorted(Path(JP_DIR).glob('*.bin')))
    img = cands[0].read_bytes()
    idx = build_file_index(img)
    return extract_file_data(img, idx[path].extent, idx[path].size)


class TestModuleExists(unittest.TestCase):
    def test_module_imports(self):
        self.assertIsNone(IMPORT_ERROR, f'RED: tools/name_check.py missing ({IMPORT_ERROR})')


@unittest.skipIf(NC is None, 'module absent (RED)')
class TestList(unittest.TestCase):
    """Which names are refused (settled list, see the module docstring)."""

    def setUp(self):
        self.names = NC.refused_names(EN)
        self.folded = {n.lower() for n in self.names}

    def test_named_characters_and_the_two_swords(self):
        chars = _records(11)
        for want in ('Elwin', 'Liffany', 'Böser', 'Altemüller', 'Dark Knight',
                     'Kaiser Kleist', 'Lushiris', 'Langrisser', 'Alhazard',
                     chars[0x144]):                    # 兄貴 (Big Brother / Bröther)
            self.assertIn(want.lower(), self.folded, want)

    def test_default_name_and_generics_are_allowed(self):
        self.assertNotIn('diehärte', self.folded)
        for g in NC.GENERIC:
            self.assertNotIn(g.lower(), self.folded, g)

    def test_every_generic_is_a_real_fntsys11_name(self):
        """No stale exclusion: a renamed generic must be renamed here too."""
        chars = set(_records(11))
        self.assertEqual(sorted(NC.GENERIC - chars), [])

    def test_only_typeable_names_up_to_16_letters(self):
        keys = set(NC.TYPEABLE)
        for n in self.names:
            self.assertLessEqual(len(n), 16, n)
            self.assertLessEqual(set(n), keys, n)

    def test_swords_are_fntsys10_records_12_and_13(self):
        self.assertEqual(_records(10)[12:14], ['Langrisser', 'Alhazard'])


@unittest.skipIf(NC is None, 'module absent (RED)')
class TestPatchDeclaration(unittest.TestCase):

    def test_registered_and_wired(self):
        import build
        import patch_registry
        self.assertIn('name_check', patch_registry.ENGINE_PATCH_MODULES)
        self.assertIs(build.ENGINE_MODULE_DICTS['name_check'], NC.NAME_CHECK)

    def test_code_fits_the_jp_function_and_spares_the_name_pool_word(self):
        (off, code), = NC.NAME_CHECK[PROG4]
        self.assertEqual(off, 0x93A8)
        self.assertLessEqual(off + len(code), 0x943C)   # 0x943C = name_buffer_home site

    def test_list_fits_below_28_sectors(self):
        self.assertLessEqual(NC.LIST_OFF + len(NC.list_blob(EN)), 0xE000)

    @unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
    def test_jp_baseline(self):
        jp = _jp(PROG4)
        for off, want in NC.NAME_CHECK_JP_BASELINE.items():
            self.assertEqual(jp[off:off + len(want)], want, hex(off))


def _type(text):
    return [ft.HANKAKU_TILE_MAP[c] for c in text] + [0xFFFF]


class TestCheckExecuted(unittest.TestCase):
    """The built PROG_4 check on the built FNT_SYS. allowed = (r0 & 0xFFFF) == 1,
    the caller's test at 0x06091B6A."""

    @classmethod
    def setUpClass(cls):
        files = _built(PROG4, FNTSYS)
        cls.p4, cls.fs = files[PROG4], files[FNTSYS]

    def allowed(self, words):
        ram = bytearray(0x1000)
        for i, w in enumerate(words):
            o = NAME_HOME - 0x06034000 + 2 * i
            ram[o:o + 2] = w.to_bytes(2, 'big')
        vm = Sh2({P4_BASE: bytearray(self.p4) + bytearray(0x1000),
                  FNTSYS_BASE: bytearray(self.fs) + bytearray(0x1000),
                  0x06034000: ram})
        vm.call(CHECK)
        return (vm.R[0] & 0xFFFF) == 1

    def test_refuses_a_character_name(self):
        self.assertFalse(self.allowed(_type('Elwin')))

    def test_refuses_every_listed_name_in_any_case(self):
        if NC is None:
            self.fail('module absent (RED)')
        for n in NC.refused_names(EN):
            for v in (n, n.lower(), n.upper(), n + '  '):
                self.assertFalse(self.allowed(_type(v)), repr(v))

    def test_allows_other_names(self):
        for n in ('Diehärte', 'Thief', 'Elwi', 'Elwinn', 'Elwin x', 'Lan',
                  'Langrissers', 'Ledin2', 'A', 'ABCDEFGHIJKLMNOP'):
            self.assertTrue(self.allowed(_type(n)), n)


if __name__ == '__main__':
    unittest.main()
