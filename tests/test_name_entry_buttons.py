"""Name-entry keyboard buttons (tiles 1488-1490) carry OUR art.

fntsys14's keyboard rows reference these three tiles as function keys.
2026-06-11 (user): ADV = right arrow, BAK = left arrow (EagleIII
arrowhead, extended shaft), END = condensed "END" in one 16x16 tile —
replacing the 0.2 patch stacked-letter icons.
"""

import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "tools"))

import font_tools as ft  # noqa: E402

JP_FONT = PROJ / 'data' / 'jp' / 'font_jp.bin'


@pytest.fixture(scope='module')
def font():
    if not JP_FONT.exists():
        pytest.skip('JP FONT.BIN not present')
    return ft.generate_english_font(JP_FONT.read_bytes())


def test_buttons_are_our_art(font):
    for idx, data in ft._NAME_ENTRY_BUTTON_TILES.items():
        assert font[idx * 32:(idx + 1) * 32] == data, f"tile {idx}"


def test_arrows_mirror_each_other():
    adv = ft._NAME_ENTRY_BUTTON_TILES[1488]
    bak = ft._NAME_ENTRY_BUTTON_TILES[1489]

    def mirror_row(v):
        return int(f'{v:016b}'[::-1], 2)

    for row in range(16):
        a = int.from_bytes(adv[row * 2:row * 2 + 2], 'big')
        b = int.from_bytes(bak[row * 2:row * 2 + 2], 'big')
        assert mirror_row(a) == b, f"row {row}: arrows are not mirrored"


def test_end_tile_has_ink(font):
    end = ft._NAME_ENTRY_BUTTON_TILES[1490]
    assert any(end), "END tile is blank"


def _ink_columns(tile):
    cols = set()
    for row in range(16):
        v = int.from_bytes(tile[row * 2:row * 2 + 2], 'big')
        cols |= {c for c in range(16) if v >> (15 - c) & 1}
    return min(cols), max(cols)


def test_arrows_sit_centered_clear_of_the_edges():
    """Playtest 2026-10-13: the ADV tip ran to column 14 and was cut. The
    arrows keep two blank columns on each side and center within 1px.
    Red state: the 2026-06-11 art spans columns 1..14."""
    for idx in (1488, 1489):
        lo, hi = _ink_columns(ft._NAME_ENTRY_BUTTON_TILES[idx])
        assert lo >= 2 and hi <= 13, f"tile {idx}: ink in columns {lo}..{hi}"
        assert abs((lo + hi) / 2 - 7.5) <= 1, f"tile {idx}: off center"


# The EagleIII 8x16 "→" / "←" (data/fonts/Mx437_CL_EagleIII_8x16.ttf, the
# face of the 8px letters), rasterized as in tools/font_jbm_generate.py.
_EAGLE_RIGHT = [0x00, 0x00, 0x00, 0x00, 0x08, 0x0C, 0x0E, 0xFF,
                0x0E, 0x0C, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00]
_EAGLE_LEFT = [0x00, 0x00, 0x00, 0x00, 0x10, 0x30, 0x70, 0xFF,
               0x70, 0x30, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00]


def test_arrows_are_the_font_arrows_centered():
    """Playtest 2026-10-13: the bold arrow was too thick. Ralf: it must be
    the equivalent of the font's own arrow. The tile draws the EagleIII
    glyph unchanged, in columns 4..11 of the 16px cell.
    Red state: the bold art (3px shaft, columns 2..12)."""
    for idx, glyph in ((1488, _EAGLE_RIGHT), (1489, _EAGLE_LEFT)):
        want = b''.join((row << 4).to_bytes(2, 'big') for row in glyph)
        assert ft._NAME_ENTRY_BUTTON_TILES[idx] == want, f"tile {idx}"


def test_glue_arrow_tile_44_is_the_keyboard_arrow(font):
    """Tile 44 (the dialogue glue arrow, "[Name]→Level rose!") draws the
    same arrow as the ADV key (Ralf 2026-10-13: one arrow everywhere)."""
    assert font[44 * 32:45 * 32] == ft._NAME_ENTRY_BUTTON_TILES[1488]
