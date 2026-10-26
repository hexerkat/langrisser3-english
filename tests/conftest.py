"""Session setup shared by the whole suite.

The font style (build.py --font) only changes pixels, but the tests that read
the newest build/*/track01.bin back through the half-glyph alphabet
(tools/ui_compose.CellReader) must compare against the style that build used.
The style is recognised from the build's own FONT.BIN: the hankaku band tile
of 'a' is that style's 'a' half-glyph.
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))


def built_font_style():
    """The font style of the newest build, or None (no build, or unknown art)."""
    import font_tools as ft
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        return None
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    entry = build_file_index(img).get("LANG/FONT.BIN")
    if entry is None:
        return None
    font = extract_file_data(img, entry.extent, entry.size)
    t = ft.HANKAKU_TILE_MAP["a"]
    for name, style in ft.FONT_STYLES.items():
        if font[t * 32:(t + 1) * 32] == ft._interleave(style.LETTERS["a"], bytes(16)):
            return name
    return None


@pytest.fixture(scope="session", autouse=True)
def _font_style_of_the_build():
    import font_tools as ft
    style = built_font_style()
    if style is not None:
        ft.apply_style(style)
    yield
