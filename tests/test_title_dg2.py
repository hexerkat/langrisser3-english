"""Round-trip / lossless guards for the TITLE.DG2 codec (tools/title_dg2.py).

TITLE.DG2 is the title-screen CG container. We decode its logo pattern-name map
(res1, a 16-bit-per-cell row-major grid) so we can add a footer credit line by
overwriting currently-empty cells, then re-pack. These tests PIN that the codec
is byte-lossless: decode->encode with no edits must reproduce the input exactly,
so a footer edit changes ONLY the cells we touch.

Red state (before tools/title_dg2.py exists): import fails.
"""
import os
import struct
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tools import title_dg2  # noqa: E402
from tools.iso_tools import build_file_index, extract_file_data  # noqa: E402

JP_DIR = Path(os.environ.get(
    "LANG3_JP_DIR",
    "/home/ralf/Jogos/emulacao/romsets/sega-saturn/cue-bin/Langrisser III (Japan)",
))


def _load_title_dg2() -> bytes:
    track1 = sorted(JP_DIR.glob("*rack*01*.bin"))
    if not track1:
        pytest.skip(f"JP track01 not found under {JP_DIR}")
    img = bytearray(track1[0].read_bytes())
    idx = build_file_index(img)
    key = next(k for k in idx if k.upper().endswith("TITLE.DG2"))
    e = idx[key]
    return extract_file_data(img, e.extent, e.size)


@pytest.fixture(scope="module")
def dg2() -> bytes:
    return _load_title_dg2()


def test_container_parses_to_four_resources(dg2):
    cont = title_dg2.parse_container(dg2)
    assert len(cont.resources) == 4
    # offsets+sizes tile the whole file with no gaps/overlap
    assert cont.resources[0].offset == 0x24
    assert sum(r.size for r in cont.resources) + 0x24 == len(dg2)


def test_container_repack_is_byte_identical(dg2):
    """Re-packing an unmodified container reproduces the original bytes."""
    cont = title_dg2.parse_container(dg2)
    assert title_dg2.pack_container(cont) == dg2


def test_logo_grid_known_cells(dg2):
    """The cracked grid must read the known logo content (row 6 = 'LANG...')."""
    grid = title_dg2.decode_logo_grid(dg2)
    # row 6: col1=tile1, col2=tile2, col6=tile3 (empties between)
    assert grid.tile(6, 0) == 0
    assert grid.tile(6, 1) == 1
    assert grid.tile(6, 2) == 2
    assert grid.tile(6, 6) == 3
    # footer rows are currently empty
    for r in range(23, 28):
        assert all(grid.tile(r, c) == 0 for c in range(grid.width))


def test_logo_grid_roundtrip_lossless(dg2):
    """decode -> encode with no edits reproduces the whole DG2 byte-for-byte."""
    grid = title_dg2.decode_logo_grid(dg2)
    out = title_dg2.encode_logo_grid(dg2, grid)
    assert out == dg2


def test_set_footer_changes_only_footer_bytes(dg2):
    """Writing a footer cell touches only that cell; size is preserved."""
    grid = title_dg2.decode_logo_grid(dg2)
    grid.set_tile(25, 10, 42)  # arbitrary existing tile in the footer area
    out = title_dg2.encode_logo_grid(dg2, grid)
    assert len(out) == len(dg2)
    # only bytes of that one 16-bit cell may differ (high byte may coincide)
    diffs = [i for i in range(len(dg2)) if out[i] != dg2[i]]
    res1_off = title_dg2.parse_container(dg2).resources[title_dg2.LOGO_RES_INDEX].offset
    cell_off = res1_off + title_dg2.GRID_BASE + (25 * title_dg2.GRID_W + 10) * 2
    assert set(diffs) <= {cell_off, cell_off + 1}
    assert struct.unpack(">H", out[cell_off:cell_off + 2])[0] == 42


def test_credit_atlas_is_committed():
    """The credit is MANDATORY — its glyphs must exist in the repo so no build
    can silently lose it."""
    assert title_dg2.CREDIT_ATLAS.exists(), f"missing: {title_dg2.CREDIT_ATLAS}"


def test_credit_is_not_a_toggleable_module():
    """The title credit must not be disableable via the patch registry."""
    from tools import patch_registry
    assert "title_credit" not in patch_registry.ALL_MODULES


def test_applied_credit_is_non_empty(dg2):
    """A built title must carry a non-empty footer credit (the MANDATORY line)."""
    out = title_dg2.apply_credit_line(dg2, "English patch 0.7.2 / Hexerkat & RalfGuth \u2022 2026")
    assert title_dg2.footer_cell_count(out) > 0
    assert title_dg2.footer_cell_count(dg2) == 0  # JP original has none
