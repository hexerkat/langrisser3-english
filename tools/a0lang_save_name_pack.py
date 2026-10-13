"""tools/a0lang_save_name_pack.py — 16 letters in the save's 18-byte name field.

The save image (staging 0x0604B3BC..0x0604BF8B, checksum at 0x0604BF8B) has
no slack: the name field is 9 words at 0x0604BF58 and live fields sit on both
sides (save layout in archive/docs/20261012_name_check_and_ram_re.md, 9).
A 16-letter name (17 words in RAM) is packed into the same 18 bytes:

  bytes 0..15  one letter per byte, tile - 1264 (hankaku band 1265..1349 ->
               1..85), 0x00 after the last letter
  bytes 16..17 0xA55A, the "packed" mark

A name with any tile outside the band (a JP or bigram name from an old save)
keeps the JP raw format, 9 words copied as is. Loading checks word 8: in a
raw save it is a tile, 0xFFFF or a leftover 0x0000 (the JP cap of 8 always
puts FFFF at word 8 or earlier), never 0xA55A. So old saves load exactly as
before, and the image size, offsets and checksum code do not change.

CALL SITES (A0LANG, load base 0x0600E000): the two 10-word name copy loops
  gather  FUN_0601566c, file 0x771E (load 0x0601571E..0x06015731)
  scatter FUN_0601592c, file 0x7A22 (load 0x06015A22..0x06015A35)
become the same stub:
  mov.l @(2,pc),r0 ; jsr @r0 ; nop ; bra +5 ; nop ; .long CAVE ; nop x3
The bra lands on the next JP instruction (0x06015732 / 0x06015A36). Both
functions push PR in their prologue (sts.l pr,@-r15), so the jsr is safe.
After each loop the JP code reloads r1..r3 and writes r0, r4..r7 and r9
before reading them (disasm 0x06015732..0x060157BE and 0x06015A36..), so the
caves may use r0..r7. They never touch r8..r15.

CAVES ride FONT.BIN (LWRAM 0x00288000), cave block (font_tools.CAVE_BLOCK):
PACK 1454-1456, UNPACK 1457-1459. The save and load screens draw text, so the
font is loaded
when they run.

Guard: tests/test_name_cap16.py (executes stub + cave on the real A0LANG
bytes: every length 0..16 round-trips, old saves load as the JP code loads
them, neighbors of the field stay untouched).
"""
from balloon_zenkaku_cave import FONT_LWRAM_BASE
from name_buffer_home import NAME_HOME

SAVE_NAME = 0x0604BF58           # the 9-word name field of the save image
MAGIC = 0xA55A
BAND_LO, BAND_SIZE = 1265, 85    # hankaku band 1265..1349 (width_class)
LETTERS = 16

PACK_TILE, PACK_TILES = 1454, 3
UNPACK_TILE, UNPACK_TILES = 1457, 3
PACK_ADDR = FONT_LWRAM_BASE + PACK_TILE * 32
UNPACK_ADDR = FONT_LWRAM_BASE + UNPACK_TILE * 32

A0LANG_LOAD_BASE = 0x0600E000
GATHER_OFF = 0x771E
SCATTER_OFF = 0x7A22


class _Asm:
    """Two-pass SH-2 assembler for the few forms the caves use."""

    def __init__(self, labels, resolve):
        self.out, self.labels, self.resolve = [], labels, resolve

    def here(self):
        return len(self.out) * 2

    def w(self, x):
        self.out.append(x & 0xFFFF)

    def mark(self, name):
        self.labels[name] = self.here()

    def _disp(self, lbl, base, scale, lo, hi):
        if not self.resolve:
            return 0
        d = (self.labels[lbl] - base) // scale
        assert lo <= d <= hi, (lbl, d)
        return d

    def movl_pc(self, rn, lbl):          # mov.l @(disp,PC),Rn
        self.w(0xD000 | rn << 8 | self._disp(lbl, (self.here() & ~3) + 4, 4, 0, 255))

    def movw_pc(self, rn, lbl):          # mov.w @(disp,PC),Rn
        self.w(0x9000 | rn << 8 | self._disp(lbl, self.here() + 4, 2, 0, 255))

    def bt(self, lbl):
        self.w(0x8900 | (self._disp(lbl, self.here() + 4, 2, -128, 127) & 0xFF))

    def bf(self, lbl):
        self.w(0x8B00 | (self._disp(lbl, self.here() + 4, 2, -128, 127) & 0xFF))

    def bra(self, lbl):
        self.w(0xA000 | (self._disp(lbl, self.here() + 4, 2, -2048, 2047) & 0xFFF))

    def long(self, lbl, value):
        while self.here() % 4:
            self.w(0x0009)
        self.mark(lbl)
        self.w(value >> 16)
        self.w(value)

    def word(self, lbl, value):
        self.mark(lbl)
        self.w(value)

    def blob(self):
        return b"".join(x.to_bytes(2, "big") for x in self.out)


def _copy_raw(a):
    """r1 = source, r2 = target: copy 9 words (the JP loop), then rts."""
    a.w(0xE709)                  # mov #9,r7
    a.mark("RAW_LOOP")
    a.w(0x6015)                  # mov.w @r1+,r0
    a.w(0x2201)                  # mov.w r0,@r2
    a.w(0x7202)                  # add #2,r2
    a.w(0x4710)                  # dt r7
    a.bf("RAW_LOOP")
    a.w(0x000B)                  # rts
    a.w(0x0009)                  # (delay) nop


def _pack(a):
    """Pack while scanning; a tile outside the band restarts as a raw copy
    (it rewrites all 18 bytes, so the partial pack does not matter)."""
    a.movl_pc(1, "SRC")          # mov.l #NAME_HOME,r1
    a.movl_pc(2, "DST")          # mov.l #SAVE_NAME,r2
    a.movw_pc(5, "NEG")          # mov.w #-1264,r5
    a.w(0xE600 | BAND_SIZE)      # mov #85,r6
    a.w(0xE700 | LETTERS)        # mov #16,r7
    a.mark("PACK_LOOP")
    a.w(0x6015)                  # mov.w @r1+,r0
    a.w(0x88FF)                  # cmp/eq #-1,r0      ; FFFF (sign-extended)
    a.bt("PAD")
    a.w(0x305C)                  # add r5,r0          ; tile - 1264
    a.w(0x70FF)                  # add #-1,r0
    a.w(0x3062)                  # cmp/hs r6,r0       ; outside 1265..1349
    a.bt("RAW")
    a.w(0x7001)                  # add #1,r0          ; 1..85
    a.w(0x2200)                  # mov.b r0,@r2
    a.w(0x7201)                  # add #1,r2
    a.w(0x4710)                  # dt r7
    a.bf("PACK_LOOP")
    a.bra("MAGIC")
    a.w(0x0009)                  # (delay) nop
    a.mark("PAD")
    a.w(0xE000)                  # mov #0,r0
    a.mark("PAD_LOOP")
    a.w(0x2200)                  # mov.b r0,@r2
    a.w(0x7201)                  # add #1,r2
    a.w(0x4710)                  # dt r7
    a.bf("PAD_LOOP")
    a.mark("MAGIC")
    a.movw_pc(0, "MAGIC_W")      # mov.w #0xA55A,r0
    a.w(0x000B)                  # rts
    a.w(0x2201)                  # (delay) mov.w r0,@r2 ; word 8 = mark
    a.mark("RAW")
    a.movl_pc(1, "SRC")          # mov.l #NAME_HOME,r1  ; from the start
    a.movl_pc(2, "DST")          # mov.l #SAVE_NAME,r2
    _copy_raw(a)
    a.word("NEG", (-(BAND_LO - 1)) & 0xFFFF)
    a.word("MAGIC_W", MAGIC)
    a.long("SRC", NAME_HOME)
    a.long("DST", SAVE_NAME)


def _unpack(a):
    a.movl_pc(1, "SRC")          # mov.l #SAVE_NAME,r1
    a.movl_pc(2, "DST")          # mov.l #NAME_HOME,r2
    a.w(0x6313)                  # mov r1,r3
    a.w(0x7310)                  # add #16,r3
    a.w(0x6031)                  # mov.w @r3,r0       ; word 8
    a.movw_pc(4, "MAGIC_W")      # mov.w #0xA55A,r4
    a.w(0x3040)                  # cmp/eq r4,r0
    a.bf("RAW")
    a.movw_pc(5, "POS")          # mov.w #1264,r5
    a.w(0xE700 | LETTERS)        # mov #16,r7
    a.mark("LOOP")
    a.w(0x6014)                  # mov.b @r1+,r0
    a.w(0x600C)                  # extu.b r0,r0
    a.w(0x8800)                  # cmp/eq #0,r0       ; end of the letters
    a.bt("END")
    a.w(0x305C)                  # add r5,r0          ; byte + 1264 = tile
    a.w(0x2201)                  # mov.w r0,@r2
    a.w(0x7202)                  # add #2,r2
    a.w(0x4710)                  # dt r7
    a.bf("LOOP")
    a.mark("END")
    a.w(0xE0FF)                  # mov #-1,r0
    a.w(0x000B)                  # rts
    a.w(0x2201)                  # (delay) mov.w r0,@r2 ; FFFF terminator
    a.mark("RAW")
    _copy_raw(a)
    a.word("MAGIC_W", MAGIC)
    a.word("POS", BAND_LO - 1)
    a.long("SRC", SAVE_NAME)
    a.long("DST", NAME_HOME)


def _assemble(body):
    labels = {}
    first = _Asm(labels, False)
    body(first)
    second = _Asm(labels, True)
    body(second)
    return second.blob()


def pack_blob():
    blob = _assemble(_pack)
    assert len(blob) <= PACK_TILES * 32, len(blob)
    return blob


def unpack_blob():
    blob = _assemble(_unpack)
    assert len(blob) <= UNPACK_TILES * 32, len(blob)
    return blob


def _stub(cave_addr):
    return (bytes.fromhex("D002" "400B" "0009" "A005" "0009")
            + cave_addr.to_bytes(4, "big")
            + bytes.fromhex("0009" "0009" "0009"))


A0LANG_SAVE_NAME_PACK = {
    "A0LANG.BIN": [
        (GATHER_OFF, _stub(PACK_ADDR)),
        (SCATTER_OFF, _stub(UNPACK_ADDR)),
    ],
}

A0LANG_SAVE_NAME_PACK_JP_BASELINE = {
    GATHER_OFF: bytes.fromhex("e300e708d23ed13e691573013376229" "18ffa7202"),
    SCATTER_OFF: bytes.fromhex("e700e308d239d139691577013736229" "18ffa7202"),
}

assert all(len(b) == 20 for b in A0LANG_SAVE_NAME_PACK_JP_BASELINE.values())
assert all(len(chunk) == 20 for _, chunk in A0LANG_SAVE_NAME_PACK["A0LANG.BIN"])
