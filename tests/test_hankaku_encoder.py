"""test_hankaku_encoder.py — per-glyph hankaku encoder (TDD guard, v0.8 spike).

The hankaku encoder emits ONE 8px tile per character (font_tools.HANKAKU_TILE_MAP),
NO bigrams. Control codes <$XXXX> and [diehardt's name] pass through unchanged.
This is what routes prose through the 8px-stepped dialogue renderer.
"""
import struct
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))


def _be16(*vals):
    return b"".join(struct.pack(">H", v) for v in vals)


def test_per_glyph_no_bigrams():
    from hankaku_encoder import encode_hankaku
    import font_tools as ft
    m = ft.HANKAKU_TILE_MAP
    assert encode_hankaku("Youth") == _be16(m["Y"], m["o"], m["u"], m["t"], m["h"])
    # doubled letter -> TWO identical tiles (a bigram encoder would pack one)
    assert encode_hankaku("aa") == _be16(m["a"], m["a"])


def test_control_codes_pass_through():
    from hankaku_encoder import encode_hankaku
    import font_tools as ft
    m = ft.HANKAKU_TILE_MAP
    assert encode_hankaku("Hi<$FFFC>o<$FFFE>") == _be16(m["H"], m["i"], 0xFFFC, m["o"], 0xFFFE)


def test_ellipsis_and_name_token():
    from hankaku_encoder import encode_hankaku
    import font_tools as ft
    # '…' renders 16px via the zenkaku width class -> the v0.7 ellipsis tile 906
    assert encode_hankaku("...") == _be16(ft.ELLIPSIS_TILE)
    assert encode_hankaku("[diehardt's name]") == _be16(0xF600, 0x0000)


def test_youth_line_is_all_hankaku_plus_ctrl():
    """The scen001 opening line encodes to hankaku band tiles + FFFC/FFFE only."""
    from hankaku_encoder import encode_hankaku
    import font_tools as ft
    line = ("…Youth aspiring to knighthood,<$FFFC>…Young man who weaves history,"
            "<$FFFC>Open your eyes.<$FFFE>")
    data = encode_hankaku(line)
    codes = [int.from_bytes(data[k:k + 2], "big") for k in range(0, len(data), 2)]
    band = set(ft.HANKAKU_TILE_MAP.values())
    ok = band | {0xFFFC, 0xFFFE, ft.ELLIPSIS_TILE}   # … = zenkaku 16px tile
    assert all(c in ok for c in codes), [c for c in codes if c not in ok]
    assert codes.count(0xFFFC) == 2 and codes.count(0xFFFE) == 1
