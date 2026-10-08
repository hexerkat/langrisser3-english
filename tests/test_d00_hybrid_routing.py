"""test_d00_hybrid_routing.py — every D00 entry ships hybrid-encoded.

Red state (2026-10-08): the build routes every entry through the per-glyph
hankaku encoder, so the shipped D00 carries no bigram tiles at all and no
entry matches encode_hybrid().

End state (Ralf 2026-10-08): the v0.7 bigram encoder that only now and then
renders 8px. Real text pairs (spaces included) stay bigrams; the 8px band
covers only the char v0.7 padded with a phantom blank. Checked on the built
track01, not on a re-encode.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))


def _built_d00():
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    d00 = next((extract_file_data(img, e.extent, e.size)
                for p, e in idx.items() if p.upper().endswith("SCEN/D00.DAT")), None)
    assert d00 is not None
    return d00


def test_built_d00_entries_are_hybrid():
    from d00_tools import parse_d00, parse_script_file
    from hybrid_encoder import encode_hybrid
    import font_tools as ft

    sections = parse_d00(_built_d00())
    mismatches, checked = [], 0
    for sec in sections:
        script = PROJECT / "scripts" / "en" / f"scen{sec.index + 1:03d}E.txt"
        if not script.exists():
            continue
        for ei, text in enumerate(parse_script_file(script)):
            want = encode_hybrid(text, ft.BIGRAM_TILE_MAP)
            if not sec.entries[ei].startswith(want):
                mismatches.append((sec.index + 1, ei))
            checked += 1
    assert checked > 10000
    assert not mismatches, (
        f"{len(mismatches)} entries are not hybrid, e.g. {mismatches[:5]}")



def test_built_d00_is_mostly_bigrams():
    """Bigram encoder first: band tiles are the exception, not the rule."""
    from d00_tools import parse_d00
    import font_tools as ft

    band = set(ft.HANKAKU_TILE_MAP.values())
    bigrams = set(ft.BIGRAM_TILE_MAP.values()) - set(ft.CHAR_TILE_MAP.values())
    n_band = n_pair = 0
    for sec in parse_d00(_built_d00()):
        for entry in sec.entries:
            for (w,) in struct.iter_unpack(">H", entry[:len(entry) & ~1]):
                n_band += w in band
                n_pair += w in bigrams
    assert n_pair > 4 * n_band, f"pairs {n_pair} vs 8px tiles {n_band}"
