"""tools/hankaku_encoder.py — per-glyph HANKAKU encoder (v0.8, branch
font-hankaku-per-glyph).

Encodes a text string as ONE 8px hankaku tile per character
(font_tools.HANKAKU_TILE_MAP), NO bigram packing. This is the prose path that,
paired with the 8px-stepped dialogue renderer (prog3_dialogue_hankaku_step),
renders per-glyph half-width text instead of 16px bigram tiles.

Pass-through (identical to d00_tools.encode_text_to_entry):
  - <$XXXX> escape sequences -> their raw BE16 code(s) (control / structural codes)
  - [diehardt's name]        -> F600 0000 (player-name token)
  - '...' / '…'              -> the 16px ellipsis tile 906 (zenkaku width class:
                                the balloon_zenkaku_cave dispatcher draws any
                                non-band tile full-width over 2 columns)
  - chars outside the band   -> CHAR_TILE_MAP zenkaku single (16px, 2 columns):
                                •, full-width SCENARIO letters, 　 -> tile 0
                                (the full-width blank), etc. — "alguns glifos
                                zenkaku" of the v0.8 full conversion
  - unsupported characters   -> silently dropped (the SAME drop set as the
                                bigram encoder: chars absent from CHAR_TILE_MAP
                                — encoder-drop layout tricks keep working)
"""
import struct

from font_tools import CHAR_TILE_MAP, ELLIPSIS_TILE, HANKAKU_TILE_MAP


def encode_hankaku(text: str) -> bytes:
    out = bytearray()
    i = 0
    n = len(text)
    while i < n:
        # player-name token
        if text[i:].lower().startswith("[diehardt's name]"):
            out += struct.pack(">HH", 0xF600, 0x0000)
            i += 17
            continue
        # <$XXXX> escape sequence (one or more BE16 words)
        if text[i:i + 2] == "<$":
            end = text.find(">", i + 2)
            if end != -1:
                hex_str = text[i + 2:end].strip()
                try:
                    for j in range(0, len(hex_str), 4):
                        part = hex_str[j:j + 4].ljust(4, "0")
                        out += struct.pack(">H", int(part, 16))
                except ValueError:
                    pass
                i = end + 1
                continue
        # '...' / '…' -> the 16px ellipsis (zenkaku class, 2 columns)
        if text[i:i + 3] == "..." or text[i] == "…":
            out += struct.pack(">H", ELLIPSIS_TILE)
            i += 3 if text[i:i + 3] == "..." else 1
            continue
        ch = text[i]
        i += 1
        tile = HANKAKU_TILE_MAP.get(ch)
        if tile is None:
            tile = CHAR_TILE_MAP.get(ch)   # zenkaku single (16px, 2 columns)
        if tile is not None:
            out += struct.pack(">H", tile)
        # else: unsupported char -> dropped
    return bytes(out)
