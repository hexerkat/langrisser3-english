"""test_fntsys14_hankaku_keyboard.py — hankaku name-entry keyboard (TDD guard).

v0.8 gate #2 (branch font-hankaku-per-glyph). The name-entry keyboard grid is
fntsys14 (FNT_SYS pair 13): 21 records x 5 BE16 tile cells. The composer
appends the CELL'S OWN tile code to the name buffer (character cells are
content-driven; only button actions/cursor snapping are positional — the
2026-06-11 canary tested a button). So swapping the grid cells to the hankaku
band converts the keyboard visual AND the stored name in one data change:
uppercase, lowercase and digits all hankaku (Ralf 2026-07-07), so a typed
name renders per-glyph 8px in dialogue via the F600 token = the v0.8
north-star. Button records (1488-1490, OUR arrow/END art) are preserved
verbatim; germanic keys are deferred (empty cells are likely positionally
unreachable — needs a reachability canary first).

The module is declarative (tools/fntsys14_hankaku_keyboard.py): rows of
characters resolved through font_tools.HANKAKU_TILE_MAP at encode time, so
band moves are followed automatically. Registry-toggleable
('fntsys14_hankaku_keyboard'); disabled -> the script file ships as-is
(zenkaku keyboard).

Red state: the module doesn't exist and the built FNT_SYS pair 13 carries the
zenkaku grid (UC 17-42, lc 1585-1610, digits 7-16).
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

JP_FNTSYS = PROJECT / "cache" / "fnt_sys_jp.bin"


def _cells(rec: bytes):
    """Record -> list of BE16 cell values (terminator excluded)."""
    assert rec.endswith(b"\xff\xff")
    return [struct.unpack_from(">H", rec, k)[0] for k in range(0, len(rec) - 2, 2)]


def _expected_grid():
    import font_tools as ft
    m = ft.HANKAKU_TILE_MAP
    E = 0
    rows = [
        [m[c] for c in "ABCDE"], [m[c] for c in "FGHIJ"],
        [m[c] for c in "KLMNO"], [m[c] for c in "PQRST"],
        [m[c] for c in "UVWXY"], [m["Z"], E, E, E, E],
        [E] * 5,
        [m[c] for c in "abcde"], [m[c] for c in "fghij"],
        [m[c] for c in "klmno"], [m[c] for c in "pqrst"],
        [m[c] for c in "uvwxy"], [m["z"], E, E, E, E],
        [E] * 5,
        [E, m["!"], m["?"], E, E],          # same key positions as the JP ! ?
        [E] * 5, [E] * 5,
        [m[c] for c in "12345"], [m[c] for c in "67890"],
    ]
    return rows


def test_module_generates_the_hankaku_grid():
    from fntsys14_hankaku_keyboard import hankaku_keyboard_records
    buttons = [b"\x05\xd0\x00\x00\x00\x00\x00\x00\x05\xd1\xff\xff",
               b"\x05\xd2\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff"]
    recs = hankaku_keyboard_records(buttons)
    assert len(recs) == 21
    assert all(len(r) == 12 for r in recs), "records must stay 5 cells + FFFF"
    for i, want in enumerate(_expected_grid()):
        assert _cells(recs[i]) == want, f"record {i} mismatch"
    assert recs[19] == buttons[0] and recs[20] == buttons[1]


def test_grid_tiles_are_all_in_the_hankaku_band():
    import font_tools as ft
    from fntsys14_hankaku_keyboard import hankaku_keyboard_records
    recs = hankaku_keyboard_records([b"\xff\xff", b"\xff\xff"])[:19]
    tiles = {c for r in recs for c in _cells(r) if c}
    assert tiles <= ft.HANKAKU_TILES
    # full coverage: 26 UC + 26 lc + 10 digits + ! ?
    assert len(tiles) == 64


@pytest.mark.skipif(not JP_FNTSYS.exists(), reason="JP FNT_SYS baseline absent")
def test_encode_fntsys_swaps_pair13():
    from fnt_sys_tools import encode_fntsys, parse_fnt_sys
    out = parse_fnt_sys(encode_fntsys(JP_FNTSYS.read_bytes(),
                                      PROJECT / "scripts" / "en"))
    recs = out.pairs[13].records
    assert len(recs) == 21
    for i, want in enumerate(_expected_grid()):
        assert _cells(recs[i]) == want, f"built pair13 record {i} mismatch"
    # buttons preserved from the script (our arrow/END art tiles)
    assert 0x05D0 in _cells(recs[19]) and 0x05D1 in _cells(recs[19])
    assert 0x05D2 in _cells(recs[20])


def test_built_track01_carries_the_hankaku_keyboard():
    from iso_tools import build_file_index, extract_file_data
    from fnt_sys_tools import parse_fnt_sys
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    fnt = next((extract_file_data(img, e.extent, e.size)
                for p, e in idx.items() if p.upper().endswith("FNT_SYS.BIN")), None)
    assert fnt is not None
    recs = parse_fnt_sys(fnt).pairs[13].records
    for i, want in enumerate(_expected_grid()):
        assert _cells(recs[i]) == want, f"shipped pair13 record {i} mismatch"
