"""tools/prog4_name_twin_convert.py — name-entry append twin->hankaku (v4).

TWO owned byte patches over the **JP** `LANG/PROG_4.BIN` (load 0x06089000),
pairing with tools/name_twin_cave.py (the FONT.BIN-resident conversion cave)
and the twin keyboard records (tools/fntsys14_hankaku_keyboard.py).

WHY (Ralf, 2026-07-15): "desenhar as letras do teclado no passo 16px mas
registrar os caracteres no passo 8px". The records carry WIDE-class twin
tiles (hankaku letterform centered in the 16px tile, font_tools
TWIN_TILE_MAP) so the keys draw in 16px columns under the positional
selector — but the composer appends the cell's own tile to the name buffer
0x06034D90, and a raw twin there would render 16px. These patches route the
append fetch through the cave, which subtracts TWIN_K before the store:
the buffer receives hankaku tiles (8px prose render via F600, save format
untouched). Both record-shaped 16px attempts were withdrawn (staging-ring
overflow / slot-ABI corruption — archive/docs/20260714_name_entry_freeze_
bug.md); v4 keeps records at 5 cells and the renderer untouched.

SITE (JP disasm, this session; no branch targets inside either region):

  file 0x8D2A  d127  mov.l @(pc),r1 ! 0x6095609 (col)  ┐ 6-word fetch-address
       0x8D2C  6110  mov.b @r1,r1                      │ block -> jmp STUB.
       0x8D2E  5223  mov.l @(12,r2),r2 ; record ptr    │ Entry contract:
       0x8D30  311c  add r1,r1         ; col*2         │ r2 = list entry addr
       0x8D32  6613  mov r1,r6                         │ (set at 0x8D14..28).
       0x8D34  362c  add r2,r6         ; r6=&rec[col]  ┘
       0x8D36  344c  add r4,r4         ; <- the cave jumps back HERE
  ...  0x8D56  6661  mov.w @r6,r6      ; the fetch     -> nop (cave did it)
       0x8D5A  0365  mov.w r6,@(r0,r3) ; name[pos] = r6 (untouched)

THE STUB (6 words, exactly the replaced block — the pool long rides the
DEAD words after the jmp delay slot, so alignment costs nothing):

       0x8D2A  D001  mov.l @(1,pc),r0  ; = cave addr from 0x8D30
       0x8D2C  402B  jmp @r0           ; jmp, NOT jsr: pr never touched
       0x8D2E  0009  nop (delay)
       0x8D30  <NAME_TWIN_CAVE_ADDR>   ; pool long (never executed)
       0x8D34  0009  nop               ; dead filler

The cave preserves r4 (pos) / r5 (&posvar) — the only live registers — and
returns r6 = twin - TWIN_K. See name_twin_cave.py for the register proof.

NOT TOUCHED: the 8-entry cap (0x8D06), the cursor patches (0x908A/0x911E,
prog4_name_entry_hankaku), the button dispatch (0x8C94/0x8CCE), and the
key fetch stride semantics (the cave re-implements the JP col*2).

Guard: tests/test_name_entry_twin_glyphs.py (JP truth-locks + an SH-2
mini-interpreter that EXECUTES stub + cave + the untouched JP tail).
"""
from font_tools import TWIN_K, TWIN_TILE_MAP
from name_twin_cave import NAME_TWIN_CAVE_ADDR

# ── Patch site bookkeeping ──────────────────────────────────────────────────
PROG4_LOAD_BASE = 0x06089000
STUB_OFF = 0x8D2A                # 6-word fetch-address block -> jmp stub
FETCH_OFF = 0x8D56               # mov.w @r6,r6 -> nop (the cave fetched)

_STUB = (
    bytes.fromhex("D001")                      # mov.l @(1,pc),r0
    + bytes.fromhex("402B")                    # jmp @r0
    + bytes.fromhex("0009")                    # (delay) nop
    + NAME_TWIN_CAVE_ADDR.to_bytes(4, "big")   # pool (dead words)
    + bytes.fromhex("0009")                    # dead filler
)
assert len(_STUB) == 12          # exactly fills 0x8D2A..0x8D35

PROG4_NAME_TWIN_CONVERT = {
    "LANG/PROG_4.BIN": [
        (STUB_OFF, _STUB),
        (FETCH_OFF, bytes.fromhex("0009")),
    ],
}

# JP baseline at both sites — truth-locked against the pristine JP disc
# by tests/test_name_entry_twin_glyphs.py before any build.
PROG4_NAME_TWIN_CONVERT_JP_BASELINE = {
    STUB_OFF: bytes.fromhex("d127 6110 5223 311c 6613 362c".replace(" ", "")),
    FETCH_OFF: bytes.fromhex("6661"),
}


# ── Python model (the requirement the bytes implement) ──────────────────────
def is_twin_tile(tile: int) -> bool:
    """True for the keyboard's display-twin band."""
    return tile in set(TWIN_TILE_MAP.values())


def twin_to_hankaku(tile: int) -> int:
    """What the cave stores for a fetched twin cell: the 8px hankaku tile."""
    return tile - TWIN_K


def appended_tile(cell: int) -> int:
    """The word that reaches the name buffer for a fetchable cell. The -K
    is unconditional (button rows never reach the append), so cells MUST
    be twins — enforced by the records guard."""
    assert is_twin_tile(cell), f"fetchable cell {cell} outside the twin band"
    return twin_to_hankaku(cell)
