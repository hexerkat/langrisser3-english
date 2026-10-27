"""test_prog5_terrain_hud_ascii.py: the terrain HUD shows the whole EN name.

PROG_5 FUN_06089094 (base 0x06089000) draws the small terrain HUD (terrain
under the cursor + its bonus). JP builds a FIXED 4-glyph string, name tile 0,
name tile 1, tens digit, ones digit, rasterizes it and queues four VDP1 sprites
(two 16x16, two 12x16). JP names are always 2 kanji; EN names are 2 to 9
tiles, so only the first two ever reached the screen ("Wasteland" -> "Wast").

Red state (2026-10-23): the built PROG_5 still runs the JP routine, which
queues 4 sprites, none of them from the ASCII bank.
End state: one 8x8 sprite per character from the small ASCII font (VDP1 VRAM
0x10000 + code * 32, the PRESS START / "Treatment" font), name, one space,
bonus, right-aligned so the last digit ends at x 300 like the JP one.

The REAL built bytes run on tools/sh2_mini with the REAL PROG_3 bonus tables;
the sprite queue (A0LANG 0x0602E034) is intercepted and records each command.
"""
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from sh2_mini import Sh2  # noqa: E402

PROG5_BASE = 0x06089000
PROG3_BASE = 0x06052800
HUD_ENTRY = 0x06089094
ENQUEUE = 0x0602E034        # A0LANG sprite queue (DMA of a 36-byte command)
RASTERIZE = 0x0607D0B8      # PROG_3 1bpp->4bpp glyph rasterizer (JP path)
VRAM_COPY = 0x0600F98C      # A0LANG copy to VDP1 VRAM (JP path)
FLAG_ON = 0x0604E6F7        # must be non-zero for the HUD to draw
FLAG_OFF = 0x060370D7       # must be zero for the HUD to draw
CLASS_TAB = 0x06085D78      # PROG_3: u8 class per param_2 (30 entries)
BONUS_TAB = 0x06085D96      # PROG_3: u8 bonus[class][28 terrains]
TERRAINS = 28
FNTSYS1_TERRAIN = 199       # fntsys1 record of terrain 0 (Plains)

ASCII_SRCA = 0x2000         # VDP1 char address /8 of glyph 0x00 (0x10000)
SPRITE_8X8 = 0x0108
ASCII_COLR = 0x00B0
RIGHT_EDGE = 300            # JP ones digit spans x 288..299
HUD_Y = 204                 # 8px row centred on the JP 16px row (y 200..215)


def _track(path):
    from iso_tools import build_file_index, extract_file_data
    img = path.read_bytes()
    idx = build_file_index(img)
    return {name: extract_file_data(img, idx[name].extent, idx[name].size)
            for name in ("LANG/PROG_5.BIN", "LANG/PROG_3.BIN")}


@pytest.fixture(scope="module")
def built():
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    return _track(max(builds, key=lambda p: p.stat().st_mtime))


@pytest.fixture(scope="module")
def jp():
    jp_dir = os.environ.get("LANG3_JP_DIR")
    if not jp_dir:
        pytest.skip("LANG3_JP_DIR not set")
    return _track(sorted(Path(jp_dir).glob("*rack*01*.bin"))[0])


class _Hud(Sh2):
    """Sh2 with the three external calls of the HUD intercepted."""

    def __init__(self, regions):
        super().__init__(regions)
        self.sprites = []

    def _step(self, pc):
        if pc == ENQUEUE:
            raw = bytes(self.rb(self.R[4] + i) for i in range(0x24))
            self.sprites.append({k: int.from_bytes(raw[o:o + 2], "big")
                                 for k, o in (("ctrl", 0), ("pmod", 4),
                                              ("colr", 6), ("srca", 8),
                                              ("size", 0xA), ("x", 0xC),
                                              ("y", 0xE))})
            self.R[0] = 1
            return self.PR
        if pc in (RASTERIZE, VRAM_COPY):
            return self.PR
        return super()._step(pc)


def _run(tracks, terrain, param2):
    prog3 = tracks["LANG/PROG_3.BIN"]
    cpu = _Hud({PROG5_BASE: tracks["LANG/PROG_5.BIN"], PROG3_BASE: prog3,
                0x06030000: bytes(0x22800)})
    cpu.wb(FLAG_ON, 1)
    cpu.wb(FLAG_OFF, 0)
    # JP path only: fntsys1 offset table / data pointers -> a zeroed area.
    for holder in (0x0603A478, 0x0604E9F0):
        cpu.wl(holder, 0x06040000)
    cpu.wl(0x0604F8A0, 0x06044000)
    cpu.call(HUD_ENTRY, {4: terrain, 5: param2})
    return cpu


def _names():
    from fnt_sys_tools import _parse_script_records
    recs = _parse_script_records(PROJECT / "scripts/en/fntsys1E.txt")
    return [r.replace("<$FFFF>", "")
            for r in recs[FNTSYS1_TERRAIN:FNTSYS1_TERRAIN + TERRAINS]]


def _bonus(prog3, terrain, param2):
    cls = prog3[CLASS_TAB - PROG3_BASE + param2]
    return prog3[BONUS_TAB - PROG3_BASE + cls * TERRAINS + terrain]


def _expected(text):
    """(x, char) of every drawn glyph: right-aligned, spaces take a cell."""
    n = len(text)
    return [(RIGHT_EDGE - 8 * (n - i), c) for i, c in enumerate(text)
            if c != " "]


def _drawn(sprites):
    out = []
    for s in sprites:
        is_ascii = (s["size"] == SPRITE_8X8 and s["colr"] == ASCII_COLR
                    and s["ctrl"] == 0 and s["srca"] >= ASCII_SRCA
                    and (s["srca"] - ASCII_SRCA) % 4 == 0)
        ch = chr((s["srca"] - ASCII_SRCA) // 4) if is_ascii else "?"
        out.append((s["x"], ch))
    return sorted(out)


def test_terrain_names_fit_the_ascii_font():
    names = _names()
    assert len(names) == TERRAINS
    for name in names:
        assert name and all(0x20 <= ord(c) < 0x7F for c in name), name
        assert not name.startswith(" ") and not name.endswith(" "), name


def test_bonus_values_have_at_most_two_digits(jp):
    prog3 = jp["LANG/PROG_3.BIN"]
    assert max(_bonus(prog3, t, p) for t in range(TERRAINS)
               for p in range(30)) <= 99


def test_hud_draws_whole_name_and_bonus_in_ascii(built):
    """Every terrain, every class: the player reads '<name> <bonus>'."""
    names = _names()
    prog3 = built["LANG/PROG_3.BIN"]
    bad = []
    for param2 in range(30):
        for terrain, name in enumerate(names):
            cpu = _run(built, terrain, param2)
            text = f"{name} {_bonus(prog3, terrain, param2)}"
            got = _drawn(cpu.sprites)
            if got != _expected(text) or any(s["y"] != HUD_Y
                                             for s in cpu.sprites):
                bad.append((terrain, param2, text, got[:6]))
    assert not bad, f"{len(bad)} HUD strings wrong, first: {bad[:3]}"


def test_hud_still_stores_the_terrain_id(built):
    """JP side effect kept: the id goes to 0x06091580 (read elsewhere)."""
    cpu = _run(built, 13, 0)
    assert cpu.rw(0x06091580) == 13


@pytest.mark.parametrize("flag, value", [(FLAG_ON, 0), (FLAG_OFF, 1)])
def test_hud_gates_unchanged(built, flag, value):
    """JP returns 0x2F and draws nothing when either gate flag says so."""
    prog3 = built["LANG/PROG_3.BIN"]
    cpu = _Hud({PROG5_BASE: built["LANG/PROG_5.BIN"], PROG3_BASE: prog3,
                0x06030000: bytes(0x22800)})
    cpu.wb(FLAG_ON, 1)
    cpu.wb(flag, value)
    cpu.call(HUD_ENTRY, {4: 0, 5: 0})
    assert cpu.R[0] == 0x2F and cpu.sprites == []


def test_jp_baseline_is_what_we_patch(jp):
    """Truth-lock: the region we overwrite is the pristine JP routine + pool."""
    import prog5_terrain_hud_ascii as mod
    assert mod.jp_region_sha256(jp["LANG/PROG_5.BIN"]) == mod.JP_BASELINE_SHA256


def test_no_outside_pc_load_reaches_the_region(jp):
    """Only the routine itself reads its pool: no PC-relative load from the
    code before it lands inside (PC loads only reach forward, so code after
    the region cannot)."""
    import prog5_terrain_hud_ascii as mod
    prog5 = jp["LANG/PROG_5.BIN"]
    for at in range(0x38, mod.REGION_OFF, 2):
        w = int.from_bytes(prog5[at:at + 2], "big")
        if w >> 12 == 0xD:
            target = ((at + 4) & ~3) + (w & 0xFF) * 4
        elif w >> 12 == 0x9:
            target = at + 4 + (w & 0xFF) * 2
        else:
            continue
        assert not mod.REGION_OFF <= target < mod.REGION_END, hex(at)
