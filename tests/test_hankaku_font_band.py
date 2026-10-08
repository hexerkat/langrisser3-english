"""test_hankaku_font_band.py — v0.8 per-glyph hankaku font band (TDD guard).

Spike (branch font-hankaku-per-glyph). The dialogue renderer patched to step 8px
(prog3_dialogue_hankaku_step) needs glyphs whose ink lives in the LEFT 8px of the
16x16 tile (right half blank, overdrawn by the next glyph). font_tools already holds
8px half-glyphs (the bigram source); a hankaku tile is just
`_interleave(half_glyph[ch], _BLANK_GLYPH)`.

This guards a dedicated HANKAKU band placed in the free tile range 1265-1469 (all
blank in the current font, below every engine-fixed band: keyboard 1488-1490, CWX
1500-1620). One tile per character; NO bigram pairing.

Red state: before the band is added to font_tools, HANKAKU_TILE_MAP doesn't exist.
"""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

# every distinct char in the scen001 opening Lushiris line (the spike test line)
YOUTH_CHARS = set("OYaspiringtoknighthoodmwvehistory,. ") | {"…"}


def test_band_covers_the_youth_line():
    import font_tools as ft
    for ch in YOUTH_CHARS:
        assert ch in ft.HANKAKU_TILE_MAP, f"hankaku band missing {ch!r}"


def test_band_indices_are_free_and_unique():
    import font_tools as ft
    idxs = list(ft.HANKAKU_TILE_MAP.values())
    assert len(idxs) == len(set(idxs)), "duplicate hankaku tile indices"
    assert all(1265 <= i <= 1469 for i in idxs), "band outside the free 1265-1469 range"


def test_band_tiles_are_left8px_hankaku():
    """Each band tile = the char's 8px half-glyph in the LEFT columns, right half blank."""
    import font_tools as ft
    jp = (PROJECT / "data/jp/font_jp.bin").read_bytes()
    font = ft.generate_english_font(jp)
    for ch in ["Y", "o", "u", "t", "h", ".", ","]:
        idx = ft.HANKAKU_TILE_MAP[ch]
        tile = font[idx * 32:(idx + 1) * 32]
        assert tile != b"\x00" * 32, f"hankaku tile for {ch!r} is blank"
        # right 8px (odd bytes = cols 8-15) must be blank
        right = tile[1::2]
        assert right == b"\x00" * 16, f"hankaku {ch!r} has ink in the right 8px"
