"""tools/name_check.py — END refuses the name of a character again.

JP (PROG_4 FUN_060923A8, load 0x060923A8..0x0609243B, RE in
archive/docs/20261012_name_check_and_ram_re.md, 1): on END the name screen
compares the typed name with FNT_SYS records (fntsys11 ids 1..0x17B except
the two Diehärte, fntsys10 ids 13/14) through A0LANG 0x06016C84 and shows
"That name can't be used" on a match. In the EN build those records are
bigram tiles and the typed name is 8px band tiles, so nothing ever matches.

THE LIST (settled with Ralf, 2026-10-13): the fntsys11 names minus GENERIC
(people without a name, army commanders, nations), plus the swords
Langrisser and Alhazard (fntsys10 records 12/13; the JP checks 13/14,
Alhazard and Hand Axe, an off-by-one). Only names the keyboard can type in
16 letters. Letter case is ignored. Diehärte (the default) is never listed.

DATA: one byte per letter (band tile - 1264, 1..85), each name ends in 0,
the list ends with an empty name. In front of it, FOLD: 86 bytes, band
index -> the index of its lowercase letter (0xFF for index 0). It rides the
end of FNT_SYS.BIN at the fixed file offset LIST_OFF (FNT_SYS loads whole at
0x00246000 and is in RAM on the name screen, it holds the keyboard). The file
is padded with zeros up to LIST_OFF; the blob ends at or below 0xE000
(28 sectors, below the 0x254400 neighbor even with a sector-rounded load).

CODE: written over the JP function, same entry, same contract (r0 = 1
allowed, 0 refused; the caller tests extu.w r0 == 1 at 0x06091B6A). It ends
before 0x0609243C, the name pointer pool word that name_buffer_home owns,
and reads the name address from it. It only lives in RAM with PROG_4.
  1. find the end of the name: the FFFF, then back over trailing spaces
     (the space key types the band space, which the JP trim does not drop);
  2. for each list name: fold each typed letter through FOLD (a tile out of
     the band folds to -1, which matches nothing) and compare it with the
     list byte; both at 0 = match = refuse.
Registers r0..r7 only, no calls (JP r8..r14 are not used by the caller after
the call, but the code does not touch them anyway).

Guard: tests/test_name_check.py (list rules, the code executed on the built
PROG_4 with the built FNT_SYS: every listed name refused in any case and with
trailing spaces, other names allowed).
"""
from pathlib import Path

from a0lang_save_name_pack import _Asm
from font_tools import HANKAKU_TILE_MAP

FNTSYS_LOAD = 0x00246000
LIST_OFF = 0xDC00                 # FNT_SYS file offset of FOLD + names
LIST_ROOM = 0xE000 - LIST_OFF     # 1 KB, the blob must end at 0xE000
LIST_ADDR = FNTSYS_LOAD + LIST_OFF

BAND_LO, BAND_SLOTS = 1264, 86    # index = tile - 1264; band is 1..85
CHECK_OFF = 0x93A8                # PROG_4 file offset of FUN_060923A8
NAME_POOL_OFF = 0x943C            # pool word with the name address (name_buffer_home)
PROG4_LOAD_BASE = 0x06089000

CHAR_IDS = [i for i in range(1, 0x17C) if i not in (0x28, 0x30)]   # fntsys11, as JP
SWORD_IDS = (12, 13)              # fntsys10: Langrisser, Alhazard

GENERIC = frozenset({
    # people and creatures without a name
    'Lord', 'Street Hawker', 'Shopkeeper', 'Bat', 'Serpent', 'High Priest',
    'Commoner', 'Monster', 'Thief', 'Thief Leader',
    # army commanders
    'Barral Commander', 'Shika Commander', 'Colcia Commander',
    'Rigüler Captain', 'Elthlead Army',
    # nations and peoples
    'Rigüler', 'Barral', 'Shika', 'Larcuss', 'Colcia', 'Elthlead',
})


def _keyboard_chars():
    from fntsys14_hankaku_keyboard import KEYBOARD_ROWS
    return frozenset(''.join(KEYBOARD_ROWS).replace('_', '') + ' ')


TYPEABLE = _keyboard_chars()      # '_' cells type the band space


def _records(scripts_dir: Path, n: int) -> list:
    from fnt_sys_tools import _parse_script_records
    path = Path(scripts_dir) / f'fntsys{n}E.txt'
    return [r.replace('<$FFFF>', '') for r in _parse_script_records(path)]


def refused_names(scripts_dir: Path) -> list:
    """The names END refuses, in script spelling, first occurrence order."""
    chars, items = _records(scripts_dir, 11), _records(scripts_dir, 10)
    out = []
    for name in [chars[i] for i in CHAR_IDS] + [items[i] for i in SWORD_IDS]:
        if (name and name not in GENERIC and len(name) <= 16
                and set(name) <= TYPEABLE and name.lower() not in
                {n.lower() for n in out}):
            out.append(name)
    return out


def _index(ch: str) -> int:
    return HANKAKU_TILE_MAP[ch] - BAND_LO


def fold_table() -> bytes:
    table = bytearray(range(BAND_SLOTS))
    table[0] = 0xFF
    for ch, tile in HANKAKU_TILE_MAP.items():
        low = ch.lower()
        if BAND_LO < tile < BAND_LO + BAND_SLOTS and low in HANKAKU_TILE_MAP:
            table[tile - BAND_LO] = _index(low)
    return bytes(table)


def list_blob(scripts_dir: Path) -> bytes:
    names = b''.join(bytes(_index(c) for c in n.lower()) + b'\0'
                     for n in refused_names(scripts_dir))
    blob = fold_table() + names + b'\0'
    assert len(blob) <= LIST_ROOM, f'name list {len(blob)} B > {LIST_ROOM} B'
    return blob


def with_list(fnt_sys: bytes, scripts_dir: Path) -> bytes:
    """FNT_SYS.BIN + zero padding up to LIST_OFF + the list blob."""
    if len(fnt_sys) > LIST_OFF:
        raise ValueError(f'FNT_SYS {len(fnt_sys)} B runs into the name list at '
                         f'0x{LIST_OFF:X}')
    return fnt_sys + bytes(LIST_OFF - len(fnt_sys)) + list_blob(scripts_dir)


def _code(a):
    space = HANKAKU_TILE_MAP[' ']
    a.labels['NAMEP'] = NAME_POOL_OFF - CHECK_OFF
    a.movl_pc(7, 'LIST')          # r7 = FOLD
    a.w(0x6473)                   # mov r7,r4
    a.w(0x7400 | BAND_SLOTS)      # add #86,r4      ; r4 = first list name
    a.movl_pc(5, 'NAMEP')         # r5 = name
    a.w(0x6153)                   # mov r5,r1
    a.mark('SCAN')
    a.w(0x6015)                   # mov.w @r1+,r0
    a.w(0x88FF)                   # cmp/eq #-1,r0
    a.bf('SCAN')
    a.w(0x71FE)                   # add #-2,r1      ; r1 = the FFFF
    a.movw_pc(3, 'SPACE')         # r3 = band space tile
    a.mark('TRIM')
    a.w(0x3150)                   # cmp/eq r5,r1
    a.bt('START')
    a.w(0x6213)                   # mov r1,r2
    a.w(0x72FE)                   # add #-2,r2
    a.w(0x6021)                   # mov.w @r2,r0
    a.w(0x3030)                   # cmp/eq r3,r0
    a.bf('START')
    a.bra('TRIM')
    a.w(0x6123)                   # (delay) mov r2,r1 ; r1 = name end
    a.mark('START')
    a.movw_pc(6, 'NEG')           # r6 = -1264
    a.mark('NEXT')
    a.w(0x6040)                   # mov.b @r4,r0
    a.w(0x8800)                   # cmp/eq #0,r0    ; empty name = list end
    a.bt('ALLOW')
    a.movl_pc(5, 'NAMEP')         # r5 = name
    a.mark('CMP')
    a.w(0x3510)                   # cmp/eq r1,r5    ; past the last letter
    a.bts('GOT')
    a.w(0xE200)                   # (delay) mov #0,r2
    a.w(0x6055)                   # mov.w @r5+,r0
    a.w(0x306C)                   # add r6,r0       ; band index
    a.w(0xE200 | BAND_SLOTS)      # mov #86,r2
    a.w(0x3022)                   # cmp/hs r2,r0    ; out of the band (unsigned)
    a.bts('GOT')
    a.w(0xE2FF)                   # (delay) mov #-1,r2
    a.w(0x027C)                   # mov.b @(r0,r7),r2 ; folded letter
    a.mark('GOT')
    a.w(0x6344)                   # mov.b @r4+,r3
    a.w(0x3230)                   # cmp/eq r3,r2
    a.bf('MISS')
    a.w(0x2338)                   # tst r3,r3
    a.bf('CMP')
    a.w(0x000B)                   # rts             ; whole name matched
    a.w(0xE000)                   # (delay) mov #0,r0 = refuse
    a.mark('MISS')
    a.w(0x2338)                   # tst r3,r3       ; list name already ended
    a.bt('NEXT')
    a.mark('SKIP')
    a.w(0x6044)                   # mov.b @r4+,r0
    a.w(0x2008)                   # tst r0,r0
    a.bf('SKIP')
    a.bra('NEXT')
    a.w(0x0009)                   # (delay) nop
    a.mark('ALLOW')
    a.w(0x000B)                   # rts
    a.w(0xE001)                   # (delay) mov #1,r0 = allow
    a.word('SPACE', space)
    a.word('NEG', (-BAND_LO) & 0xFFFF)
    a.long('LIST', LIST_ADDR)


def code_blob() -> bytes:
    labels = {}
    first = _Asm(labels, False)
    _code(first)
    second = _Asm(labels, True)
    _code(second)
    blob = second.blob()
    assert CHECK_OFF + len(blob) <= NAME_POOL_OFF, len(blob)
    return blob


NAME_CHECK = {
    'LANG/PROG_4.BIN': [(CHECK_OFF, code_blob())],
}

NAME_CHECK_JP_BASELINE = {
    CHECK_OFF: bytes.fromhex(
        '2f862f962fa62fe64f226ef3e801da1ed91e608d88288d10780188308d0d300cd11b'
        '6112051dd41b655d61a2355c490b351c600d88018d1fe000628d912332168fe8608d'
        'e80dda14d910628dd11360236112300c051dd40f655d61a2355c490b351c600d8801'
        '8f027801a005e000628de10e32168fea00296fe34f266ef66af669f6000b68f6017b'
        '0604eb6806016c840604e9fc'),
}
