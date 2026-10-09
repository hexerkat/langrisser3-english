"""test_width_class_cave.py — the shared width-class rule and its font cave.

Red state (2026-10-08): tools/width_class.py does not exist. The narrow (8px)
class is copied as an inline range test into four patches, and the engine glue
before a number is a 16px blank (tile 0) because no 8-bit `mov #imm` tile can
reach the band at 1265 (RE: archive/docs/20261008_hybrid_fntsys_surfaces_re.md).

End state: ONE rule. Narrow = the hankaku band [1265..1349] plus the glue
tile 43 (a blank, reachable by `mov #0x2B`). The font cave `is_narrow` executes
that rule for the two measurers; the cave bytes are run here on the SH-2
interpreter and must agree with the Python rule for every boundary.
"""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import width_class as wc  # noqa: E402
from sh2_mini import Sh2  # noqa: E402

PROBES = [0, 1, 7, 16, 42, 43, 44, 0x2C, 0x7F, 500, 1264, 1265, 1300, 1327,
          1349, 1350, 1416, 1428, 1690, 0xF600, 0xFFFC, 0xFFFE]


def test_rule():
    assert wc.NARROW_GLUE_TILE == 43
    assert wc.NARROW_GLUE_TILE <= 0x7F, "must be reachable by mov #imm8"
    assert wc.is_narrow_tile(43)
    assert wc.is_narrow_tile(1265) and wc.is_narrow_tile(1349)
    for t in (0, 42, 44, 1264, 1350, 0xF600):
        assert not wc.is_narrow_tile(t), t


def test_cave_fits_free_font_tiles():
    import font_tools as ft
    blob = wc.cave_blob()
    assert len(blob) <= wc.WIDTH_CAVE_TILES * 32
    tiles = set(range(wc.WIDTH_CAVE_TILE, wc.WIDTH_CAVE_TILE + wc.WIDTH_CAVE_TILES))
    assert tiles <= set(ft.V08_RESERVED_TILES)
    taken = (set(ft.BIGRAM_TILE_MAP.values()) | set(ft.HANKAKU_TILE_MAP.values())
             | set(ft.TWIN_TILE_MAP.values()) | {ft.NAKAGURO_TILE})
    assert not tiles & taken


def _run(tile, extra=None):
    cpu = Sh2({wc.WIDTH_CAVE_ADDR: wc.cave_blob()})
    regs = {r: 0x1000 + r for r in range(1, 15)}
    regs[0] = tile if tile < 0x8000 else tile - 0x10000   # mov.w sign-extends
    cpu.call(wc.WIDTH_CAVE_ADDR, regs)
    return cpu, regs


def test_cave_executes_the_rule():
    for t in PROBES:
        cpu, _ = _run(t)
        assert cpu.T == int(wc.is_narrow_tile(t)), f"tile {t}"


def test_cave_preserves_every_register_but_r0():
    for t in (43, 1300, 500, 0xF600):
        cpu, regs = _run(t)
        for r in range(1, 15):
            assert cpu.R[r] == regs[r] & 0xFFFFFFFF, f"r{r} clobbered (tile {t})"
        assert cpu.R[15] == 0x060FFF00, "stack not balanced"


def test_built_font_carries_the_cave_and_a_blank_glue():
    from iso_tools import build_file_index, extract_file_data
    import pytest
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    font = next(extract_file_data(img, e.extent, e.size)
                for p, e in idx.items() if p.upper().endswith("FONT.BIN"))
    blob = wc.cave_blob()
    at = wc.WIDTH_CAVE_TILE * 32
    assert font[at:at + len(blob)] == blob
    g = wc.NARROW_GLUE_TILE * 32
    assert not any(font[g:g + 32]), "glue tile must draw nothing"


def test_balloon_dispatcher_uses_the_same_rule():
    """The PROG_3 balloon cave (inline test, it cannot call: its narrow path
    tail-jumps into cf80 with the caller's PR) must classify exactly like the
    rule. Narrow = reaches cf80 by the tail jump (PR untouched); wide = reaches
    cf80 through its own jsr (left half first)."""
    import balloon_zenkaku_cave as bc
    from sh2_mini import RETURN_SENTINEL
    font = bytearray(1700 * 32)
    blob = bc.cave_blob()
    font[bc.CAVE_TILE * 32:bc.CAVE_TILE * 32 + len(blob)] = blob
    for t in PROBES:
        if t >= 0x8000:
            continue        # control words never reach the draw dispatcher
        cpu = Sh2({bc.FONT_LWRAM_BASE: bytes(font), 0x00200000: t.to_bytes(2, "big") + bytes(6)})
        cpu.call(bc.CAVE_ADDR, {4: 0, 5: 0x00200000, 6: 3, 7: 1}, stop=bc.CF80_ADDR)
        narrow_path = cpu.PR == RETURN_SENTINEL
        assert narrow_path == wc.is_narrow_tile(t), f"tile {t}"
