"""The title menu box is the same with and without a save.

The title menu group (RAM 0x060333C4: +4 parent X, +5 parent Y, +8 width,
+9 height) is written by one of two A0LANG paths. With a save (START, LOAD,
OPTIONS) the code at PC 0x06015CC6 runs; with no save (START, OPTIONS) the
code at PC 0x06015D5E. Both run here on tools/sh2_mini, real bytes.

Red state (2026-10-17, Windows playtest on a fresh memory, user: "a com start
e options e a com start load options deveria ter o mesmo tamanho e posicao"):
the save path was narrowed to X 14 / width 12, the no-save path kept the JP
X 12 / width 19. Its width shares one immediate with its Y, so the no-save
patch reorders that sequence instead of changing one byte.

The heights differ by design: 8 rows for three items, 6 for two, and the
no-save box sits one row lower, so both are centered on the same row (JP).
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from sh2_mini import Sh2  # noqa: E402

BASE = 0x0600E000
GROUP = 0x060333C4
RAM = 0x06033000
WITH_SAVE = (0x06015CC6, 0x06015CEC)
NO_SAVE = (0x06015D5E, 0x06015D82)


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
    from a0lang_title_menu_geometry import A0LANG_TITLE_MENU_GEOMETRY as GEO
    out = bytearray(jp)
    for off, data in GEO["A0LANG.BIN"]:
        out[off:off + len(data)] = data
    return bytes(out)


def _box(a0lang, path):
    """(parent X, parent Y, width, height) the path writes."""
    cpu = Sh2({BASE: a0lang, RAM: bytes(0x1000)})
    cpu.call(path[0], stop=path[1])
    return tuple(cpu.rb(GROUP + d) for d in (4, 5, 8, 9))


def test_jp_boxes(jp_a0lang):
    assert _box(jp_a0lang, WITH_SAVE) == (11, 18, 19, 8)
    assert _box(jp_a0lang, NO_SAVE) == (12, 19, 19, 6)


def test_no_save_box_matches_the_save_box(jp_a0lang):
    a0 = _patched(jp_a0lang)
    x, y, w, h = _box(a0, WITH_SAVE)
    assert (x, y, w, h) == (14, 18, 12, 8)
    assert _box(a0, NO_SAVE) == (x, 19, w, 6)


def test_no_save_path_keeps_its_instruction_count(jp_a0lang):
    """Only bytes inside the no-save sequence change; the code after it is JP."""
    a0 = _patched(jp_a0lang)
    lo, hi = NO_SAVE[0] - BASE, NO_SAVE[1] - BASE
    assert a0[hi:hi + 0x100] == jp_a0lang[hi:hi + 0x100]
    assert len(a0) == len(jp_a0lang)
    changed = [i for i in range(len(a0)) if a0[i] != jp_a0lang[i]]
    assert all(lo <= i < hi or i in (0x7CD3, 0x7CE3) for i in changed), [hex(i) for i in changed]
