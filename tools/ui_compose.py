"""tools/ui_compose.py — rebuild the engine's COMPOSED UI lines and read them
back as text, from a built track01 (effective-behaviour QA).

Some on-screen lines are not one string: the engine glues records together at
runtime, with hardcoded glue tiles between them (SH-2 `mov #imm` writes). A
per-record check cannot see the junctions, so this module reproduces the
composers (RE 2026-10-08) and renders the resulting tile stream cell by cell
(8px cells) from the real FONT.BIN pixels:

  - narrow band tiles (the v0.8 8px step) draw ONE cell, every other tile two;
  - a cell is read back through the half-glyph alphabet (font_tools.HALF_GLYPHS),
    a blank cell is ' ', a few whole-tile glyphs (digits, the compact 's, the
    colon glue) have a fixed label.

Composers (all addresses are runtime, JP load bases):

  ITEM ACTION BOX  A0LANG FUN_0601299c -> measured by FUN_06012A98
      [item fntsys10] + glue(A0LANG file 0x49CB) + [fntsys1 rec14 Use | rec13 Equip]
      + [fntsys1 rec at byte index A0LANG file 0x4A75]
  UNIT SPLASH      A0LANG FUN_060128D8 -> measured by FUN_06012A98
      [fntsys1 rec77 Enemy | rec129 NPC] + [troop type fntsys7] + [fntsys1 rec63 Unit]
      (no engine glue at all: the records must carry their own spaces)
  EVENT MESSAGES   PROG_3 FUN_0607c430 (opcode switch)
      level  : [name] + glue(0x29DCF) + [fntsys3 rec24] + glue(0x29DE9) + digits + [rec0|rec29]
      item   : [name] + glue(0x2A0C3) + [item fntsys10] + [fntsys3 rec10]
      MP     : [fntsys3 rec20] + glue(0x29F83) + digits + [fntsys3 rec28]
"""
import struct

FNTSYS1, FNTSYS3, FNTSYS7, FNTSYS10, FNTSYS11 = 0, 2, 6, 9, 10   # FNT_SYS pairs
ENEMY, NPC, UNIT = 77, 129, 63                          # fntsys1 splash records
from width_class import is_narrow_tile                  # the ONE width rule
DIGIT_BASE = 7                                          # engine digits: value + 7
TERMINATOR = 0xFFFF


def _halves(tile_bytes: bytes) -> tuple[bytes, bytes]:
    """Split a 32-byte interleaved 16x16 tile into its left/right 8x16 cells."""
    return tile_bytes[0::2], tile_bytes[1::2]


class CellReader:
    """Reads tile streams back as text, one 8px cell at a time."""

    def __init__(self, font: bytes):
        import font_tools as ft
        self.font = font
        self.by_half = {}
        for ch, half in ft.HALF_GLYPHS.items():
            if ch != ' ':
                self.by_half.setdefault(bytes(half), ch)
        self.whole = {DIGIT_BASE + d: str(d) for d in range(10)}

    def tile_text(self, t: int) -> str:
        left, right = _halves(self.font[t * 32:(t + 1) * 32])
        if t in self.whole:
            return self.whole[t]
        cells = [left] if is_narrow_tile(t) else [left, right]
        out = []
        for c in cells:
            if not any(c):
                out.append(' ')
            else:
                out.append(self.by_half.get(bytes(c), _special(c)))
        return ''.join(out)

    def text(self, tiles) -> str:
        return ''.join(self.tile_text(t) for t in tiles)


def _special(cell: bytes) -> str:
    """Whole-cell glyphs outside the half alphabet: the compact possessive
    ('s drawn inside one 8px cell) and anything unknown."""
    rows = [b for b in cell]
    top = any(rows[2:6])       # apostrophe band
    body = any(rows[6:13])     # x-height band
    if top and body:
        return "'s"
    return '�'


def _record(fs, pair: int, index: int) -> list[int]:
    words = [w for (w,) in struct.iter_unpack('>H', fs.pairs[pair].records[index])]
    return words[:words.index(TERMINATOR)] if TERMINATOR in words else words


def _byte(blob: bytes, offset: int) -> int:
    return blob[offset]


def _digits(value: int) -> list[int]:
    return [DIGIT_BASE + int(c) for c in str(value)]


def item_action(fs, a0lang: bytes, item: int, use: bool) -> list[int]:
    verb = _record(fs, FNTSYS1, 14 if use else 13)
    tail = _record(fs, FNTSYS1, _byte(a0lang, 0x4A75) // 2)
    return _record(fs, FNTSYS10, item) + [_byte(a0lang, 0x49CB)] + verb + tail


def level_message(fs, prog3: bytes, name: int, value: int, up: bool = True) -> list[int]:
    return (_record(fs, FNTSYS11, name) + [_byte(prog3, 0x29DCF)]
            + _record(fs, FNTSYS3, 24) + [_byte(prog3, 0x29DE9)] + _digits(value)
            + _record(fs, FNTSYS3, 0 if up else 29))


def item_use_message(fs, prog3: bytes, name: int, item: int) -> list[int]:
    return (_record(fs, FNTSYS11, name) + [_byte(prog3, 0x2A0C3)]
            + _record(fs, FNTSYS10, item) + _record(fs, FNTSYS3, 10))


def mp_message(fs, prog3: bytes, value: int) -> list[int]:
    return (_record(fs, FNTSYS3, 20) + [_byte(prog3, 0x29F83)] + _digits(value)
            + _record(fs, FNTSYS3, 28))


def unit_splash(fs, troop: int, npc: bool = False) -> list[int]:
    return (_record(fs, FNTSYS1, NPC if npc else ENEMY)
            + _record(fs, FNTSYS7, troop) + _record(fs, FNTSYS1, UNIT))
