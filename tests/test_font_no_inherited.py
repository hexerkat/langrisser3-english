"""test_font_no_inherited.py — locks the font disembark invariant.

User rule (2026-06-13): the generated FONT.BIN must contain ONLY glyphs we
draw ourselves (Eagle III), with exactly two exceptions inherited from the
**Japanese** baseline: the formation glyphs (囗 ｜ ― ＼ ／) and the star
(`*` → tile 489, the JP full-width ＊). No byte may be inherited from the
third-party 0.2 patch.

This test pins that:
  - formations + star are byte-identical to the JP original (JP-preserved);
  - the three orphan engine-UI slots (766="Uü", 1041="Rü", 1630=decoration)
    that the 0.2 patch hand-drew are now BLANK (our zeros), not inherited;
  - the 1500-1620 menu range is drawn via the composing _MENU_GLYPHS spec
    (no raw byte-blob, so the write-then-override waste can't creep back).
"""

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import font_tools as ft

JP_FONT = PROJECT / "data" / "jp" / "font_jp.bin"
TILE = 32
BLANK = b"\x00" * TILE


def _require_jp():
    if not JP_FONT.exists():
        pytest.skip("data/jp/font_jp.bin not present (run build.py once)")


def _generated():
    _require_jp()
    return ft.generate_english_font(JP_FONT.read_bytes())


def _tile(buf, i):
    return buf[i * TILE:(i + 1) * TILE]


def test_formations_and_star_are_jp_preserved():
    jp = JP_FONT.read_bytes()
    gen = _generated()
    keep = list(ft._FORMATION_GLYPH_TILES.values()) + [ft.CHAR_TILE_MAP["*"]]
    for idx in keep:
        assert _tile(gen, idx) == _tile(jp, idx), (
            f"tile {idx} must stay JP-preserved (formation/star)")


def test_unmapped_tiles_are_blank():
    """No 0.2-patch (or any) inheritance: the data-driven generator starts from a
    BLANK buffer, copies only the PRESERVED tiles (from the JP-based legacy
    generator) and composes the mapped bigrams — so every tile that is neither
    preserved nor a mapped bigram is left blank. Dead slots carry no inherited
    pixels by construction.

    Supersedes the old per-slot 766/1041/1630 blank check + the _MENU_GLYPHS
    source inspection: the Part 6 packing reclaims those former orphan slots with
    OUR composed glyphs, and the menu range is now JP-preserved, not redrawn."""
    gen = _generated()
    from balloon_zenkaku_cave import CAVE_TILE, CAVE_TILES
    from name_twin_cave import NAME_TWIN_CAVE_TILE, NAME_TWIN_CAVE_TILES
    from width_class import WIDTH_CAVE_TILE, WIDTH_CAVE_TILES
    import a0lang_save_name_pack as NP
    # HANKAKU_TILES = the v0.8 per-glyph 8px band (mapped via HANKAKU_TILE_MAP).
    # TWIN_TILE_MAP = the v4 name-entry display twins (centered 16px keys).
    # CAVE tiles = the v0.8 width-class + name-twin code riding
    # the font, and the 16-letter name save PACK/UNPACK caves. NAKAGURO_TILE = the rehomed JP objectives bullet ・.
    used = (ft.PRESERVED_TILES | set(ft.BIGRAM_TILE_MAP.values()) | ft.HANKAKU_TILES
            | set(ft.TWIN_TILE_MAP.values())
            | set(range(CAVE_TILE, CAVE_TILE + CAVE_TILES))
            | set(range(NAME_TWIN_CAVE_TILE,
                        NAME_TWIN_CAVE_TILE + NAME_TWIN_CAVE_TILES))
            | set(range(WIDTH_CAVE_TILE, WIDTH_CAVE_TILE + WIDTH_CAVE_TILES))
            | set(range(NP.PACK_TILE, NP.PACK_TILE + NP.PACK_TILES))
            | set(range(NP.UNPACK_TILE, NP.UNPACK_TILE + NP.UNPACK_TILES))
            | {ft.NAKAGURO_TILE})
    junk = [t for t in range(ft.NEW_FONT_TILES)
            if t not in used and _tile(gen, t) != BLANK]
    assert not junk, (
        f"{len(junk)} unmapped tiles carry non-blank (inherited) pixels: {junk[:10]}")
