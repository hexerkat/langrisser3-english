"""test_a0lang_centered_box_width.py — the centred message box measures by class.

A0LANG FUN_06012c98 (LOAD/SAVE box via FUN_06013d80, PROG_3 x2, PROG_5
FUN_0608cb7c) measures its string at a fixed 2 cells per word, then builds the
box: X = 18 - cells/2, W = cells + 4. Red state (2026-10-08): with hybrid
records an odd word tail is ONE 8px cell, so the box came out one cell too wide
and the text half a cell off centre. End state: the loop asks the shared
width-class cave (tools/width_class.py) per word.

The REAL bytes run on tools/sh2_mini (JP baseline and patched), from the pool
load at 0x06012CE2 to the first untouched instruction at 0x06012D0A.
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
ENTRY, STOP = 0x06012CE2, 0x06012D0A
STR = 0x00200000
FRAME = 0x060F0000


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
    import a0lang_centered_box_width as mod
    out = bytearray(jp)
    for off, data in mod.A0LANG_CENTERED_BOX_WIDTH["A0LANG.BIN"]:
        out[off:off + len(data)] = data
    return bytes(out)


def _measure(a0lang, tiles):
    s = b"".join(t.to_bytes(2, "big") for t in tiles) + b"\xff\xff"
    cpu = Sh2({BASE: a0lang, wc.WIDTH_CAVE_ADDR: wc.cave_blob(),
               STR: s + bytes(16), FRAME: bytes(0x100)})
    cpu.call(ENTRY, {4: STR, 14: FRAME, 3: FRAME, 1: FRAME}, stop=STOP)
    return cpu.R[3] & 0xFFFF


def test_jp_baseline_is_what_we_patch(jp_a0lang):
    import a0lang_centered_box_width as mod
    for off, data in mod.JP_BASELINE.items():
        assert jp_a0lang[off:off + len(data)] == data, hex(off)


def test_jp_loop_is_width_blind(jp_a0lang):
    assert _measure(jp_a0lang, [1300, 1301, 1302]) == 6


def test_patched_loop_measures_by_class(jp_a0lang):
    a0 = _patched(jp_a0lang)
    cases = [[], [500] * 9, [1300, 1301, 1302], [7, 1265, 1349, 1350, 43, 0],
             [0xF600, 0x0000, 1300]]
    for tiles in cases:
        assert _measure(a0, tiles) == wc.cells(tiles), tiles


def test_wide_only_strings_match_jp(jp_a0lang):
    a0 = _patched(jp_a0lang)
    for tiles in ([500] * 9, [7, 8, 9, 0, 1690], []):
        assert _measure(a0, tiles) == _measure(jp_a0lang, tiles)
