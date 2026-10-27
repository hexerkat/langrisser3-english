"""tools/font_style_eagle.py: the Eagle III font style (art of v0.6 to v0.8).

Mx437 CL Eagle III 8x16 (VileR pack, data/fonts/SOURCES.md), re-rasterized
and moved one row down (baseline row 12), with hand-tuned punctuation. These
bytes are the shipped v0.8 art moved here unchanged from tools/font_tools.py
(guard: tests/test_font_styles.py, font SHA-256 of the eagle style). Not
regenerated from the TTF: the hand tuning would be lost.

UMLAUTS_UPPER is None: font_tools composes A/O/U-diaeresis from the capital
plus dots, as it always did for this style.
"""

LETTERS = {
    'a': bytes.fromhex('000000000000780c7ccccccc76000000'),
    'b': bytes.fromhex('000000e060607c6666666676dc000000'),
    'c': bytes.fromhex('0000000000007cc6c0c0c0c67c000000'),
    'd': bytes.fromhex('0000001c0c0c7cccccccccdc76000000'),
    'e': bytes.fromhex('0000000000007cc6c6fec0c67c000000'),
    'f': bytes.fromhex('0000001c363230783030303078000000'),
    'g': bytes.fromhex('00000000000076cccccccccc7c0ccc78'),
    'h': bytes.fromhex('000000e060607c6666666666e6000000'),
    'i': bytes.fromhex('0000001818003818181818183c000000'),
    'j': bytes.fromhex('0000000606000e06060606060666663c'),
    'k': bytes.fromhex('000000e0606066666c786c66e6000000'),
    'l': bytes.fromhex('0000003818181818181818183c000000'),
    'm': bytes.fromhex('000000000000ecfed6d6d6c6c6000000'),
    'n': bytes.fromhex('000000000000dc666666666666000000'),
    'o': bytes.fromhex('0000000000007cc6c6c6c6c67c000000'),
    'p': bytes.fromhex('000000000000dc66666666667c6060f0'),
    'q': bytes.fromhex('00000000000076cccccccccc7c0c0c1e'),
    'r': bytes.fromhex('000000000000dc7666606060f0000000'),
    's': bytes.fromhex('0000000000007cc6c07c06c67c000000'),
    't': bytes.fromhex('000000103030fc30303030361c000000'),
    'u': bytes.fromhex('000000000000cccccccccccc76000000'),
    'v': bytes.fromhex('000000000000c6c6c6c66c3810000000'),
    'w': bytes.fromhex('000000000000c6c6d6d6d6fe6c000000'),
    'x': bytes.fromhex('000000000000c6ee7c387ceec6000000'),
    'y': bytes.fromhex('000000000000c6c6c6c6c6c67e0c1870'),
    'z': bytes.fromhex('000000000000fe8c183060c2fe000000'),
    'A': bytes.fromhex('00000010387ceec6c6c6fec6c6000000'),
    'B': bytes.fromhex('000000fc6666667c66666666fc000000'),
    'C': bytes.fromhex('0000003c66c2c0c0c0c0c2663c000000'),
    'D': bytes.fromhex('000000f86c6666666666666cf8000000'),
    'E': bytes.fromhex('000000fe6662687868606266fe000000'),
    'F': bytes.fromhex('000000fe6662687868606060f0000000'),
    'G': bytes.fromhex('0000003c66c2c0c0cec6c66e3a000000'),
    'H': bytes.fromhex('000000c6c6c6c6fec6c6c6c6c6000000'),
    'I': bytes.fromhex('0000003c18181818181818183c000000'),
    'J': bytes.fromhex('0000001e0c0c0c0c0ccccccc78000000'),
    'K': bytes.fromhex('000000e6666c6c786c6c6666e6000000'),
    'L': bytes.fromhex('000000f06060606060606266fe000000'),
    'M': bytes.fromhex('000000c6eefefed6d6d6c6c6c6000000'),
    'N': bytes.fromhex('000000c6e6e6f6f6dedececec6000000'),
    'O': bytes.fromhex('0000007cc6c6c6c6c6c6c6c67c000000'),
    'P': bytes.fromhex('000000fc666666667c606060f0000000'),
    'Q': bytes.fromhex('000000386cc6c6c6c6c6de7e3c0c0e00'),
    'R': bytes.fromhex('000000fc666666667c6c6666f6000000'),
    'S': bytes.fromhex('0000007cc6c6c0701c06c6c67c000000'),
    'T': bytes.fromhex('0000007e7e5a1818181818183c000000'),
    'U': bytes.fromhex('000000c6c6c6c6c6c6c6c6c67c000000'),
    'V': bytes.fromhex('000000c6c6c6c6c6c6c67c3810000000'),
    'W': bytes.fromhex('000000c6c6c6d6d6d6d6fe6c6c000000'),
    'X': bytes.fromhex('000000c6c66c6c38386c6cc6c6000000'),
    'Y': bytes.fromhex('000000666666667e3c1818183c000000'),
    'Z': bytes.fromhex('000000fec6860c183060c2c6fe000000'),
}

DIGITS = {
    '0': bytes.fromhex('000000386cc6cedef6e6c66c38000000'),
    '1': bytes.fromhex('0000001838781818181818183c000000'),
    '2': bytes.fromhex('0000007cc6060c183060c6c6fe000000'),
    '3': bytes.fromhex('0000007e460c183c060606663c000000'),
    '4': bytes.fromhex('0000001c1c3c3c6c6cccfe0c1e000000'),
    '5': bytes.fromhex('000000fcc0c0f8cc060686cc78000000'),
    '6': bytes.fromhex('0000003c60c0f8ecc6c6c66c38000000'),
    '7': bytes.fromhex('000000fec6060c0c1818303030000000'),
    '8': bytes.fromhex('0000007cc6c6c67cc6c6c6c67c000000'),
    '9': bytes.fromhex('000000386cc6c6c66e3e060c78000000'),
}

PUNCT = {
    ':': bytes.fromhex('00000000000018180000001818000000'),
    ';': bytes.fromhex('00000000000018180000001818300000'),
    ',': bytes.fromhex('00000000000000000000001818300000'),
    '.': bytes.fromhex('00000000000000000000001818000000'),
    '?': bytes.fromhex('0000007cc6c60c0c1818001818000000'),
    '!': bytes.fromhex('000000183c3c3c181818001818000000'),
}

EXTRA_PUNCT = {
    '-': bytes.fromhex('00000000000000007e7e000000000000'),
    '+': bytes.fromhex('00000000000018187e7e181800000000'),
    '(': bytes.fromhex('00000c181830303030303018180c0000'),
    ')': bytes.fromhex('00003018180c0c0c0c0c0c1818300000'),
    '/': bytes.fromhex('00000006060c0c181830306060000000'),
    '*': bytes.fromhex('00001092543854921000000000000000'),
    '%': bytes.fromhex('000000e6a6ec0c181830376567000000'),
    '[': bytes.fromhex('0000003c30303030303030303c000000'),
    ']': bytes.fromhex('0000003c0c0c0c0c0c0c0c0c3c000000'),
    "'": bytes.fromhex('00000018183000000000000000000000'),
    '&': bytes.fromhex('000000386c6c3876dcdccccc76000000'),
}

UMLAUTS = {
    'ä': bytes.fromhex('000000cccc00780c7ccccccc76000000'),
    'ö': bytes.fromhex('000000c6c6007cc6c6c6c6c67c000000'),
    'ü': bytes.fromhex('000000cccc00cccccccccccc76000000'),
}

UMLAUTS_UPPER = None
