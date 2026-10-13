"""16-letter protagonist name (feat/name-cap16, 2026-10-12).

Red state (2026-10-12): the name entry stops at 8 letters. The buffer
0x06034D90 holds 9 words (8 tiles + FFFF) with live data on both sides, five
PROG_4 sites bound the name at 8 entries, the default name is 4 bigram tiles
that cannot share a 16-letter field with 8px letters, and the save copies the
same 9 words. None of tools/name_buffer_home.py, prog4_name_cap16.py,
a0lang_save_name_pack.py or fntsys11_default_name.py exists.

Requirement (Ralf): the name holds 16 letters of 8px, the same 128px as the
8 zenkaku of the JP field. Design and evidence:
archive/docs/20260715_name_cap16_re_design.md and
archive/docs/20261012_name_check_and_ram_re.md (sections 8, 9, 10).

Every behavior test EXECUTES real bytes on tools/sh2_mini.py: the JP binaries
from the disc with every enabled engine overlay applied (build.engine_overlays,
the same merge the build uses), plus the font caves at their LWRAM addresses.
"""
import os
import struct
import sys
import unittest
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))
sys.path.insert(0, str(PROJ))

import font_tools as ft  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

try:
    import name_buffer_home as HOME
    import prog4_name_cap16 as CAP
    import a0lang_save_name_pack as PACK
    import fntsys11_default_name as DEFNAME
    IMPORT_ERROR = None
except Exception as exc:  # Red
    HOME = CAP = PACK = DEFNAME = None
    IMPORT_ERROR = exc

JP_DIR = os.environ.get('LANG3_JP_DIR')
A0LANG, PROG4 = 'A0LANG.BIN', 'LANG/PROG_4.BIN'
A0_BASE, P4_BASE = 0x0600E000, 0x06089000
JP_NAME_BUF = 0x06034D90
ROOT_DIR_TABLE, ROOT_ENTRIES, NEXT_LIVE = 0x06034C00, 8, 0x06034D80
SAVE_NAME = 0x0604BF58
BAND = [ft.HANKAKU_TILE_MAP[c] for c in 'ABCDEFGHIJKLMNOPQ']
CODE_FILES = ('A0LANG.BIN', 'LANG/BATTLE/SYSWIN.BIN', 'LANG/DEMO.BIN',
              'LANG/PROG_2.BIN', 'LANG/PROG_3.BIN', 'LANG/PROG_4.BIN',
              'LANG/PROG_5.BIN', 'LANG/PROG_6.BIN', 'LANG/PROG_7.BIN')

# The 17 pool words that hold the JP buffer address (disc scan, 2026-10-12).
SITES = [('A0LANG.BIN', 0x05B4), ('A0LANG.BIN', 0x7820), ('A0LANG.BIN', 0x7B0C),
         ('LANG/PROG_2.BIN', 0x2824),
         ('LANG/PROG_3.BIN', 0x283B4), ('LANG/PROG_3.BIN', 0x2CB28),
         ('LANG/PROG_3.BIN', 0x2CC84),
         ('LANG/PROG_4.BIN', 0x847C), ('LANG/PROG_4.BIN', 0x8658),
         ('LANG/PROG_4.BIN', 0x894C), ('LANG/PROG_4.BIN', 0x8B8C),
         ('LANG/PROG_4.BIN', 0x8D9C), ('LANG/PROG_4.BIN', 0x8EF0),
         ('LANG/PROG_4.BIN', 0x93A0), ('LANG/PROG_4.BIN', 0x943C),
         ('LANG/PROG_4.BIN', 0x9674), ('LANG/PROG_5.BIN', 0x5FA8)]


def _jp_files():
    from iso_tools import build_file_index, extract_file_data
    cands = (sorted(Path(JP_DIR).glob('*rack*01*.bin'))
             or sorted(Path(JP_DIR).glob('*.bin')))
    img = cands[0].read_bytes()
    idx = build_file_index(img)
    return {p: extract_file_data(img, idx[p].extent, idx[p].size)
            for p in CODE_FILES}


def _built_files(*paths):
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        raise unittest.SkipTest('no build/*/track01.bin (run build.py first)')
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    return {p: extract_file_data(img, idx[p].extent, idx[p].size) for p in paths}


def _patched(jp, path, skip=()):
    """JP file + every enabled engine overlay, minus the modules in `skip`."""
    import build
    out = bytearray(jp)
    for name, module in build.ENGINE_MODULE_DICTS.items():
        if name in skip:
            continue
        for off, chunk in module.get(path, []):
            out[off:off + len(chunk)] = chunk
    return bytes(out)


def _font_caves():
    """Every SH-2 cave the font writer puts into FONT.BIN, at its LWRAM slot."""
    import balloon_zenkaku_cave as BZ
    import name_twin_cave as NT
    import width_class as WC
    region = bytearray(0x2000)
    base = 0x00288000 + 1400 * 32
    blobs = [(BZ.CAVE_TILE, BZ.cave_blob()), (NT.NAME_TWIN_CAVE_TILE, NT.cave_blob()),
             (WC.WIDTH_CAVE_TILE, WC.cave_blob())]
    if PACK is not None:
        blobs += [(PACK.PACK_TILE, PACK.pack_blob()), (PACK.UNPACK_TILE, PACK.unpack_blob())]
    for tile, blob in blobs:
        o = 0x00288000 + tile * 32 - base
        region[o:o + len(blob)] = blob
    return base, region


def _words(vm, addr, n):
    return [vm.rw(addr + 2 * i) for i in range(n)]


def _put_words(region, base, addr, words):
    for i, w in enumerate(words):
        region[addr - base + 2 * i:addr - base + 2 * i + 2] = (w & 0xFFFF).to_bytes(2, 'big')


class TestModulesExist(unittest.TestCase):

    def test_modules_are_built(self):
        self.assertIsNone(IMPORT_ERROR, f'RED: modules not built ({IMPORT_ERROR})')


@unittest.skipIf(HOME is None, 'modules absent (RED)')
class TestBufferHome(unittest.TestCase):

    def test_home_sits_in_the_unused_root_directory_slots(self):
        """GFS root table: 24-byte records from 0x06034C00, the root holds 8,
        the next live byte is 0x06034D80 (section 9 of the RAM doc)."""
        self.assertGreaterEqual(HOME.NAME_HOME, ROOT_DIR_TABLE + ROOT_ENTRIES * 24)
        self.assertLessEqual(HOME.NAME_HOME + 34, NEXT_LIVE)
        self.assertEqual(HOME.NAME_HOME % 4, 0)

    def test_every_pool_site_points_home(self):
        want = {}
        for path, off in SITES:
            want.setdefault(path, []).append((off, HOME.NAME_HOME.to_bytes(4, 'big')))
        got = {p: sorted(e) for p, e in HOME.NAME_BUFFER_HOME.items()}
        self.assertEqual(got, {p: sorted(e) for p, e in want.items()})


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
class TestJPDiscFacts(unittest.TestCase):
    """The sites list is complete and every JP baseline holds."""

    @classmethod
    def setUpClass(cls):
        cls.jp = _jp_files()

    def test_sites_are_every_aligned_pointer_to_the_jp_buffer(self):
        found = []
        for path, data in self.jp.items():
            for off in range(0, len(data) - 3, 4):
                v = int.from_bytes(data[off:off + 4], 'big') & 0xDFFFFFFF
                if v == JP_NAME_BUF:
                    found.append((path, off))
        self.assertEqual(sorted(found), sorted(SITES))

    @unittest.skipIf(CAP is None, 'modules absent (RED)')
    def test_module_baselines_match_the_disc(self):
        for off, want in CAP.PROG4_NAME_CAP16_JP_BASELINE.items():
            self.assertEqual(self.jp[PROG4][off:off + len(want)], want, hex(off))
        for off, want in PACK.A0LANG_SAVE_NAME_PACK_JP_BASELINE.items():
            self.assertEqual(self.jp[A0LANG][off:off + len(want)], want, hex(off))

    def test_save_functions_save_pr_before_the_stubs(self):
        """The stubs `jsr` into the font caves: both enclosing functions must
        push PR in their prologue (sts.l pr,@-r15) and pop it before rts."""
        a0 = self.jp[A0LANG]
        for entry in (0x0601566C, 0x0601592C):
            prologue = a0[entry - A0_BASE:entry - A0_BASE + 8]
            self.assertIn(b'\x4f\x22', prologue)


class _Prog4Vm:
    """PROG_4 (JP + overlays) + font caves + HWRAM page of the name."""
    REC = 0x06060000          # synthetic keyboard records, one per list entry
    LIST = 0x06095404         # 21 entries x 16, record ptr at +12

    def __init__(self, prog4, name_addr):
        self.name = name_addr
        self.prog4 = bytearray(prog4) + bytearray(0x1000)
        fb, fr = _font_caves()
        self.regions = {P4_BASE: self.prog4, fb: fr,
                        0x06034000: bytearray(0x1000), self.REC: bytearray(0x1000)}

    def var(self, pool_addr):
        return int.from_bytes(self.prog4[pool_addr - P4_BASE:pool_addr - P4_BASE + 4], 'big')

    def press(self, name, block, row, col, cell):
        """Run the append from 0x06091CFC; return (exit pc, name words, pos)."""
        regions = {b: bytearray(r) for b, r in self.regions.items()}
        p4, recs, ram = regions[P4_BASE], regions[self.REC], regions[0x06034000]
        idx = block * 7 + row
        entry = self.LIST + idx * 16
        p4[entry + 12 - P4_BASE:entry + 16 - P4_BASE] = (self.REC + idx * 16).to_bytes(4, 'big')
        _put_words(recs, self.REC, self.REC + idx * 16, [cell] * 5)
        for pool, val in ((0x06091DC4, block), (0x06091DCC, row),
                          (0x06091DC8, col), (0x06091DBC, len(name))):
            a = self.var(pool)
            p4[a - P4_BASE] = val
        _put_words(ram, 0x06034000, self.name, list(name) + [0xFFFF])
        vm = Sh2(regions)
        vm.R = [0] * 16
        vm.R[15] = 0x060FFF00
        pc, steps = 0x06091CFC, 0
        while pc not in (0x06091E5A, 0x06091E94):
            steps += 1
            assert steps < 2000, hex(pc)
            pc = vm._step(pc)
        pos = vm.rb(self.var(0x06091DBC))
        return pc, _words(vm, self.name, 18), pos


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
@unittest.skipIf(CAP is None, 'modules absent (RED)')
class TestAppendExecuted(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        jp = _jp_files()[PROG4]
        cls.vm = _Prog4Vm(_patched(jp, PROG4), HOME.NAME_HOME)
        cls.vm_nocap = _Prog4Vm(_patched(jp, PROG4, skip={'prog4_name_cap16'}),
                                HOME.NAME_HOME)
        cls.twin_a = ft.TWIN_TILE_MAP['a']

    def test_letters_9_to_16_are_accepted(self):
        for pos in range(16):
            pc, name, newpos = self.vm.press(BAND[:pos], 0, 0, 0, self.twin_a)
            self.assertEqual(pc, 0x06091E5A, f'pos {pos} refused')
            self.assertEqual(name[:pos + 2],
                             BAND[:pos] + [ft.HANKAKU_TILE_MAP['a'], 0xFFFF])
            self.assertEqual(newpos, pos + 1)

    def test_the_17th_letter_is_refused(self):
        pc, name, pos = self.vm.press(BAND[:16], 0, 0, 0, self.twin_a)
        self.assertEqual(pc, 0x06091E94)
        self.assertEqual(name[:17], BAND[:16] + [0xFFFF])
        self.assertEqual(pos, 16)

    def test_without_the_cap_module_the_9th_letter_is_refused(self):
        pc, _, _ = self.vm_nocap.press(BAND[:8], 0, 0, 0, self.twin_a)
        self.assertEqual(pc, 0x06091E94)

    def test_every_key_still_fetches_its_own_list_entry(self):
        """The JP `mov #7` is also the rows-per-block multiplier (block*7+row);
        the cap rewrite must keep r2 = 7 for the mul.l."""
        for block in range(3):
            for row in range(7):
                for col in (0, 4):
                    ch = 'ABCDEFGHIJKLMNOPQRSTU'[block * 7 + row]
                    pc, name, _ = self.vm.press(BAND[:3], block, row, col,
                                                ft.TWIN_TILE_MAP[ch])
                    self.assertEqual(pc, 0x06091E5A)
                    self.assertEqual(name[3], ft.HANKAKU_TILE_MAP[ch],
                                     f'block {block} row {row} col {col}')


def _call(prog4, name_addr, entry, words, regs=None, stop=None):
    ram = bytearray(0x1000)
    _put_words(ram, 0x06034000, name_addr, words)
    vm = Sh2({P4_BASE: bytearray(prog4) + bytearray(0x1000), 0x06034000: ram})
    if stop is None:
        vm.call(entry, regs)
    else:
        vm.R = [0] * 16
        for k, v in (regs or {}).items():
            vm.R[k] = v
        vm.R[15] = 0x060FFF00
        pc = entry
        while pc != stop:
            pc = vm._step(pc)
    return vm


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
@unittest.skipIf(CAP is None, 'modules absent (RED)')
class TestLengthEndAndCursor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        jp = _jp_files()[PROG4]
        cls.p4 = _patched(jp, PROG4)
        cls.jp = jp

    def test_name_length_counts_up_to_16(self):
        """FUN_06092348 returns the name length (trailing 16px blanks
        trimmed); JP stops counting at 8."""
        for n in range(17):
            vm = _call(self.p4, HOME.NAME_HOME, 0x06092348, BAND[:n] + [0xFFFF])
            # n = 0: 0 since prog4_name_trim_space (JP read index 255 and
            # returned 1 after flooding the zeroed test RAM with FFFF)
            self.assertEqual(vm.R[0], n, f'n={n}')
            self.assertEqual(_words(vm, HOME.NAME_HOME, n + 1)[:n], BAND[:n])

    def test_length_matches_jp_up_to_8(self):
        for n in range(1, 9):     # n = 0: see prog4_name_trim_space
            words = BAND[:n] + [0xFFFF]
            a = _call(self.p4, HOME.NAME_HOME, 0x06092348, words)
            b = _call(self.jp, JP_NAME_BUF, 0x06092348, words)
            self.assertEqual(a.R[0], b.R[0])

    def test_end_sees_a_letter_anywhere_in_16(self):
        """END only accepts a name with a non-blank tile; the scan must reach
        entry 15 (JP: entry 7)."""
        words = [0] * 12 + [BAND[0]] + [0xFFFF]
        vm = _call(self.p4, HOME.NAME_HOME, 0x06091C10, words, {3: 0}, stop=0x06091C46)
        self.assertEqual(vm.R[3], 1)
        vm = _call(self.p4, HOME.NAME_HOME, 0x06091C10, [0] * 16 + [0xFFFF], {3: 0},
                   stop=0x06091C46)
        self.assertEqual(vm.R[3], 0)

    def test_cursor_steps_8px_and_parks_on_the_16th_cell(self):
        for pos in range(18):
            vm = _call(self.p4, HOME.NAME_HOME, 0x06092078, [0xFFFF], {4: pos},
                       stop=0x06092094)
            want = 0xB0 + min(pos, 15) * 8
            self.assertEqual(vm.R[3] & 0xFFFF, want, f'pos {pos}')

    def test_cursor_bar_is_one_8px_cell_wide(self):
        """The blinking bar is a VDP1 quad built on the stack: corners
        (X, 0x26) (X+w, 0x26) (X+w, 0x27) (X, 0x27). JP w = 15 (one 16px
        zenkaku cell); with 8px letters it must be 7. Red state: the JP
        `add #15,r2` at 0x060920CE drew the bar over two letters."""
        blink = 0x06095610                 # frame counter; > 15 = bar shown
        p4 = bytearray(self.p4)
        p4[blink - P4_BASE:blink - P4_BASE + 4] = (0x10).to_bytes(4, 'big')
        for pos in (0, 5, 15, 16):
            vm = _call(bytes(p4), HOME.NAME_HOME, 0x06092078, [0xFFFF], {4: pos},
                       stop=0x060920FE)
            quad = _words(vm, vm.R[14] + 0x0C, 8)
            x = 0xB0 + min(pos, 15) * 8
            self.assertEqual(quad, [x, 0x26, x + 7, 0x26, x + 7, 0x27, x, 0x27],
                             f'pos {pos}')


@unittest.skipIf(DEFNAME is None, 'modules absent (RED)')
class TestDefaultName(unittest.TestCase):

    def test_default_name_record_is_8px_letters(self):
        rec = DEFNAME.default_name_record('Diehärte<$FFFF>')
        self.assertEqual(rec, b''.join(struct.pack('>H', ft.HANKAKU_TILE_MAP[c])
                                       for c in 'Diehärte') + b'\xff\xff')

    def test_copy_cap_is_16(self):
        edits = dict(CAP.PROG4_NAME_CAP16[PROG4])
        self.assertEqual(edits[0x8A1E], bytes.fromhex('e610'))

    @unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
    def test_the_screen_copies_the_whole_default_name(self):
        """A0LANG 0x06016D04 copies at most r6 words (PROG_4 passes 16 now)."""
        a0 = _jp_files()[A0LANG]
        src = 0x06034E00
        ram = bytearray(0x1000)
        rec = DEFNAME.default_name_record('Diehärte<$FFFF>')
        ram[src - 0x06034000:src - 0x06034000 + len(rec)] = rec
        vm = Sh2({A0_BASE: a0, 0x06034000: ram})
        vm.call(0x06016D04, {4: src, 5: HOME.NAME_HOME, 6: 16})
        self.assertEqual(_words(vm, HOME.NAME_HOME, 9),
                         [ft.HANKAKU_TILE_MAP[c] for c in 'Diehärte'] + [0xFFFF])

    def test_built_fnt_sys_carries_the_8px_default(self):
        from fnt_sys_tools import parse_fnt_sys
        fs = parse_fnt_sys(_built_files('LANG/FNT_SYS.BIN')['LANG/FNT_SYS.BIN'])
        self.assertEqual(fs.pairs[10].records[0],
                         DEFNAME.default_name_record('Diehärte<$FFFF>'))


class _SaveVm:
    def __init__(self, a0):
        fb, fr = _font_caves()
        self.regions = {A0_BASE: bytearray(a0), fb: fr,
                        0x06034000: bytearray(0x1000), 0x0604B000: bytearray(0x1000)}

    def run(self, start, stop, name=None, field=None, name_addr=None):
        regions = {b: bytearray(r) for b, r in self.regions.items()}
        if name is not None:
            _put_words(regions[0x06034000], 0x06034000, name_addr, name)
        if field is not None:
            o = SAVE_NAME - 0x0604B000
            regions[0x0604B000][o:o + 18] = field
        vm = Sh2(regions)
        vm.R = [0] * 16
        for r in range(8, 15):
            vm.R[r] = 0x1000 + r
        vm.R[15] = 0x060FFF00
        pc = start
        while pc != stop:
            pc = vm._step(pc)
        return vm

    def gather(self, name, name_addr):
        vm = self.run(0x0601571E, 0x06015732, name=name, name_addr=name_addr)
        return vm, bytes(vm.rb(SAVE_NAME + i) for i in range(18))

    def scatter(self, field, name_addr):
        vm = self.run(0x06015A22, 0x06015A36, field=field)
        return vm, _words(vm, name_addr, 17)


@unittest.skipUnless(JP_DIR, 'LANG3_JP_DIR not set')
@unittest.skipIf(PACK is None, 'modules absent (RED)')
class TestSaveExecuted(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        jp = _jp_files()[A0LANG]
        cls.new = _SaveVm(_patched(jp, A0LANG))
        cls.jp = _SaveVm(jp)

    def test_8px_names_up_to_16_pack_into_the_18_bytes(self):
        for n in range(17):
            name = BAND[:n] + [0xFFFF]
            vm, field = self.new.gather(name, HOME.NAME_HOME)
            want = bytes(t - 1264 for t in BAND[:n]) + bytes(16 - n) + b'\xa5\x5a'
            self.assertEqual(field, want, f'n={n}')
            self.assertEqual([vm.R[r] for r in range(8, 15)],
                             [0x1000 + r for r in range(8, 15)])

    def test_round_trip(self):
        for n in range(17):
            name = BAND[:n] + [0xFFFF]
            _, field = self.new.gather(name, HOME.NAME_HOME)
            _, back = self.new.scatter(field, HOME.NAME_HOME)
            self.assertEqual(back[:n + 1], name, f'n={n}')

    def test_only_the_18_bytes_change(self):
        vm, _ = self.new.gather(BAND[:16] + [0xFFFF], HOME.NAME_HOME)
        self.assertEqual(vm.rw(SAVE_NAME - 2), 0)
        self.assertEqual(vm.rw(SAVE_NAME + 18), 0)

    def test_a_non_8px_name_keeps_the_jp_format(self):
        """A name carried over from an old save (JP zenkaku or bigrams) is
        copied raw, exactly as the JP code copies it."""
        for name in ([0x03E9, 0x00B2, 0x067E, 0x02B4, 0xFFFF] + [0] * 4,
                     [0x0302, 0x0401, BAND[0], 0xFFFF] + [0] * 5):
            _, new = self.new.gather(name, HOME.NAME_HOME)
            _, old = self.jp.gather(name, JP_NAME_BUF)
            self.assertEqual(new, old)

    def test_old_saves_load_unchanged(self):
        """Saves written before this change hold 9 raw words, word 8 never
        0xA55A: they load exactly as the JP code loads them."""
        for name in ([0x03E9, 0x00B2, 0x067E, 0x02B4, 0xFFFF, 0, 0, 0, 0],
                     BAND[:8] + [0xFFFF]):
            field = b''.join(struct.pack('>H', w) for w in name)
            _, new = self.new.scatter(field, HOME.NAME_HOME)
            _, old = self.jp.scatter(field, JP_NAME_BUF)
            self.assertEqual(new[:9], old[:9])


@unittest.skipIf(PACK is None, 'modules absent (RED)')
class TestFontAndRegistration(unittest.TestCase):

    def test_caves_fit_reserved_free_tiles(self):
        taken = set(ft.HANKAKU_TILE_MAP.values()) | set(ft.TWIN_TILE_MAP.values())
        import balloon_zenkaku_cave as BZ
        import name_twin_cave as NT
        import width_class as WC
        taken |= {BZ.SCRATCH_TILE, ft.NAKAGURO_TILE, WC.WIDTH_CAVE_TILE}
        taken |= set(range(BZ.CAVE_TILE, BZ.CAVE_TILE + BZ.CAVE_TILES))
        taken |= set(range(NT.NAME_TWIN_CAVE_TILE, NT.NAME_TWIN_CAVE_TILE + 2))
        for tile, blob, tiles in ((PACK.PACK_TILE, PACK.pack_blob(), PACK.PACK_TILES),
                                  (PACK.UNPACK_TILE, PACK.unpack_blob(), PACK.UNPACK_TILES)):
            self.assertLessEqual(len(blob), tiles * 32)
            span = set(range(tile, tile + tiles))
            self.assertTrue(span <= ft.V08_RESERVED_TILES)
            self.assertFalse(span & taken)
        self.assertFalse(set(range(PACK.PACK_TILE, PACK.PACK_TILE + PACK.PACK_TILES))
                         & set(range(PACK.UNPACK_TILE, PACK.UNPACK_TILE + PACK.UNPACK_TILES)))

    def test_registered_and_disjoint(self):
        import build
        import patch_registry
        names = ('name_buffer_home', 'prog4_name_cap16', 'a0lang_save_name_pack')
        for name in names:
            self.assertIn(name, build.ENGINE_MODULE_DICTS)
            self.assertIn(name, patch_registry.ENGINE_PATCH_MODULES)
        spans = {}
        for name, module in build.ENGINE_MODULE_DICTS.items():
            for path, edits in module.items():
                for off, chunk in edits:
                    for b in range(off, off + len(chunk)):
                        other = spans.setdefault((path, b), name)
                        if other != name and (name in names or other in names):
                            self.fail(f'{name} and {other} both write {path}+0x{b:X}')

    def test_built_disc_carries_everything(self):
        files = _built_files('LANG/FONT.BIN', *CODE_FILES)
        font = files['LANG/FONT.BIN']
        for tile, blob in ((PACK.PACK_TILE, PACK.pack_blob()),
                           (PACK.UNPACK_TILE, PACK.unpack_blob())):
            self.assertEqual(font[tile * 32:tile * 32 + len(blob)], blob)
        for path in CODE_FILES:
            data = files[path]
            for off in range(0, len(data) - 3, 4):
                v = int.from_bytes(data[off:off + 4], 'big') & 0xDFFFFFFF
                self.assertNotEqual(v, JP_NAME_BUF, f'{path}+0x{off:X} still points at the JP buffer')
        for path, off in SITES:
            self.assertEqual(int.from_bytes(files[path][off:off + 4], 'big'), HOME.NAME_HOME)


if __name__ == '__main__':
    unittest.main()
