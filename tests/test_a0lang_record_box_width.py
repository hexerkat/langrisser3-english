"""test_a0lang_record_box_width.py — the single-record box measures by class.

A0LANG FUN_060127A0 looks up an fntsys1 record by index, measures it at a fixed
2 cells per word and hands the count to the box builder FUN_06012AF4 (the same
centred descriptor as the location labels). Found 2026-10-08 next to the unit
splash composer. Red state: width-blind JP loop, so hybrid odd tails made the
box one cell too wide. End state: the loop asks the shared width-class cave.

The REAL bytes (JP and patched) run on tools/sh2_mini from 0x060127C0 to the
first untouched instruction 0x060127D6; r5 holds the cells there.
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import width_class as wc  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

BASE = 0x0600E000
ENTRY, STOP = 0x060127C0, 0x060127D6
STR = 0x00200000


@pytest.fixture(scope="module")
def jp_a0lang():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR not set")
    from iso_tools import build_file_index, extract_file_data
    img = sorted(Path(jp_dir).glob("*rack*01*.bin"))[0].read_bytes()
    e = build_file_index(img)["A0LANG.BIN"]
    return extract_file_data(img, e.extent, e.size)


def _patched(jp):
    import a0lang_record_box_width as mod
    out = bytearray(jp)
    for off, data in mod.A0LANG_RECORD_BOX_WIDTH["A0LANG.BIN"]:
        out[off:off + len(data)] = data
    return bytes(out)


def _measure(a0lang, tiles, index=0x4D, arg=0x9):
    s = b"".join(t.to_bytes(2, "big") for t in tiles) + b"\xff\xff"
    cpu = Sh2({BASE: a0lang, wc.WIDTH_CAVE_ADDR: wc.cave_blob(), STR: s + bytes(8)})
    cpu.call(ENTRY, {2: STR, 4: index, 5: 0, 6: arg}, stop=STOP)
    return cpu


def test_jp_baseline_is_what_we_patch(jp_a0lang):
    import a0lang_record_box_width as mod
    for off, data in mod.JP_BASELINE.items():
        assert jp_a0lang[off:off + len(data)] == data, hex(off)


def test_jp_loop_is_width_blind(jp_a0lang):
    assert _measure(jp_a0lang, [1300, 1301, 1302]).R[5] == 6


def test_patched_loop_measures_by_class(jp_a0lang):
    a0 = _patched(jp_a0lang)
    for tiles in ([], [500] * 9, [1300, 1301, 1302], [7, 1265, 1349, 1350, 43, 0]):
        assert _measure(a0, tiles).R[5] == wc.cells(tiles), tiles


def test_index_and_arg_survive_the_loop(jp_a0lang):
    cpu = _measure(_patched(jp_a0lang), [1300, 500], index=0x4D, arg=0x9)
    assert (cpu.R[4], cpu.R[6]) == (0x4D, 0x9)


def test_registered_in_build():
    import a0lang_record_box_width as mod
    sys.path.insert(0, str(PROJECT))
    import build
    assert build.ENGINE_MODULE_DICTS["a0lang_record_box_width"] is mod.A0LANG_RECORD_BOX_WIDTH
