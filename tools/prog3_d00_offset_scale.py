"""tools/prog3_d00_offset_scale.py — Piece D v2: scaled D00 entry offsets (x2).

Patches over the **JP** `LANG/PROG_3.BIN` (load base 0x06052800) that read the
D00 text-area entry-offset table as `u16 * 2`, lifting the per-section text
ceiling from 64 KB to 128 KB. This lets scen124 (the epilogues, ~73 KB at one
hankaku tile per char) join the full hankaku conversion and retires the last
bigram-encoded scen text.

WHY x2 WITH NO PADDING (v2 — supersedes the x4 design): every entry is a
stream of u16 words, so offsets are NATURALLY even — stored = offset/2 needs
no alignment filler. The x4 build padded entries with FFFF words, and the
choice-list walker ("consecutive FFFF-terminated strings", the PROG_3 menu
family) saw each pad as a PHANTOM EMPTY ITEM — Ralf's playtest bug: the
second choice rendered rows below the first. x2 keeps the entry stream
byte-identical to the unscaled layout; only the table values change.

Stored offsets use ALL 16 bits (<= 0xFFFF -> real <= 0x1FFFE), so the readers
need `extu.w` AND `shll` after the load (`mov.w` sign-extends). Three readers
gain the extra slot IN PLACE by computing the table displacement directly in
r0 (dropping their `mov r1,r0`); the interleaved pc-relative pool loads keep
their encodings (same &~3 base and displacement at the shifted address —
verified). The fourth reader (composer branch B) has no spare slot and
detours through d00_offset_cave (jsr-safe: the composer prologue saves pr at
0x0607F36E), returning r1 = real offset and r2 = text-area base so the
untouched join at 0x0607F426 (`mov r1,r8; add r2,r8`) works as before.

READER INVENTORY (complete: value-exact sweep for the base var 0x0603D570 +
per-user decompile). NON-readers verified: FUN_060779b0 (u32 total_text_size
only — stays REAL), A0LANG 0x06011EF6 (the setter).

DATA SIDE (d00_tools, same registry name so data and engine ship together):
build_text_area(scaled_offsets=True) stores offsets>>1 with NO padding;
parse_d00 auto-detects (a scaled first offset lands inside the offset-table
region — impossible raw). File offset = RAM - 0x06052800.
"""

from d00_offset_cave import D00_CAVE_ADDR

_B = 0x06052800


def _w(*words):
    return b"".join(w.to_bytes(2, "big") for w in words)


# (file_offset, jp_bytes, new_bytes, comment)
_SITES = [
    # S1 — FUN_060625c8 primary fetch, 0x0606267E..0x0606268F (9 words).
    # disp -> r0 directly frees one slot for the shll; the pool load D22B
    # moves 2 bytes earlier with the SAME displacement (verified: both
    # positions share the &~3 base).
    (0x0606267E - _B,
     _w(0x6193, 0x316C, 0x311C, 0x7104, 0x6013, 0x017D, 0xD22B, 0x611D, 0x317C),
     _w(0x6093, 0x306C, 0x300C, 0x7004, 0x017D, 0xD22B, 0x611D, 0x4100, 0x317C),
     "primary entry fetch: disp in r0, extu+shll"),
    # S2 — FUN_060625c8 choice-redirect fetch, 0x060626B2..0x060626C1 (8 words).
    (0x060626B2 - _B,
     _w(0x6193, 0x316C, 0x311C, 0x7104, 0x6013, 0x017D, 0x611D, 0x317C),
     _w(0x6093, 0x306C, 0x300C, 0x7004, 0x017D, 0x611D, 0x4100, 0x317C),
     "choice-redirect fetch: disp in r0, extu+shll"),
    # S3 — second opcode handler, 0x06062B16..0x06062B27 (9 words). The
    # base-index extu retargets to r0 (601D); pool load D216 moves 2 bytes
    # earlier with the same displacement (verified).
    (0x06062B16 - _B,
     _w(0x611D, 0x319C, 0x311C, 0x7104, 0x6013, 0x013D, 0xD216, 0x611D, 0x313C),
     _w(0x601D, 0x309C, 0x300C, 0x7004, 0x013D, 0xD216, 0x611D, 0x4100, 0x313C),
     "2nd handler fetch: disp in r0, extu+shll"),
    # S4a — composer pool 0x0607F49C: &base_var -> the d00_offset_cave.
    (0x0607F49C - _B,
     (0x0603D570).to_bytes(4, "big"),
     D00_CAVE_ADDR.to_bytes(4, "big"),
     "composer pool -> cave"),
    # S4b — composer branch-B block 0x0607F418..0x0607F425 becomes the
    # detour call (0x0607F416 `mov.l @(pc),r2` now loads the cave address).
    (0x0607F418 - _B,
     _w(0x2149, 0x311C, 0x7104, 0x6222, 0x6013, 0x012D, 0x611D),
     _w(0x420B, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009),
     "composer branch B: jsr @r2 (cave) + nops"),
]

PROG3_D00_OFFSET_SCALE = {
    "LANG/PROG_3.BIN": [(off, new) for off, _jp, new, _c in _SITES],
}

JP_BASELINE = {off: jp for off, jp, _new, _c in _SITES}
