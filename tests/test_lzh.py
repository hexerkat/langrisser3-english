"""Tests for the stdlib LZH reader the launcher uses for the disc gallery.

Red state (2026-10-12): tools/lzh.py does not exist.

Truth is the real archive on the JP disc (LANG/OMAKE/GRAPHIC.LZH, 16 JPGs,
-lh5- and -lh0- members): every member must come out with the CRC-16 its
own header declares, and TIALISU.JPG must be byte-identical to what 7-Zip
extracts (SHA-256 pinned below).
"""
import hashlib
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import lzh  # noqa: E402

JP_DIR = os.environ.get("LANG3_JP_DIR")
TIALISU_SHA256 = "1cb3d55d62eb1532a0fd1c2e8a012ec8af652c757289e26158b177cd5d41c79e"


@pytest.fixture(scope="module")
def gallery():
    if not JP_DIR:
        pytest.skip("LANG3_JP_DIR not set")
    from iso_tools import _find_jp_track, build_file_index, extract_file_data
    img = bytearray(_find_jp_track(Path(JP_DIR), 1).read_bytes())
    e = build_file_index(img)["LANG/OMAKE/GRAPHIC.LZH"]
    return extract_file_data(img, e.extent, e.size)


def test_lists_all_sixteen_members(gallery):
    members = lzh.list_members(gallery)
    assert len(members) == 16
    assert {m.method for m in members} == {"-lh0-", "-lh5-"}
    assert "TIALISU.JPG" in [m.name for m in members]


def test_every_member_matches_its_header_crc(gallery):
    for m in lzh.list_members(gallery):
        data = lzh.extract(gallery, m.name)
        assert len(data) == m.size, m.name
        assert lzh.crc16(data) == m.crc, m.name


def test_tiaris_matches_7zip(gallery):
    data = lzh.extract(gallery, "TIALISU.JPG")
    assert hashlib.sha256(data).hexdigest() == TIALISU_SHA256


def test_missing_member_raises_keyerror(gallery):
    with pytest.raises(KeyError):
        lzh.extract(gallery, "NOPE.JPG")


def test_corrupt_member_raises_valueerror(gallery):
    first = lzh.list_members(gallery)[0]
    bad = bytearray(gallery)
    bad[first.data_offset + 100] ^= 0xFF
    with pytest.raises(ValueError):
        lzh.extract(bytes(bad), first.name)


def test_crc16_is_lha_arc_variant():
    # CRC-16/ARC check value for "123456789".
    assert lzh.crc16(b"123456789") == 0xBB3D
