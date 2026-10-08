"""test_d00_full_hankaku_conversion.py — ALL D00 prose through the hankaku
encoder (TDD guard, v0.8 conversion).

Ralf 2026-07-07: "faça a conversão total para usar o novo encoder de hankaku
com alguns glifos zenkaku". Every scen entry is routed through
hankaku_encoder.encode_hankaku:

  - band chars (A-z, digits, punct incl. the NEW ( ) " % & + / *) -> 1 tile,
    8px via the width-class dispatch;
  - anything else in CHAR_TILE_MAP (•, full-width SCENARIO letters, the
    ideographic space 　 -> tile 0, ‐, …=906) -> ZENKAKU single, 16px over
    2 columns — "alguns glifos zenkaku";
  - chars in neither map -> dropped (the SAME drop set as the bigram
    encoder, so encoder-drop layout tricks keep working);
  - control codes / F600 pass through -> structural parity preserved.

The hankaku band grew to cover prose punctuation with existing 8px art, so
the zenkaku dispatch cave moved up (scratch 1420, code 1421+) to leave band
headroom 1265-1419.

Red state: only the scen001 spike entry routes hankaku; every other entry is
bigram-encoded, and the built D00 is full of bigram tiles.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))


def test_every_entry_routes_hankaku():
    from d00_tools import is_hankaku_entry
    assert is_hankaku_entry(1, "…Youth aspiring to knighthood,")
    assert is_hankaku_entry(44, "Any line of any scen")
    assert is_hankaku_entry(125, "<$FFFF>Castle Gate")
    # scen124 included since Piece D (prog3_d00_offset_scale lifted the u16
    # section ceiling to 128 KB) — no exceptions remain.
    assert is_hankaku_entry(124, "epilogue prose")


def test_band_covers_prose_punctuation():
    import font_tools as ft
    for ch in "()\"%&+/":
        assert ch in ft.HANKAKU_TILE_MAP, f"band missing {ch!r}"
    # '*' is NOT prose: it is the objectives-header marker and must render
    # as the original JP full-width asterisk ＊ (tile 489), like '•' does
    # (Ralf 2026-07-08: "existe um glifo original do JP que é esse asteriscão").
    assert "*" not in ft.HANKAKU_TILE_MAP


def test_encoder_zenkaku_fallback():
    from hankaku_encoder import encode_hankaku
    import font_tools as ft

    def be16(*v):
        return b"".join(struct.pack(">H", x) for x in v)

    m = ft.HANKAKU_TILE_MAP
    # bullet -> zenkaku single 1657; ideographic space -> tile 0 (16px blank)
    assert encode_hankaku("•a") == be16(ft.CHAR_TILE_MAP["•"], m["a"])
    assert encode_hankaku("　") == be16(0)
    # full-width SCENARIO letters -> zenkaku singles
    assert encode_hankaku("Ｓ") == be16(ft.CHAR_TILE_MAP["Ｓ"])
    # band punct is hankaku, not the old zenkaku singles
    assert encode_hankaku("(a)") == be16(m["("], m["a"], m[")"])
    # objectives-header asterisk -> the JP full-width ＊ (zenkaku 489)
    assert encode_hankaku("*V") == be16(ft.CHAR_TILE_MAP["*"], m["V"])


def test_band_and_cave_are_disjoint_after_growth():
    import font_tools as ft
    import balloon_zenkaku_cave as cave
    assert max(ft.HANKAKU_TILES) <= cave.HANKAKU_HI < cave.SCRATCH_TILE
    tiles = set(range(cave.CAVE_TILE, cave.CAVE_TILE + cave.CAVE_TILES))
    tiles.add(cave.SCRATCH_TILE)
    assert not tiles & ft.HANKAKU_TILES
    assert not tiles & set(ft.BIGRAM_TILE_MAP.values())
    assert max(tiles) < 1435, "cave must stay below the _VD_SPACE bigram range"


def test_built_d00_has_no_bigram_tiles():
    """The shipped D00 must carry ZERO bigram-only tiles in any entry."""
    from iso_tools import build_file_index, extract_file_data
    from d00_tools import parse_d00
    import font_tools as ft

    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    d00 = next((extract_file_data(img, e.extent, e.size)
                for p, e in idx.items() if p.upper().endswith("SCEN/D00.DAT")), None)
    assert d00 is not None

    from d00_tools import is_hankaku_entry
    bigram_only = set(ft.BIGRAM_TILE_MAP.values()) - set(ft.CHAR_TILE_MAP.values())
    offenders = []
    for sec in parse_d00(d00):
        if not is_hankaku_entry(sec.index + 1, ""):
            continue          # documented exception (scen124 stays bigram)
        for ei, entry in enumerate(sec.entries):
            for k in range(0, len(entry) - 1, 2):
                c = struct.unpack_from(">H", entry, k)[0]
                if c in bigram_only:
                    offenders.append((sec.index + 1, ei, hex(c)))
                    break
    assert not offenders, (
        f"{len(offenders)} entries still bigram-encoded, e.g. {offenders[:5]}")
