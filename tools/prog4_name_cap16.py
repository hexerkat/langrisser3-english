"""tools/prog4_name_cap16.py — the name entry takes 16 letters (was 8).

Owned byte patches over the JP LANG/PROG_4.BIN (load base 0x06089000). The
name is 8px hankaku letters only (keyboard twins -> band, the default name in
the band too: fntsys11_default_name), so 16 letters fill the same 128px as the
8 zenkaku of the JP field. The buffer moves first (name_buffer_home: 17 words)
and the save packs 16 letters into the old 18 bytes (a0lang_save_name_pack).

Five sites bound the name at 8 entries (JP disasm 2026-10-12, Ghidra logs
ghidra-proj/evidence/20261012-19*_PROG_4_*):

1. APPEND CAP, file 0x8D06 (load 0x06091D06), 7 words. JP:
       mov #7,r2 ; extu.b r1,r3 ; cmp/hi r2,r3 ; bf/s ok ; mov r3,r4 ;
       bra refuse ; nop                         (ok = 0x06091D14)
   The 7 in r2 is ALSO the rows-per-block multiplier at 0x06091D18
   (`mul.l r2,r1`: list index = block*7 + row), so `mov #15,r2` would break
   the keyboard. Rewrite, same length, r0 free here (next read 0x06091D3C):
       mov #15,r0 ; extu.b r1,r3 ; cmp/hi r0,r3 ; bf/s 0x06091D12 ; mov r3,r4 ;
       bra refuse ; mov #7,r2
   The last insn is both the delay slot of the refuse bra (the refuse path
   reloads r0..r2) and the target of the bf/s, so r2 = 7 on the ok path.
2. END non-empty scan, file 0x8C1E: mov #7,r5 -> mov #15,r5 (END accepts
   the name if any entry 0..15 is not tile 0; r5 dead after the loop).
3. NAME LENGTH, file 0x934E (FUN_06092348, trims trailing tile-0 blanks and
   returns the length the cursor resumes at): mov #7,r6 -> mov #15,r6. The
   July doc gave 0x924E; the disc has it at 0x934E.
4. CURSOR PARK, file 0x907A (FUN_06092070): mov #7,r1 -> mov #15,r1 (the
   sprite parks on the last cell past the cap; its X word at 0x911E is owned
   by prog4_name_entry_hankaku: 0xB0 + 15*8).
5. DEFAULT NAME COPY, file 0x8A1E: the name screen copies fntsys11 record 0
   into the buffer through A0LANG 0x06016D04 (r6 = max words, then FFFF):
   mov #6,r6 -> mov #16,r6 so the 8-letter default is not cut at 6.

Not touched: `mov #7` at 0x8410/0x84C4/0x85D8/0x86EA/0x87B4 (record color
bytes of FUN_060912e8, not lengths).

Guard: tests/test_name_cap16.py (executes the append, END scan, length and
cursor on the real bytes; baselines locked against the JP disc).
"""

PROG4_LOAD_BASE = 0x06089000
NAME_CAP = 16

APPEND_CAP_OFF = 0x8D06
END_SCAN_OFF = 0x8C1E
LENGTH_OFF = 0x934E
CURSOR_PARK_OFF = 0x907A
DEFAULT_COPY_OFF = 0x8A1E

PROG4_NAME_CAP16 = {
    "LANG/PROG_4.BIN": [
        (APPEND_CAP_OFF, bytes.fromhex("e00f631c33068f016433a0c0e207")),
        (END_SCAN_OFF, bytes.fromhex("e50f")),
        (LENGTH_OFF, bytes.fromhex("e60f")),
        (CURSOR_PARK_OFF, bytes.fromhex("e10f")),
        (DEFAULT_COPY_OFF, bytes.fromhex("e610")),
    ],
}

PROG4_NAME_CAP16_JP_BASELINE = {
    APPEND_CAP_OFF: bytes.fromhex("e207631c33268f026433a0c0200b"),
    END_SCAN_OFF: bytes.fromhex("e507"),
    LENGTH_OFF: bytes.fromhex("e607"),
    CURSOR_PARK_OFF: bytes.fromhex("e107"),
    DEFAULT_COPY_OFF: bytes.fromhex("e606"),
}
