"""test_prog3_dialogue_hankaku_step.py — dialogue half-width (hankaku) step (TDD guard).

v0.8 spike (branch font-hankaku-per-glyph). RE (Ghidra + independent Fable session,
2026-07-06): the scen dialogue / nameplate text renders through the PROG_3 VDP1 grid
path `FUN_0607bf6c -> 0x0607D1C0 -> FUN_0607d168 -> FUN_0607cf80 -> FUN_0607d0b8 ->
VDP1`. In the layout `FUN_0607cf80` the per-glyph grid X byte is `baseX + column*2`;
the flush `FUN_0607d224` turns it into the sprite X `pixelX = byteX*8 + 10` (unit =
8px). So each column advances 2*8 = 16px (one 16x16 bigram tile today).

The `column*2` is ONE instruction:
    0x0607D018  333C  add r3,r3     (r3 = column; doubled -> 16px step)
r3 is set at 0x0607D004 (`mov r6,r3` = column), used ONLY by the X compute at
0x0607D038 (`add r3,r1`, r1 = baseX), and reassigned at 0x0607D044. So NOPing the
doubling makes r3 = column*1 -> `pixelX` advances 1*8 = 8px/glyph = hankaku dialogue.

Fix: 0x0607D018 `333C` (add r3,r3) -> `0009` (nop). File offset = 0x0607D018 -
0x06052800 = 0x2A818.

Red state: before tools/prog3_dialogue_hankaku_step.py is wired, the build leaves
`333C` at 0x2A818 (16px/glyph, the bigram-era step).
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

STEP_OFFSET = 0x2A818          # file offset in LANG/PROG_3.BIN
ADD_R3_R3 = b"\x33\x3c"        # SH-2 `add r3,r3` (column doubling -> 16px)
NOP = b"\x00\x09"              # SH-2 `nop` (column*1 -> 8px)


def test_jp_baseline_is_add_r3_r3():
    """The JP baseline at the patch site must be `add r3,r3` (the column doubling)."""
    jp = (PROJECT / "data/jp/prog/prog_3.bin").read_bytes()
    assert jp[STEP_OFFSET:STEP_OFFSET + 2] == ADD_R3_R3


def test_module_declares_the_nop():
    from prog3_dialogue_hankaku_step import (
        PROG3_DIALOGUE_HANKAKU_STEP, JP_BASELINE)
    patches = PROG3_DIALOGUE_HANKAKU_STEP["LANG/PROG_3.BIN"]
    assert (STEP_OFFSET, NOP) in patches
    assert JP_BASELINE[STEP_OFFSET] == ADD_R3_R3


def test_built_prog3_is_nopped():
    """If a build exists, the built PROG_3 must carry the NOP (8px step)."""
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    prog3 = next((extract_file_data(img, e.extent, e.size)
                  for p, e in idx.items() if p.upper().endswith("PROG_3.BIN")), None)
    assert prog3 is not None
    assert prog3[STEP_OFFSET:STEP_OFFSET + 2] == NOP
