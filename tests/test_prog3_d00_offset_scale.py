"""test_prog3_d00_offset_scale.py — Piece D v2: scaled D00 entry offsets (x2).

The D00 text-area entry-offset table is u16 (ceiling 65535 B), which forced
scen124 (epilogues, ~73 KB at 1 tile/char) to stay bigram. Piece D reads the
table as `u16 * 2` (ceiling 128 KB) with NO entry padding — entries are u16
word streams, naturally even. (The v1 x4 design padded entries with FFFF and
the choice-list walker rendered each pad as a PHANTOM EMPTY ITEM — Ralf's
playtest: "a segunda linha foi renderizada na última linha". x2 keeps the
entry stream byte-identical; only the table values halve.)

Engine: 3 readers rewritten in place (table disp computed directly in r0
frees the slot for `extu.w + shll`; interleaved pc-rel pool loads keep their
encodings at the shifted position) + the composer branch-B detours through
d00_offset_cave via its repointed pool literal (composer saves pr — jsr-safe).

Red state: v1 x4 bytes in the module / padded entries in the build.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

LOAD_BASE = 0x06052800


def _expected_sites():
    from prog3_d00_offset_scale import JP_BASELINE, PROG3_D00_OFFSET_SCALE
    patches = dict(PROG3_D00_OFFSET_SCALE["LANG/PROG_3.BIN"])
    return patches, JP_BASELINE


def test_jp_baselines_match_pristine_prog3():
    jp = (PROJECT / "data/jp/prog/prog_3.bin").read_bytes()
    patches, baseline = _expected_sites()
    assert set(patches) == set(baseline)
    for off, jpb in baseline.items():
        assert jp[off:off + len(jpb)] == jpb, (
            f"JP mismatch at 0x{off:05X}: got {jp[off:off+len(jpb)].hex()}")


def test_the_four_readers_are_covered():
    patches, _ = _expected_sites()
    offs = {off + LOAD_BASE for off in patches}
    assert 0x0606267E in offs      # S1 primary
    assert 0x060626B2 in offs      # S2 choice-redirect
    assert 0x06062B16 in offs      # S3 second handler
    assert 0x0607F49C in offs      # S4a composer pool -> cave
    assert 0x0607F418 in offs      # S4b composer jsr block
    from d00_offset_cave import D00_CAVE_ADDR
    assert patches[0x0607F49C - LOAD_BASE] == D00_CAVE_ADDR.to_bytes(4, "big")


def test_scaled_build_has_no_padding_phantoms():
    """The entry-data region must be byte-identical raw vs scaled — filler
    between entries becomes phantom empty choice items (the v1 bug)."""
    from d00_tools import build_text_area
    entries = [b"\x04\xf1\x04\xf2\xff\xfe",       # 6 B (odd word count)
               b"\x05\x00" * 3 + b"\xff\xff",
               b"\x04\xf3\xff\xfe"]
    raw = build_text_area(entries)
    scaled = build_text_area(entries, scaled_offsets=True)
    assert len(raw) == len(scaled), "no padding may be added"
    n = len(entries)
    data_start = 6 + 2 * (n + 1) + 10
    assert raw[data_start:] == scaled[data_start:], "entry stream must match"
    # table halves exactly
    for j in range(n):
        r = struct.unpack_from(">H", raw, 6 + j * 2)[0]
        s = struct.unpack_from(">H", scaled, 6 + j * 2)[0]
        assert s == r >> 1 and r % 2 == 0


def test_scaled_lifts_the_ceiling():
    from d00_tools import build_text_area
    entries = [b"\x05\x00" * 399 + b"\xff\xfe" for _ in range(90)]   # ~72 KB
    assert build_text_area(entries) is None, "raw must still cap at 65535"
    area = build_text_area(entries, scaled_offsets=True)
    assert area is not None
    stored_last = struct.unpack_from(">H", area, 6 + 89 * 2)[0]
    assert stored_last <= 0xFFFF and stored_last > 0x8000 // 2


def test_scaled_roundtrip_preserves_entries_exactly():
    from d00_tools import build_text_area, parse_d00
    entries = [b"\x04\xf1\x04\xf2\xff\xfe",
               b"\x05\x00" * 3 + b"\xff\xff",
               b"\x04\xf3\xff\xfe"]
    area = build_text_area(entries, scaled_offsets=True)
    sec = bytearray(2048)
    tb_off = 0x40
    struct.pack_into(">I", sec, 0, tb_off)
    for k in range(17):
        struct.pack_into(">I", sec, tb_off + k * 4, 0x44)
    sec[tb_off + 0x44:tb_off + 0x44 + len(area)] = area
    img = struct.pack(">I", 1) + struct.pack(">II", 1, 2048) + bytes(2036) + bytes(sec)
    got = parse_d00(img)[0].entries
    assert len(got) == len(entries)
    for j, (g, e) in enumerate(zip(got, entries)):
        if j < len(entries) - 1:
            assert g == e, "inter-entry bytes must be identical (no pads)"
        else:
            # the LAST entry may carry the historic area-end 4-align pad
            # (raw format does the same; harmless, after the terminator)
            assert g[:len(e)] == e and set(g[len(e):]) <= {0}


def test_scen124_routes_hankaku():
    from d00_tools import is_hankaku_entry
    assert is_hankaku_entry(124, "epilogue prose")


def test_built_track01_carries_piece_d():
    from iso_tools import build_file_index, extract_file_data
    from d00_tools import parse_d00
    from d00_offset_cave import D00_CAVE_TILE, d00_cave_blob
    import font_tools as ft
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)

    def grab(suffix):
        return next((extract_file_data(img, e.extent, e.size)
                     for p, e in idx.items() if p.upper().endswith(suffix)), None)

    prog3 = grab("PROG_3.BIN")
    patches, _ = _expected_sites()
    for off, newb in patches.items():
        assert prog3[off:off + len(newb)] == newb, f"PROG_3 site 0x{off:05X}"

    font = grab("FONT.BIN")
    blob = d00_cave_blob()
    assert font[D00_CAVE_TILE * 32:D00_CAVE_TILE * 32 + len(blob)] == blob

    # The hybrid encoding (2026-10-08) brought scen124 back under the old u16
    # ceiling; Piece D stays as headroom, so the scaled table must still parse.
    d00 = grab("SCEN/D00.DAT")
    sec124 = parse_d00(d00)[123]
    assert sec124.entries and all(e for e in sec124.entries)
