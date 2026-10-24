"""tools/prog5_terrain_hud_ascii.py: the terrain HUD in the small ASCII font.

Owned byte patch over the **JP** `LANG/PROG_5.BIN` (load base 0x06089000).

WHY (user playtest 2026-10-18, RE 2026-10-23): the small HUD that names the
terrain under the cursor showed garbage like "Wast" for Wasteland. PROG_5
FUN_06089094 (file 0x0094, entry slot 0x06089034 of the PROG_5 export table)
builds a FIXED 4-glyph string, [name tile 0][name tile 1][tens][ones],
rasterizes it with PROG_3 FUN_0607d0b8 into VDP1 VRAM 0x62880 and queues four
VDP1 sprites: name 16x16 at x 240/256, digits scaled to 12x16 at x 276/288,
y 200. JP names are always 2 kanji; EN names are 2 to 9 tiles, so only the
first two tiles were ever drawn. Evidence logs (Ghidra, ghidra-proj/evidence):
20261023-155155_PROG_5_decompile_force.txt, 20261023-155649_A0LANG_decompile.txt.

THE REWRITE (in place, file 0x0094..0x02C8 = the old function + its pool):
one 8x8 VDP1 sprite per character from the small ASCII font that the game
already keeps in VDP1 VRAM at 0x10000 + code * 32 (the PRESS START BUTTON /
battle skill label font, archive/docs/20261012_name_check_and_ram_re.md 7;
the "Treatment" label in the same battle mode queues exactly these sprites:
CMDSRCA 0x2000 + code * 4, CMDSIZE 0x0108, CMDCOLR 0x00B0, CMDPMOD 0x0080).
No rasterizing and no VRAM copy any more. The text is "<name> <bonus>",
drawn right to left so its last digit ends at x 300 like the JP one, on y 204
(the 8px row centred on the JP 16px row). Spaces only advance the pen.

Kept from JP: the two gate flags (0x0604E6F7 must be set, 0x060370D7 clear,
else return 0x2F and draw nothing), the store of the terrain id at
0x06091580, the bonus lookup bonus[class[param_2]][terrain] in the PROG_3
tables 0x06085D78 / 0x06085D96, the sprite queue A0LANG FUN_0602e034 with
priority 0x00C80000. The queue DMAs a 36-byte VDP1 command from the stack.

NAMES: generated at build time from scripts/en/fntsys1E.txt records 199..226
(the 28 terrains; the bonus table rows are 28 wide), so the HUD and the
terrain panel read the same text. Stored after the code as 28 u8 offsets,
then each name REVERSED and NUL terminated (the pen walks right to left).

Source (GNU as, `sh-elf-as --big`, linked at 0x06089094):
    push r8-r14, pr ; r15 -= 36 ; r14 = r15            (command on the stack)
    gates -> .Lquit (r0 = 0x2F)
    r8 = terrain ; *(u16*)0x06091580 = r8
    r9 = bonus[class[param_2]][r8] ; r13 = r9 / 10 ; r9 %= 10 (by subtraction)
    command: CTRL 0, LINK 0, PMOD 0x80, COLR 0xB0, SIZE 0x0108, YA 204, GRDA 0
    r11 = &CMDSRCA, r12 = &CMDXA, r10 = x = 292
    put(r9 + '0') ; x -= 8 ; if r13: put(r13 + '0') ; x -= 8
    x -= 8                                              (the space)
    for c in reversed name: if c != ' ': put(c) ; x -= 8
    r0 = 1 ; pop ; rts
  put(c): CMDSRCA = 0x2000 + c * 4 ; CMDXA = x ; jsr 0x0602E034(r14, 0x00C80000)

Guard: tests/test_prog5_terrain_hud_ascii.py (runs the BUILT bytes on
tools/sh2_mini with the real PROG_3 tables, every terrain and class).
"""
import hashlib
from pathlib import Path

PROG5_BASE = 0x06089000
REGION_OFF = 0x0094            # FUN_06089094
REGION_END = 0x02C8            # end of its literal pool (next function)
FNTSYS1_TERRAIN = 199          # fntsys1 record of terrain 0 (Plains)
TERRAINS = 28
NAMES_SCRIPT = Path(__file__).resolve().parent.parent / "scripts/en/fntsys1E.txt"

# JP bytes of the whole region, so a drifted offset fails loudly.
JP_BASELINE_SHA256 = "ad0192dc8648bbc8a2b5dfb4c9f68b9a30abcd3e54e9ed1f8e4aaa52bde164d6"

CODE = bytes.fromhex(
    "2f862f962fa62fb62fc62fd62fe64f22"
    "7fdc6ef3d1386110611c21188952d137"
    "6110611c21188b4d684cd1352181605c"
    "d134011c611ce21c0127011ad232312c"
    "6083091c699ced00e10a39128b0279f6"
    "affb7d01e00061e32101710221017102"
    "925a212171029258212171026b137102"
    "9254212171026c1371029250212161e3"
    "711c21019a4c6493b02874307af82dd8"
    "890364d3b02274307af87af8d11b6083"
    "001c600c310c711c69136494644c2448"
    "8906e12034108901b0100009aff57af8"
    "a001e001e02f7e246fe34f266ef66df6"
    "6cf66bf66af669f6000b68f64f224408"
    "911f341c2b412ca164e3d509d109410b"
    "00094f26000b00090604e6f7060370d7"
    "0609158006085d7806085d96060891b8"
    "00c800000602e034008000b0010800cc"
    "01242000"
)
NAMES_LITERAL_OFF = 0x10C      # .Lnames in CODE: absolute address of the table


def terrain_names(script=NAMES_SCRIPT):
    from fnt_sys_tools import _parse_script_records
    recs = _parse_script_records(Path(script))
    names = [r.replace("<$FFFF>", "")
             for r in recs[FNTSYS1_TERRAIN:FNTSYS1_TERRAIN + TERRAINS]]
    for name in names:
        if not name or not all(0x20 <= ord(c) < 0x7F for c in name):
            raise ValueError(f"terrain name not plain ASCII: {name!r}")
    return names


def names_table(names):
    offsets, text = bytearray(), bytearray()
    for name in names:
        offsets.append(len(text))
        text += name[::-1].encode("ascii") + b"\x00"
    if len(text) > 0x100:
        raise ValueError("terrain name table too large for u8 offsets")
    return bytes(offsets) + bytes(text)


def region_blob(names=None):
    table_addr = int.from_bytes(CODE[NAMES_LITERAL_OFF:NAMES_LITERAL_OFF + 4],
                                "big")
    assert table_addr == PROG5_BASE + REGION_OFF + len(CODE)
    blob = CODE + names_table(terrain_names() if names is None else names)
    size = REGION_END - REGION_OFF
    if len(blob) > size:
        raise ValueError(f"terrain HUD blob {len(blob)} B > {size} B region")
    return blob + bytes(size - len(blob))


def jp_region_sha256(jp_prog5):
    return hashlib.sha256(jp_prog5[REGION_OFF:REGION_END]).hexdigest()


PROG5_TERRAIN_HUD_ASCII = {
    "LANG/PROG_5.BIN": [(REGION_OFF, region_blob())],
}
