"""tools/hybrid_encoder.py — bigram + 8px-standalone HYBRID encoder
(branch font-hybrid-ui-bigram, Ralf's spec 2026-07-16).

The inverse of the per-glyph hankaku path: text encodes v0.7-style — greedy
left-to-right BIGRAM pairing (16px tiles, 2 real chars each, spaces allowed
INSIDE pairs when the text has them) — but with ONE new rule:

    NO PHANTOM BLANK, EVER. A half-width char that cannot pair (odd word
    tail, char before '…'/a control code/end of line, a lone space) emits
    its HANKAKU BAND tile: 8px step, narrow width class, no blank right
    half. The 16px full-width blank (tile 0) never stands in for an ASCII
    space.

Why this works with zero engine change: the renderers and the measurer this
branch inherited (balloon_zenkaku_cave, a0lang_field_hankaku_step,
a0lang_label_box_width) dispatch width BY TILE CLASS — band [1265..NARROW_HI]
steps 1 cell, everything else 2. Width cost per half-width char is 1 unit in
both worlds (pair = 2 units / 2 chars), so <$FFFC> breaks, the 34/26 balloon
budgets and layout QA are unchanged by construction — and the drawn pixels
are near-identical to the per-glyph build (bigram art = the same half-glyphs
at columns 0/8).

Pass-through (same contract as encode_text_to_entry / encode_hankaku):
  - <$XXXX> escapes -> raw BE16 words (structural codes, never paired)
  - [diehardt's name] -> F600 0000
  - '...' / '…' -> the 16px ellipsis (zenkaku class) — Ralf's example:
    "letra standalone e '…' → letra 8px e … de 16px"
  - non-band chars -> CHAR_TILE_MAP zenkaku single (16px)
  - unsupported chars -> silently dropped (encoder-drop tricks keep working)
"""
import struct

from font_tools import CHAR_TILE_MAP, ELLIPSIS_TILE, HANKAKU_TILE_MAP


def encode_hybrid(text: str, bigram_tile_map: dict) -> bytes:
    out = bytearray()
    i = 0
    n = len(text)
    while i < n:
        # player-name token
        if text[i:].lower().startswith("[diehardt's name]"):
            out += struct.pack('>HH', 0xF600, 0x0000)
            i += 17
            continue
        # <$XXXX> escape sequence (one or more BE16 words)
        if text[i:i + 2] == '<$':
            end = text.find('>', i + 2)
            if end != -1:
                hex_str = text[i + 2:end].strip()
                try:
                    for j in range(0, len(hex_str), 4):
                        part = hex_str[j:j + 4].ljust(4, '0')
                        out += struct.pack('>H', int(part, 16))
                except ValueError:
                    pass
                i = end + 1
                continue
        # '...' / '…' -> 16px ellipsis (zenkaku class, 2 cells)
        if text[i:i + 3] == '...' or text[i] == '…':
            out += struct.pack('>H', ELLIPSIS_TILE)
            i += 3 if text[i:i + 3] == '...' else 1
            continue
        # greedy bigram: two real chars, spaces included when the text
        # has them — the blank inside a (x,' ') pair is REAL text. Tokens,
        # escapes and '…' never match (the map holds only half-glyph
        # pairs); the one real edge is a (c,'.') pair that would eat the
        # first dot of a '...' ellipsis.
        if i + 1 < n and (text[i], text[i + 1]) in bigram_tile_map \
                and text[i + 1:i + 4] != '...':
            out += struct.pack('>H', bigram_tile_map[(text[i], text[i + 1])])
            i += 2
            continue
        # standalone half-width char -> hankaku band tile (8px, no blank)
        ch = text[i]
        i += 1
        tile = HANKAKU_TILE_MAP.get(ch)
        if tile is None:
            tile = CHAR_TILE_MAP.get(ch)   # zenkaku single (16px)
        if tile is not None:
            out += struct.pack('>H', tile)
        # else: unsupported char -> dropped
    return bytes(out)
