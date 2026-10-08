"""tools/name_twin_cave.py — twin->hankaku append cave (v4 "display twins").

SH-2 code cave riding FONT.BIN (LWRAM 0x00288000, resident whenever text can
render — the balloon_zenkaku_cave / d00_offset_cave delivery pattern; tiles
1429-1430, the free pair right above the nakaguro at 1428; 1426 stays
off-limits per the legacy-'Yo' canon).

WHY: the v4 name-entry keyboard records carry TWIN tiles (wide-class copies
of the hankaku letterforms at +TWIN_K, font_tools.TWIN_TILE_MAP) so the
field-UI renderer draws the keys in 16px columns under the positional
selector. But the composer appends the CELL'S OWN tile to the name buffer
(0x06034D90) — a raw twin there would render 16px in prose and break the
8px name. This cave redoes the append FETCH and subtracts TWIN_K, so the
buffer receives the hankaku tile: draw 16px, register 8px.

CALL SITE (tools/prog4_name_twin_convert.py): the 6-word fetch-address block
at PROG_4 file 0x8D2A..0x8D35 becomes a jmp stub into this cave; the cave
does the whole block's job plus the fetch (0x8D56's `mov.w @r6,r6`, which
the stub module turns into a nop) plus the -K, and jumps straight back to
the untouched JP code at load 0x06091D36.

Register contract (JP disasm, 2026-07-15 session): entry r2 = keyboard-list
entry addr (computed at 0x8D14..28, untouched); r0/r1/r2/r6 are free across
the replaced block (r3/r7 are reloaded after it); r4 = pos and r5 = &posvar
are LIVE and preserved here (never touched). No pr save needed: this is a
jmp/jmp round trip, not jsr/rts. `mov.w @r6,r6` sign-extends, but every
fetchable cell is a twin (< 0x8000) — guarded by
tests/test_name_entry_twin_glyphs.py, which also EXECUTES this blob.

The -K is UNCONDITIONAL: button rows (block 2 rows 5-6) never reach the
append (positional dispatch at 0x8C94/0x8CCE bails first), and the fntsys14
records guard pins every fetchable cell inside the twin band.
"""
from balloon_zenkaku_cave import FONT_LWRAM_BASE
from font_tools import TWIN_K

NAME_TWIN_CAVE_TILE = 1429       # free pair above the nakaguro (1428)
NAME_TWIN_CAVE_TILES = 2
NAME_TWIN_CAVE_ADDR = FONT_LWRAM_BASE + NAME_TWIN_CAVE_TILE * 32

COL_VAR_ADDR = 0x06095609        # keyboard column (byte), the JP pool value
RETURN_ADDR = 0x06091D36         # the untouched JP insn after the stub


def _assemble(resolve, labels):
    out = []

    def here():
        return len(out) * 2

    def w(x):
        out.append(x & 0xFFFF)

    def mark(name):
        labels[name] = here()

    def movw_pc(rn, lbl):        # mov.w @(disp,PC),Rn
        d = 0
        if resolve:
            d = (labels[lbl] - (here() + 4)) // 2
            assert 0 <= d < 256, (lbl, d)
        w(0x9000 | rn << 8 | d)

    def movl_pc(rn, lbl):        # mov.l @(disp,PC),Rn
        d = 0
        if resolve:
            d = (labels[lbl] - ((here() & ~3) + 4)) // 4
            assert 0 <= d < 256, (lbl, d)
        w(0xD000 | rn << 8 | d)

    # ---- the replaced block's job + fetch + conversion ---------------------
    movl_pc(1, 'COLVAR')         # mov.l #0x06095609,r1
    w(0x6110)                    # mov.b @r1,r1        ; col (0..4)
    w(0x5223)                    # mov.l @(12,r2),r2   ; record ptr
    w(0x311C)                    # add r1,r1           ; col*2 (5-cell rows)
    w(0x6613)                    # mov r1,r6
    w(0x362C)                    # add r2,r6           ; r6 = &rec[col]
    w(0x6661)                    # mov.w @r6,r6        ; r6 = twin tile
    movw_pc(1, 'K')              # mov.w #TWIN_K,r1
    w(0x3618)                    # sub r1,r6           ; r6 = hankaku tile
    movl_pc(0, 'RET')            # mov.l #0x06091D36,r0
    w(0x402B)                    # jmp @r0             ; back to the JP tail
    w(0x0009)                    # (delay) nop
    # ---- literal pool -------------------------------------------------------
    while here() % 4:
        w(0x0009)
    mark('COLVAR')
    w(COL_VAR_ADDR >> 16); w(COL_VAR_ADDR)
    mark('RET')
    w(RETURN_ADDR >> 16); w(RETURN_ADDR)
    mark('K')
    w(TWIN_K)
    return b''.join(x.to_bytes(2, 'big') for x in out)


def cave_blob():
    """The assembled cave (two passes: label discovery, then resolution)."""
    labels = {}
    _assemble(False, labels)
    blob = _assemble(True, labels)
    assert len(blob) <= NAME_TWIN_CAVE_TILES * 32, len(blob)
    return blob


# Encoding spot-checks against opcodes seen in the PROG_4 disassembly.
_b = cave_blob()
assert _b.count(b"\x40\x2b") == 1   # exactly one jmp @r0 (the way back)
assert b"\x66\x61" in _b            # the relocated fetch (mov.w @r6,r6)
assert b"\x36\x18" in _b            # sub r1,r6 (the -K conversion)
del _b
