"""tools/d00_offset_cave.py — composer-side entry-offset fetch (Piece D v2).

Tiny SH-2 cave for the ONE scaled-offset reader that cannot be rewritten in
place: the composer FUN_0607f364's branch-B fetch (its 8-word block has no
spare slot for the extra `shll`, unlike the other three readers). The
composer saves pr in its prologue (0x0607F36E `sts.l pr,@-r15`), so a jsr
detour is safe.

Hook: prog3_d00_offset_scale repoints the pool literal 0x0607F49C (was the
text-area base var 0x0603D570) to this cave and turns the block into
`jsr @r2` + nops. Entry state (verified in the branch-B disasm): r1 = entry
index mask (DAT_0607f474, via the bt/s delay slot), r4 = param (extu'd).
Returns r1 = REAL entry offset (stored u16 * 2) and r2 = text-area base, so
the untouched join at 0x0607F426 (`mov r1,r8; add r2,r8`) composes the entry
pointer exactly as before.

Rides FONT.BIN like the zenkaku dispatch cave: tile 1427 (LWRAM 0x00293260),
between the nakaguro glyph (1426) and the _VD_SPACE bigrams (1435+).
"""

FONT_LWRAM_BASE = 0x00288000
D00_CAVE_TILE = 1427
D00_CAVE_TILES = 1
D00_CAVE_ADDR = FONT_LWRAM_BASE + D00_CAVE_TILE * 32

_BASE_VAR = 0x0603D570        # text-area base pointer variable (A0LANG-set)


def d00_cave_blob() -> bytes:
    words = [
        0x2149,   # and   r4,r1        ; idx = mask & param
        0x311C,   # add   r1,r1        ; idx*2
        0x7104,   # add   #4,r1        ; table disp
        0xD204,   # mov.l @(pc+...),r2 ; r2 = &base_var  (pool below)
        0x6222,   # mov.l @r2,r2       ; r2 = text-area base
        0x6013,   # mov   r1,r0
        0x012D,   # mov.w @(r0,r2),r1  ; stored offset (u16, /2)
        0x611D,   # extu.w r1,r1
        0x000B,   # rts
        0x4100,   # (delay) shll r1    ; r1 = real offset
        0x0009,   # pad to 4-align the pool
        0x0009,
    ]
    blob = b"".join(w.to_bytes(2, "big") for w in words)
    # pool literal: mov.l @(disp,PC) at word 3 (byte 6):
    # EA = (6 & ~3) + 4 + disp*4 = 4 + 4 + 2*4 = 16?? — computed below instead.
    pool_off = len(blob)
    # verify the D204 displacement actually lands on the pool:
    # EA = (instr_byte & ~3) + 4 + disp*4, instr at byte 6, disp 4
    ea = (6 & ~3) + 4 + 0x04 * 4
    assert ea == pool_off, (ea, pool_off)
    blob += _BASE_VAR.to_bytes(4, "big")
    assert len(blob) <= D00_CAVE_TILES * 32, len(blob)
    return blob


_b = d00_cave_blob()
assert _b[:2] == b"\x21\x49"
assert _b.endswith(_BASE_VAR.to_bytes(4, "big"))
del _b
