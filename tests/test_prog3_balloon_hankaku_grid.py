"""test_prog3_balloon_hankaku_grid.py — 34-col hankaku balloon grid (TDD guard).

v0.8 Piece B (branch font-hankaku-per-glyph). Full RE reference:
archive/docs/20260707_prog3_dialogue_balloon_pipeline_re.md.

The PROG_3 VDP1 balloon renderer draws a per-window grid of 17 cols x 5 rows
(win stride 0x55, row stride 0x11) with one 16x16 4bpp texture per cell (0x80 B,
VDP1 VRAM 0x25C60000 + win*0x2A80). With the 8px step NOP (the v0.8 spike) each
column is 8px, so 17 cols only fill half the balloon. This module re-dimensions
the grid to 34 cols (narration) / 26 (dialogue) = the SAME line budgets as the
v0.7 bigram encoding (17/13 tiles x 2 chars), so existing <$FFFC> breaks fit.

Three coordinated changes, all in-place over the JP LANG/PROG_3.BIN:
 1. Grid geometry: col bounds 0x10->0x21, row strides 0x11->0x22, d168 line
    limits 17->34 / 13->26.
 2. Window stride 0x55->0x100 via `mov rWIN,rD; shll8 rD` replacing each
    `mov #0x55; mul.l; sts macl` (mov #imm8 sign-extends, so >=0x80 is not
    loadable; shll8 sidesteps it). 7 sites across ccac/fnA/cf3c/cf80/flush.
 3. 8px-wide textures (0x40 B/cell): rasterizer emits 4 B/row, staging/blit/
    CMDSRCA cell steps drop x0x80->x0x40, CMDSIZE 0x210->0x110. Texture need =
    0xAA cells x 0x40 = 0x2A80 = EXACTLY the JP per-window VRAM stride, so the
    VDP1 VRAM footprint is unchanged (0x65500+ is occupied; growth would clash).

The 4 per-cell grid buffers (slot/X/Y/flag, 1 B/cell) grow from 0xB0 to 0x200
(2 windows x 0x100) and are relocated to the PROG_3 BSS tail in HWRAM,
0x06088800..0x06089000 (right below PROG_4; zero in the jp/0.7/ours BUSY
scen005 dumps; no code literal in any game binary points into it). The 11
pool literals referencing them are repointed; the row cursor, scalars and the
0x20-byte VDP1 command template do not scale and stay in place.

    2026-07-08 CORRECTION (Citizen-portrait bug): the first LWRAM home
    (0x002A6000, "free block 0x002A57C8+0x2483B") was chosen from a QUIET
    dialogue-state dump. The busy scen005 dumps show the JP engine fills
    0x2A57C8-0x2AFA43 with battle data — the buffers sat inside a live
    engine arena and mutually corrupted it. Same-family lesson: a region is
    free only if it is free in a BUSY state.

STAGING DISCIPLINE (the Citizen-portrait fix). The rasterizer stages each
glyph at *0x0604F8A0 (= 0x0600A000, the HWRAM ring below A0LANG) + slot*0x40,
where slot is the monotonic counter 0x060885F8, and the on-chip DMAC copy
consumes the slot into VDP1 immediately (the copy entry polls CHCR until the
previous transfer is done). The ring is SHARED: the engine parks portrait
blink/animation frame sources at ring+0xA68/+0x2100/+0x2520 (PROG_3
FUN_06079198 reads the same pointer), so our full-hankaku conversion — many
more cf80 calls per burst than bigram — pushed glyph residue over the frames
(scen005 barcode + dead blink). Fix: mask the staging offset to 4 rotating
transient slots, (slot<<6)&0xFF, footprint 0x0600A000..0x0600A100 — inside
the slice JP's own staging uses (JP reach: slot<<7, observed < +0xA68) and
far below every frame. 2 in-place words in cf80; safe for ANY scene size by
construction. VDP1 cell addresses are computed from the grid cell index, not
from this counter, so texture allocation is untouched.

Red state (2026-07-08): the module still relocates the buffers to LWRAM
0x002A6000 (inside the battle arena) and leaves the staging offset unmasked
(nop at 0x0607CFE0, reach 0xAA*0x40 = 0x2A80 — covers the portrait frames).
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

LOAD_BASE = 0x06052800

# (file_offset, jp_word, new_word) — SH-2 big-endian opcode words / u16 data.
CODE_SITES = [
    # --- col-clear loop bounds: mov #0x10 -> mov #0x21 (<=33 -> 34 cols) ---
    (0x0607CCD2 - LOAD_BASE, b"\xEB\x10", b"\xEB\x21"),  # ccac (clear-all)
    (0x0607CE36 - LOAD_BASE, b"\xEA\x10", b"\xEA\x21"),  # fnA FFFC path
    (0x0607CED8 - LOAD_BASE, b"\xEA\x10", b"\xEA\x21"),  # fnA normal-char path
    (0x0607CF46 - LOAD_BASE, b"\xE9\x10", b"\xE9\x21"),  # cf3c (scroll)
    (0x0607D292 - LOAD_BASE, b"\xEB\x10", b"\xEB\x21"),  # flush row-clear
    # --- row stride 0x11 -> 0x22 ---
    (0x0607CCE0 - LOAD_BASE, b"\xE4\x11", b"\xE4\x22"),  # ccac
    (0x0607CE3C - LOAD_BASE, b"\xE5\x11", b"\xE5\x22"),  # fnA FFFC path
    (0x0607CEDE - LOAD_BASE, b"\xE4\x11", b"\xE4\x22"),  # fnA normal-char path
    (0x0607CF70 - LOAD_BASE, b"\x73\x11", b"\x73\x22"),  # cf3c (add #0x11,r3)
    (0x0607CFB8 - LOAD_BASE, b"\xE1\x11", b"\xE1\x22"),  # cf80 (layout)
    (0x0607D298 - LOAD_BASE, b"\xE8\x11", b"\xE8\x22"),  # flush row-clear
    (0x0607D44E - LOAD_BASE, b"\x7A\x11", b"\x7A\x22"),  # flush draw (add #0x11,r10)
    # --- d168 per-line char limits ---
    (0x0607D192 - LOAD_BASE, b"\xE3\x11", b"\xE3\x22"),  # narration 17 -> 34
    (0x0607D1A0 - LOAD_BASE, b"\xE3\x0D", b"\xE3\x1A"),  # dialogue 13 -> 26
    # --- window stride 0x55 -> 0x100: mul-by-imm -> win<<8 ---
    (0x0607CCE4 - LOAD_BASE, b"\x05\xA7", b"\x61\x53"),  # ccac mul.l r10,r5 -> mov r5,r1
    (0x0607CCE8 - LOAD_BASE, b"\x01\x1A", b"\x41\x18"),  # ccac sts macl,r1 -> shll8 r1
    (0x0607CE60 - LOAD_BASE, b"\x04\x97", b"\x61\x43"),  # fnA-FFFC mul.l r9,r4 -> mov r4,r1
    (0x0607CE64 - LOAD_BASE, b"\x01\x1A", b"\x41\x18"),  # fnA-FFFC sts -> shll8 r1
    (0x0607CEE2 - LOAD_BASE, b"\x03\x97", b"\x61\x33"),  # fnA-char mul.l r9,r3 -> mov r3,r1
    (0x0607CEE6 - LOAD_BASE, b"\x01\x1A", b"\x41\x18"),  # fnA-char sts -> shll8 r1
    # cf3c is SPECIAL: its inner loop re-enters BETWEEN the mul/sts pair
    # (bf/s -> 0x0607CF54), so the pair CANNOT be replaced like the others —
    # a per-iteration shll8 corrupted the address after column 0 (the
    # "only the first column scrolls" playtest bug, 2026-07-07 evening).
    # Instead: win<<8 is precomputed ONCE in r4 (the dead #0x55 load's slot)
    # and r1 is re-initialized fresh each inner iteration.
    (0x0607CF4A - LOAD_BASE, b"\xE8\x55", b"\x44\x18"),  # cf3c dead mov #0x55,r8 -> shll8 r4 (win<<8, pre-loop)
    (0x0607CF52 - LOAD_BASE, b"\x04\x87", b"\x00\x09"),  # cf3c mul.l r8,r4 -> nop
    (0x0607CF56 - LOAD_BASE, b"\x01\x1A", b"\x61\x43"),  # cf3c sts macl,r1 -> mov r4,r1 (per-iteration re-init)
    (0x0607CFAC - LOAD_BASE, b"\xE1\x55", b"\x6B\xA3"),  # cf80 mov #0x55,r1 -> mov r10,r11
    (0x0607CFAE - LOAD_BASE, b"\x0A\x17", b"\x4B\x18"),  # cf80 mul.l r1,r10 -> shll8 r11
    (0x0607CFB0 - LOAD_BASE, b"\x0B\x1A", b"\x00\x09"),  # cf80 sts macl,r11 -> nop
    (0x0607D2AC - LOAD_BASE, b"\x03\xA7", b"\x61\x33"),  # flush-clear mul.l r10,r3 -> mov r3,r1
    (0x0607D2B0 - LOAD_BASE, b"\x01\x1A", b"\x41\x18"),  # flush-clear sts -> shll8 r1
    (0x0607D3A2 - LOAD_BASE, b"\x0C\x17", b"\x67\xC3"),  # flush-draw mul.l r1,r12 -> mov r12,r7
    (0x0607D3A4 - LOAD_BASE, b"\x07\x1A", b"\x47\x18"),  # flush-draw sts macl,r7 -> shll8 r7
    # --- 8px-wide textures: cell step x0x80 -> x0x40 (drop one doubling) ---
    # staging offset = (slot<<6)&0xFF: shll2/shll2/shll2/extu.b over the JP
    # shll2/shll2/add/shll2 — 4 rotating 0x40 B slots at ring+0..0x100, so the
    # staging can never reach the portrait frames at ring+0xA68 and beyond.
    (0x0607CFE0 - LOAD_BASE, b"\x31\x1C", b"\x41\x08"),  # cf80 staging: add r1,r1 -> shll2 r1 (slot<<6)
    (0x0607CFE2 - LOAD_BASE, b"\x41\x08", b"\x61\x1C"),  # cf80 staging: shll2 r1 -> extu.b r1,r1 (&0xFF)
    (0x0607D000 - LOAD_BASE, b"\x32\x2C", b"\x00\x09"),  # cf80 blit dest cell<<7 -> <<6
    (0x0607D012 - LOAD_BASE, b"\x42\x01", b"\x00\x09"),  # cf80 slot-byte recover >>7 -> >>6
    (0x0607D084 - LOAD_BASE, b"\x00\x80", b"\x00\x40"),  # cf80 glyph copy length (u16 pool)
    (0x0607D128 - LOAD_BASE, b"\x76\x02", b"\x76\x04"),  # rasterizer: 4 output B/row (left 8px)
    (0x0607D3F8 - LOAD_BASE, b"\x31\x1C", b"\x00\x09"),  # flush CMDSRCA slot<<7 -> <<6
    (0x0607D492 - LOAD_BASE, b"\x02\x10", b"\x01\x10"),  # CMDSIZE 16x16 -> 8x16 (u16 pool)
]

# (file_offset, jp_u32, new_u32) — the 11 pool literals of the 4 per-cell buffers.
HWRAM_SLOT, HWRAM_X, HWRAM_Y, HWRAM_FLAG = (
    0x06088800, 0x06088A00, 0x06088C00, 0x06088E00)
POOL_LITERALS = [
    (0x0607D09C - LOAD_BASE, 0x06088308, HWRAM_SLOT),   # slot @cf80
    (0x0607D4CC - LOAD_BASE, 0x06088308, HWRAM_SLOT),   # slot @flush
    (0x0607D0A0 - LOAD_BASE, 0x060883B8, HWRAM_X),      # X @cf80
    (0x0607D4D0 - LOAD_BASE, 0x060883B8, HWRAM_X),      # X @flush
    (0x0607CF7C - LOAD_BASE, 0x06088468, HWRAM_Y),      # Y @cf3c (scroll)
    (0x0607D0A8 - LOAD_BASE, 0x06088468, HWRAM_Y),      # Y @cf80
    (0x0607D4D8 - LOAD_BASE, 0x06088468, HWRAM_Y),      # Y @flush
    (0x0607CD40 - LOAD_BASE, 0x06088528, HWRAM_FLAG),   # flag @ccac
    (0x0607CF38 - LOAD_BASE, 0x06088528, HWRAM_FLAG),   # flag @fnA
    (0x0607D088 - LOAD_BASE, 0x06088528, HWRAM_FLAG),   # flag @cf80
    (0x0607D4A4 - LOAD_BASE, 0x06088528, HWRAM_FLAG),   # flag @flush
]


def _expected_patches():
    out = list(CODE_SITES)
    for off, jp, new in POOL_LITERALS:
        out.append((off, jp.to_bytes(4, "big"), new.to_bytes(4, "big")))
    return out


def test_jp_baselines_match_pristine_prog3():
    """Every patch site's JP baseline must match the pristine JP PROG_3."""
    jp = (PROJECT / "data/jp/prog/prog_3.bin").read_bytes()
    for off, jpb, _ in _expected_patches():
        assert jp[off:off + len(jpb)] == jpb, (
            f"JP baseline mismatch at file 0x{off:05X}: "
            f"got {jp[off:off + len(jpb)].hex()} want {jpb.hex()}")


def test_module_declares_every_site():
    from prog3_balloon_hankaku_grid import (
        PROG3_BALLOON_HANKAKU_GRID, JP_BASELINE)
    patches = dict(PROG3_BALLOON_HANKAKU_GRID["LANG/PROG_3.BIN"])
    expected = _expected_patches()
    assert len(patches) == len(expected)
    for off, jpb, newb in expected:
        assert patches.get(off) == newb, f"missing/wrong patch at 0x{off:05X}"
        assert JP_BASELINE[off] == jpb, f"missing/wrong baseline at 0x{off:05X}"


def test_grid_buffers_live_in_the_prog3_bss_tail_and_are_disjoint():
    """The 4 relocated buffers (0x200 each = 2 windows x 0x100 stride) must sit
    in the PROG_3 BSS tail [0x06088800, 0x06089000): after the PROG_3 file
    image (ends 0x0608827C) and the JP-retained grid structures (cmd template
    0x060882E8 .. scalars 0x060885F8+4), before the PROG_4 load base.

    Red state (2026-07-08): buffers at LWRAM 0x002A6000 — inside the battle
    arena the JP engine fills in busy scenes (seen live-corrupted in the
    scen005 dumps)."""
    bss_lo, bss_hi = 0x06088800, 0x06089000   # free run below PROG_4
    bases = [HWRAM_SLOT, HWRAM_X, HWRAM_Y, HWRAM_FLAG]
    for b in bases:
        assert bss_lo <= b and b + 0x200 <= bss_hi, (
            f"buffer 0x{b:08X} outside the PROG_3 BSS tail")
    spans = sorted((b, b + 0x200) for b in bases)
    for (lo1, hi1), (lo2, hi2) in zip(spans, spans[1:]):
        assert hi1 <= lo2, "relocated buffers overlap"


def test_no_buffer_lives_in_the_lwram_battle_arena():
    """No relocated buffer may sit in LWRAM [0x295360, 0x2CA000): the region
    between the end of FONT.BIN's tiles and the next fixed load destination
    behaves as a growing engine arena in battle (busy scen005 dumps: JP fills
    0x2A57C8-0x2AFA43 over the old 0x2A6000 homes).

    Red state (2026-07-08): all 4 buffers at 0x2A6000-0x2A6800."""
    arena_lo, arena_hi = 0x00295360, 0x002CA000
    for b in (HWRAM_SLOT, HWRAM_X, HWRAM_Y, HWRAM_FLAG):
        assert not (arena_lo <= b < arena_hi), (
            f"buffer 0x{b:08X} sits in the LWRAM battle arena")


def test_staging_footprint_cannot_reach_the_portrait_frames():
    """Model the patched cf80 staging-offset math (the effective behavior the
    player sees, per the の→0xD4 lesson): offset = (slot<<6) & 0xFF for every
    possible counter value. The reach must stay below ring+0xA68, the lowest
    portrait blink-frame source (jp/0.7 dumps; frames also at +0x2100/+0x2520).

    Red state (2026-07-08): unmasked slot<<6 — 0xAA cells per balloon reach
    ring+0x2A80 and overwrite the frames (scen005 Citizen barcode/dead blink)."""
    frame_lo = 0xA68
    reach = max(((slot << 6) & 0xFF) + 0x40 for slot in range(0x10000))
    assert reach == 0x100
    assert reach <= frame_lo
    # and the module must actually carry the two masking words
    from prog3_balloon_hankaku_grid import PROG3_BALLOON_HANKAKU_GRID
    patches = dict(PROG3_BALLOON_HANKAKU_GRID["LANG/PROG_3.BIN"])
    assert patches.get(0x0607CFE0 - LOAD_BASE) == b"\x41\x08", (
        "staging mask word 1 (shll2 r1) missing")
    assert patches.get(0x0607CFE2 - LOAD_BASE) == b"\x61\x1C", (
        "staging mask word 2 (extu.b r1,r1) missing")


def test_geometry_is_consistent():
    """34 cols x 5 rows must fit the 0x100 window stride, the byte-wide slot
    index, and the unchanged 0x2A80 VDP1 VRAM window (0x40 B/cell)."""
    cols, rows, row_stride, win_stride, cell_bytes = 34, 5, 0x22, 0x100, 0x40
    assert row_stride >= cols
    assert win_stride >= rows * row_stride
    max_cell = (rows - 1) * row_stride + (cols - 1)
    assert max_cell <= 0xFF                      # slot buffer stores a byte
    assert (max_cell + 1) * cell_bytes <= 0x2A80  # per-window VRAM stride kept


def test_built_prog3_carries_the_grid():
    """If a build exists, the built PROG_3 must carry every patched word."""
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    prog3 = next((extract_file_data(img, e.extent, e.size)
                  for p, e in idx.items() if p.upper().endswith("PROG_3.BIN")), None)
    assert prog3 is not None
    for off, _, newb in _expected_patches():
        assert prog3[off:off + len(newb)] == newb, (
            f"built PROG_3 missing patch at 0x{off:05X}")
