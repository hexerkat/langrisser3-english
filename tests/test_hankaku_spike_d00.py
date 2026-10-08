"""test_hankaku_spike_d00.py — the routed Youth line is hankaku in the built D00.

v0.8 spike (branch font-hankaku-per-glyph): d00_tools routes scen001 entry 18 (the
opening Lushiris "…Youth aspiring…" line) through the per-glyph hankaku encoder.
This build-gated guard confirms that entry's codes in the SHIPPED D00.DAT are all
hankaku-band tiles (font_tools.HANKAKU_TILE_MAP) + structural control codes — i.e.
NO bigram tiles. Pairs with the renderer NOP (prog3_dialogue_hankaku_step): together
they render that line per-glyph 8px in-game.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

SCEN001_SECTION = 0
YOUTH_ENTRY = 18
STRUCTURAL = {0xFFFC, 0xFFFD, 0xFFFE, 0xFFFF, 0xF600, 0x0000}


def test_built_d00_youth_line_is_hankaku():
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
    assert d00 is not None, "D00.DAT not found in build"

    sections = parse_d00(d00)
    entry = sections[SCEN001_SECTION].entries[YOUTH_ENTRY]
    codes = [struct.unpack_from(">H", entry, k)[0] for k in range(0, len(entry) - 1, 2)]

    band = set(ft.HANKAKU_TILE_MAP.values())
    offenders = [c for c in codes if c not in band and c not in STRUCTURAL]
    assert not offenders, (
        f"Youth line has non-hankaku, non-structural codes (bigrams?): "
        f"{[hex(c) for c in offenders]}")
    # sanity: it really did encode letters as hankaku (not an empty/JP entry)
    assert sum(c in band for c in codes) > 20, "too few hankaku tiles — routing failed?"
