"""test_prog3_balloon_zenkaku_dispatch.py — mixed 8/16px steps (TDD guard).

v0.8 width classes (branch font-hankaku-per-glyph). The balloon dispatcher
FUN_0607d168 calls the layout fn FUN_0607cf80 through the pool pointer at
0x0607D220 (the ONLY 0x0607CF80 reference in any game binary). Repointing that
ONE literal to a cave stored in free FONT.BIN tiles (LWRAM, always resident
with the font) gives per-glyph width classes:

  hankaku band tile  -> tail-jump to the real cf80 (1 column, 8px)
  any other tile     -> drawn as TWO adjacent 8px cells (left half + a
                        right-half scratch glyph shifted <<8) and the row
                        cursor advances 2 columns = 16px

This is what renders zenkaku (kanji, the 16px ellipsis 906, full-width space,
bigram tiles) INSIDE hankaku prose — and it restores v0.7 rendering for all
not-yet-converted bigram content (dialogue, nameplates, menus), turning the
hankaku conversion incremental.

Red state: before the cave + repoint exist, the pool still holds 0x0607CF80,
every tile steps 8px, and 16px content draws garbled left-half-only.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

POOL_OFFSET = 0x2AA20            # file offset of the cf80 pointer (0x0607D220)
JP_POOL_VALUE = 0x0607CF80


def test_jp_baseline_pool_points_at_cf80():
    jp = (PROJECT / "data/jp/prog/prog_3.bin").read_bytes()
    assert struct.unpack_from(">I", jp, POOL_OFFSET)[0] == JP_POOL_VALUE


def test_module_repoints_the_dispatcher():
    from prog3_balloon_zenkaku_dispatch import (
        PROG3_BALLOON_ZENKAKU_DISPATCH, JP_BASELINE)
    from balloon_zenkaku_cave import CAVE_ADDR
    patches = dict(PROG3_BALLOON_ZENKAKU_DISPATCH["LANG/PROG_3.BIN"])
    assert patches[POOL_OFFSET] == CAVE_ADDR.to_bytes(4, "big")
    assert JP_BASELINE[POOL_OFFSET] == JP_POOL_VALUE.to_bytes(4, "big")


def test_cave_geometry_is_consistent():
    """Cave + scratch tiles: inside the loaded font, outside every other tile
    consumer (hankaku band, bigram layout, preserved tiles)."""
    import balloon_zenkaku_cave as cave
    import font_tools as ft
    assert cave.CAVE_ADDR == cave.FONT_LWRAM_BASE + cave.CAVE_TILE * 32
    tiles = set(range(cave.CAVE_TILE, cave.CAVE_TILE + cave.CAVE_TILES))
    tiles.add(cave.SCRATCH_TILE)
    assert max(tiles) < ft.NEW_FONT_TILES, "cave outside the loaded font"
    assert not tiles & set(ft.HANKAKU_TILE_MAP.values())
    assert not tiles & set(ft.BIGRAM_TILE_MAP.values())
    assert not tiles & ft.PRESERVED_TILES
    # v0.8 reserved range vs the packer: FRESH allocations are forbidden here
    # (regression: a corpus shift spilled 'Yo'->1426 and '• '->1265, silently
    # overwritten by our band/cave writes). PRESERVED-tile reuse (1426 'Yo')
    # is legitimate — the legacy glyph pre-exists — but then NONE of OUR
    # written tiles may sit on a reused slot.
    bigram_tiles = set(ft.BIGRAM_TILE_MAP.values())
    spill = ft.V08_RESERVED_TILES & bigram_tiles - ft.PRESERVED_TILES
    assert not spill, f"packer FRESH-allocated inside the v0.8 range: {spill}"
    ours = (set(ft.HANKAKU_TILE_MAP.values()) | tiles
            | {ft.NAKAGURO_TILE, cave.SCRATCH_TILE})
    assert not ours & bigram_tiles, f"our tiles collide with bigrams: {ours & bigram_tiles}"
    assert set(ft.HANKAKU_TILE_MAP.values()) <= ft.V08_RESERVED_TILES
    assert ft.NAKAGURO_TILE in ft.V08_RESERVED_TILES
    # the class bounds baked into the cave must match the actual band
    band = ft.HANKAKU_TILES
    assert cave.HANKAKU_LO == min(band) == ft.HANKAKU_BASE
    assert cave.HANKAKU_HI >= max(band)
    assert cave.HANKAKU_HI < cave.SCRATCH_TILE


def test_generated_font_carries_the_cave():
    """The cave blob is embedded in the generated FONT.BIN at CAVE_TILE; the
    scratch tile stays zero in the file (runtime-only)."""
    import balloon_zenkaku_cave as cave
    import font_tools as ft
    jp = (PROJECT / "data/jp/font_jp.bin").read_bytes()
    font = ft.generate_english_font(jp)
    blob = cave.cave_blob()
    off = cave.CAVE_TILE * 32
    assert font[off:off + len(blob)] == blob
    s = cave.SCRATCH_TILE * 32
    assert font[s:s + 32] == b"\x00" * 32


def test_hankaku_encoder_emits_the_16px_ellipsis():
    """With zenkaku dispatch, '…' is the 16px ellipsis tile 906 (v0.7 look),
    NOT the 8px band stand-in."""
    from hankaku_encoder import encode_hankaku
    import font_tools as ft
    want = struct.pack(">H", ft.ELLIPSIS_TILE)
    assert encode_hankaku("…") == want
    assert encode_hankaku("...") == want


def test_built_track01_carries_cave_and_repoint():
    from iso_tools import build_file_index, extract_file_data
    import balloon_zenkaku_cave as cave
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)

    def grab(suffix):
        return next((extract_file_data(img, e.extent, e.size)
                     for p, e in idx.items() if p.upper().endswith(suffix)), None)

    prog3 = grab("PROG_3.BIN")
    assert prog3 is not None
    assert struct.unpack_from(">I", prog3, POOL_OFFSET)[0] == cave.CAVE_ADDR

    font = grab("FONT.BIN")
    assert font is not None
    blob = cave.cave_blob()
    off = cave.CAVE_TILE * 32
    assert font[off:off + len(blob)] == blob
