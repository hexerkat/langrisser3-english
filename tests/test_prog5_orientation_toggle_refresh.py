"""test_prog5_orientation_toggle_refresh.py: the Unit Orientation toggle redraws.

PROG_5 FUN_0608e5c4 (base 0x06089000) runs the "Unit Orientation" menu: title
fntsys1 rec 21, two options rec 160 "Allies" / rec 156 "Enemies" in text nodes
0x060926C0 (X 2) and 0x060926D0 (X 13). Moving the cursor (case 2) SWAPS the
two texts between the nodes, restores the background (0x06018240) and redraws
the group (A0LANG 0x06017EF8). The redraw writes the new tilemap into the RAM
buffer (0x0604EE94 -> 0x0604F8B0) and the new glyphs into VDP2, but the copy
of the RAM tilemap to VDP2 (A0LANG 0x060186E8) is never called. Every other
PROG_5 redraw calls it (e.g. 0x0608E392 -> 0x0608E39A, 0x0608E9A2 -> 0x0608E9B6).
JP never showed it: both options are 4 equal kanji, so the old tilemap fits.
EN "Allies" is 3 wide glyphs, "Enemies" 3 wide + 1 narrow, so the old tilemap
showed "Enemie" / "s Allie" (Ymir dump ymir-dumps/facing-menu/split: VDP2 row
10 still has the old shape, the RAM buffer has the new one).

Red state (2026-10-23): case 2 of the built PROG_5 calls 0x06017EF8 and never
0x060186E8.
End state: 0x060186E8 is called right after the redraw; everything else the
toggle does (order bytes, node text pointers, flag, other calls) equals JP.

The REAL bytes (built and JP) run on tools/sh2_mini; every call into A0LANG is
intercepted and recorded.
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from sh2_mini import Sh2  # noqa: E402

PROG5_BASE = 0x06089000
ENTRY = 0x0608E5C4
STATE = 0x060925AC          # menu state byte, 2 = waiting for input
FLAG = 0x060396E3           # which option is on the left
ORDER = 0x06092ADC          # two bytes: node index of rec 160, of rec 156
NODES = 0x060926B0          # text node list (16 bytes each, text ptr at +0xC)
GROUP = 0x06092710
PRESSED = 0x06034B7C        # input mask; 0xC000 = left/right
OFFSETS_HOLDER = 0x0603A478 # fntsys1 offset table pointer
DATA_HOLDER = 0x0604E9F0    # fntsys1 data pointer
A0LANG_LO, A0LANG_HI = 0x0600E000, 0x06034A50
REDRAW = 0x06017EF8
TILEMAP_TO_VDP2 = 0x060186E8


def _prog5(path):
    from iso_tools import build_file_index, extract_file_data
    img = path.read_bytes()
    e = build_file_index(img)["LANG/PROG_5.BIN"]
    return extract_file_data(img, e.extent, e.size)


@pytest.fixture(scope="module")
def built():
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    return _prog5(max(builds, key=lambda p: p.stat().st_mtime))


@pytest.fixture(scope="module")
def jp():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR not set")
    return _prog5(sorted(Path(jp_dir).glob("*rack*01*.bin"))[0])


class _Menu(Sh2):
    """Sh2 with every call into A0LANG recorded and stubbed (r0 = 0)."""

    def __init__(self, regions):
        super().__init__(regions)
        self.calls = []

    def _step(self, pc):
        if A0LANG_LO <= pc < A0LANG_HI:
            self.calls.append((pc, self.R[4], self.R[5]))
            self.R[0] = 0
            return self.PR
        return super()._step(pc)


def _toggle(prog5, flag):
    cpu = _Menu({PROG5_BASE: prog5 + bytes(0x1000), 0x06030000: bytes(0x22800)})
    cpu.wb(STATE, 2)
    cpu.wb(FLAG, flag)
    cpu.ww(PRESSED, 0x8000)
    cpu.wl(OFFSETS_HOLDER, 0x06040000)
    cpu.wl(DATA_HOLDER, 0x06044000)
    cpu.ww(0x06040000 + 156 * 2, 0x0100)     # rec 156 Enemies
    cpu.ww(0x06040000 + 160 * 2, 0x0200)     # rec 160 Allies
    cpu.call(ENTRY)
    return {
        "calls": cpu.calls,
        "r0": cpu.R[0],
        "flag": cpu.rb(FLAG),
        "order": (cpu.rb(ORDER), cpu.rb(ORDER + 1)),
        "texts": tuple(cpu.rl(NODES + i * 0x10 + 0xC) for i in (1, 2)),
    }


@pytest.mark.parametrize("flag", [0x00, 0x01, 0xFF])
def test_toggle_copies_the_new_tilemap_to_vdp2(built, flag):
    calls = [pc for pc, _r4, _r5 in _toggle(built, flag)["calls"]]
    assert REDRAW in calls
    after = calls[calls.index(REDRAW) + 1:]
    assert after[:1] == [TILEMAP_TO_VDP2], (
        f"after the redraw the toggle calls {[hex(c) for c in after]}: the "
        "VDP2 tilemap keeps the shape of the previous texts")


@pytest.mark.parametrize("flag", [0x00, 0x01, 0xFF])
def test_toggle_otherwise_behaves_like_jp(built, jp, flag):
    got, want = _toggle(built, flag), _toggle(jp, flag)
    for key in ("r0", "flag", "order", "texts"):
        assert got[key] == want[key], key
    assert [c for c in got["calls"] if c[0] != TILEMAP_TO_VDP2] == want["calls"]
    assert (REDRAW, GROUP, 1) in got["calls"]


def test_texts_really_swap(built):
    """Sanity of the harness: the two options trade places on each toggle."""
    a, b = _toggle(built, 0x00), _toggle(built, 0xFF)
    assert a["texts"] == b["texts"][::-1] and a["texts"][0] != a["texts"][1]


def test_jp_baseline_is_what_we_patch(jp):
    import prog5_orientation_toggle_refresh as mod
    off = mod.START - PROG5_BASE
    assert jp[off:off + len(mod.JP_BASELINE)] == mod.JP_BASELINE


def test_borrowed_literal_is_the_tilemap_copy(built, jp):
    """0x0608E9FC belongs to FUN_0608e81c's pool; it must stay 0x060186E8."""
    import prog5_orientation_toggle_refresh as mod
    off = mod.TILEMAP_LIT - PROG5_BASE
    for prog5 in (built, jp):
        assert int.from_bytes(prog5[off:off + 4], "big") == TILEMAP_TO_VDP2


def test_no_outside_branch_lands_in_the_region(jp):
    """Only the replaced code itself branched inside 0x0608E6F0..0x0608E755
    (its two order-pick branches). Scans every halfword of FUN_0608e5c4 and
    its neighbours within bt/bf/bra reach for a branch into the region."""
    import prog5_orientation_toggle_refresh as mod
    lo, hi = mod.START, mod.END
    for at in range(lo - 0x1000, hi + 0x1000, 2):
        if lo <= at < hi:
            continue
        w = int.from_bytes(jp[at - PROG5_BASE:at - PROG5_BASE + 2], "big")
        if w >> 8 in (0x89, 0x8B, 0x8D, 0x8F):
            d = w & 0xFF
            target = at + 4 + (d - 0x100 if d & 0x80 else d) * 2
        elif w >> 12 in (0xA, 0xB):
            d = w & 0xFFF
            target = at + 4 + (d - 0x1000 if d & 0x800 else d) * 2
        else:
            continue
        assert not lo <= target < hi, f"branch at {at:#x} -> {target:#x}"
