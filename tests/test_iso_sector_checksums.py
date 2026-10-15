"""Every Track 01 sector the patch writes carries a valid CD checksum, and the
rebuild moves each sector once.

Red state (2026-10-15, measured on the JP disc and the v0.7.2 build):
  - `rewrite_sector_edc_ecc` wrote a non-standard ECC (P and Q parity): it
    reproduced 0 of 338 sampled JP sectors (the EDC was right in all 338).
    Every sector the patch moved or rewrote shipped a wrong ECC. Emulators
    ignore it; a real Saturn drive reading a burned disc uses it to correct
    read errors, so a wrong one can turn good data bad.
  - `rebuild_iso_batch` shifted the whole tail of the disc once per grown
    file (5 files, about 137,000 sector rewrites at 1.6 ms each), 180 s of
    a 193 s build.

Truth: the JP disc's own sectors (ECMA-130 Mode 1, EDC + P/Q parity).
"""
import os
import sys
import time
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / 'tools'))

import iso_tools as it  # noqa: E402

SS = it.SECTOR_SIZE
JP_DIR = os.environ.get('LANG3_JP_DIR')


def _jp_track01() -> bytes:
    if not JP_DIR:
        pytest.skip('LANG3_JP_DIR not set')
    cands = sorted(Path(JP_DIR).glob('*rack*01*.bin'))
    if not cands:
        pytest.skip('no JP Track 01 .bin')
    return cands[0].read_bytes()


def _built_track01() -> bytes:
    builds = list((PROJ / 'build').glob('*/track01.bin'))
    if not builds:
        pytest.skip('no build/*/track01.bin (run build.py first)')
    return max(builds, key=lambda p: p.stat().st_mtime).read_bytes()


def _bad_sectors(image: bytes) -> list[int]:
    bad = []
    for i in range(len(image) // SS):
        raw = image[i * SS:(i + 1) * SS]
        fixed = bytearray(raw)
        it.rewrite_sector_edc_ecc(fixed)
        if fixed != raw:
            bad.append(i)
    return bad


# --- the checksum itself, against the pressed disc --------------------------

def test_checksum_reproduces_the_jp_disc():
    image = _jp_track01()
    assert _bad_sectors(image[:SS * 400]) == []
    tail = len(image) // SS - 400
    assert _bad_sectors(image[tail * SS:]) == []


def test_moving_a_sector_equals_writing_it_fresh():
    image = _jp_track01()
    for lba in (16, 1000, 20000, 32779):
        raw = image[lba * SS:(lba + 1) * SS]
        for new_lba in (lba + 1, lba + 987, lba + 4500):
            assert it.move_sector(raw, new_lba) == \
                it._make_sector(new_lba, raw[16:16 + it.USER_SIZE])


def test_checksum_is_fast_enough():
    """A full build rewrites tens of thousands of sectors."""
    sector = it._make_sector(1234, bytes(range(256)) * 8)
    t = time.perf_counter()
    for _ in range(200):
        it.rewrite_sector_edc_ecc(sector)
    assert (time.perf_counter() - t) / 200 < 0.0005   # 1.6 ms before


# --- the rebuild -------------------------------------------------------------

def _image(sectors):
    return b''.join(it._make_sector(i, bytes([i % 251]) * it.USER_SIZE)
                    for i in range(sectors))


def _entry(path, extent, size, slot):
    return it.ISOEntry(path, extent, size, False, it.USER_OFFSET + 64 * slot)


def _batch():
    image = _image(120)
    index = {'A': _entry('A', 10, 2048, 0), 'B': _entry('B', 40, 3000, 1),
             'C': _entry('C', 70, 2048, 2), 'D': _entry('D', 90, 2048, 3)}
    patches = [('C', b'c' * 3 * 2048), ('A', b'a' * 2 * 2048),
               ('B', b'b' * 100), ('D', b'd' * 2049)]
    image = bytearray(image)
    for e in index.values():       # the records start out right, like a disc's
        it.update_dir_record_extent(image, e.record_offset, e.extent, e.size)
    return image, index, patches


def test_rebuild_moves_each_sector_once(monkeypatch):
    image, index, patches = _batch()
    moves = []
    real = it.move_sector
    monkeypatch.setattr(it, 'move_sector',
                        lambda raw, lba: moves.append(lba) or real(raw, lba))
    it.rebuild_iso_batch(bytearray(image), index, patches)
    # every sector after A's old end (sector 11) moves, none twice, none of
    # the sectors the grown files replace
    assert len(moves) == len(set(moves))
    assert len(moves) == 120 - 11 - 1 - 1


def test_rebuild_layout_and_checksums():
    image, index, patches = _batch()
    out = it.rebuild_iso_batch(bytearray(image), index, patches)
    assert len(out) // SS == 120 + 1 + 2 + 1
    assert _bad_sectors(out) == []
    want = {'A': (10, b'a' * 2 * 2048), 'B': (41, b'b' * 100),
            'C': (71, b'c' * 3 * 2048), 'D': (93, b'd' * 2049)}
    for path, (extent, data) in want.items():
        got = it.extract_file_data(bytes(out), extent, len(data))
        assert got == data, path
        rec = index[path].record_offset
        assert int.from_bytes(out[rec + 2:rec + 6], 'little') == extent, path
        assert int.from_bytes(out[rec + 10:rec + 14], 'little') == len(data), path
    # an untouched sector keeps its content at its new place: old 50 -> 51
    assert out[51 * SS + 16:51 * SS + 32] == bytes([50]) * 16
    # and an untouched one after D: old 100 -> 104
    assert out[104 * SS + 16:104 * SS + 32] == bytes([100]) * 16


def test_built_track01_has_only_valid_sectors():
    assert _bad_sectors(_built_track01()) == []
