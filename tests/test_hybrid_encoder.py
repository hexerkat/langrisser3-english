#!/usr/bin/env python3
"""test_hybrid_encoder.py — bigram + 8px-standalone hybrid encoder (TDD).

════════════════════════════════════════════════════════════════════════════
RED STATE (2026-07-16): tools/hybrid_encoder.py does not exist. Ralf's spec
(branch font-hybrid-ui-bigram, after parking the full-hankaku conversion):

  "usar bigramas, mas garantir que o espaço em branco seja renderizado só
   quando necessário, e esse espaço em branco seja sempre no passo 8px.
   [...] só letras standalone e espaços standalone que serão de 8px.
   bigrams [letra,espaço] podem existir se no texto original foi
   [letra,espaço]; mas onde for letra standalone e '…', terá que ser
   letra 8px e '…' de 16px."
════════════════════════════════════════════════════════════════════════════

THE RULE — v0.7 greedy 2-by-2 pairing, but NO PHANTOM BLANK, ever:
  - two half-width chars (letters, or letter+space when the TEXT has the
    space) -> the bigram tile (16px, both chars real);
  - an odd/unpairable half-width char (letter, space, band punct) -> its
    HANKAKU BAND tile (8px step, narrow width class — the renderers this
    branch inherited from 21531e2 already dispatch by tile class);
  - '…' and every non-band char -> zenkaku single (16px), as always;
  - control codes / [diehardt's name] pass through.

WIDTH IDENTITY: half-width chars cost 1 unit each (pair = 2 units for 2
chars, band tile = 1 unit), zenkaku = 2 — exactly the per-glyph hankaku
cost. Existing <$FFFC> breaks, the 34/26 balloon budgets and layout QA
are unchanged by construction.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / 'tools'))

import font_tools as ft                    # noqa: E402

try:
    from hybrid_encoder import encode_hybrid
    PRESENT, ERR = True, None
except Exception as exc:                   # noqa: BLE001
    PRESENT, ERR = False, exc

H = ft.HANKAKU_TILE_MAP
# Synthetic pair map for the unit tests (deterministic, corpus-independent);
# the property sweep below uses the real data-driven BIGRAM_TILE_MAP.
B = {('w', 'o'): 0x380, ('r', 'd'): 0x381, ('a', ' '): 0x382,
     ('b', 'c'): 0x383, ('h', 'i'): 0x384, ('a', 'b'): 0x385,
     ('c', 'd'): 0x386, ('s', ' '): 0x387, ('d', '.'): 0x388}


def words(raw):
    return [w for (w,) in struct.iter_unpack('>H', raw)]


def enc(text):
    return words(encode_hybrid(text, B))


def test_module_exists():
    assert PRESENT, f'RED: tools/hybrid_encoder.py not built ({ERR})'


@pytest.mark.skipif(not PRESENT, reason='module absent (RED)')
class TestPairing:

    def test_even_word_is_pure_bigrams(self):
        assert enc('word') == [B[('w', 'o')], B[('r', 'd')]]

    def test_odd_tail_is_a_band_tile_not_a_phantom_blank(self):
        out = enc('words')
        assert out == [B[('w', 'o')], B[('r', 'd')], H['s']]
        assert B[('s', ' ')] not in out, 'phantom (s,space) tile banned'

    def test_tail_before_ellipsis(self):
        """Ralf's example: standalone letter 8px + '…' 16px."""
        assert enc('words…') == [B[('w', 'o')], B[('r', 'd')], H['s'],
                                 ft.ELLIPSIS_TILE]

    def test_letter_space_bigram_when_text_has_the_space(self):
        # greedy from the left: (a,' ') is a REAL text pair -> 16px tile
        out = enc('a bc')
        assert out == [B[('a', ' ')], B[('b', 'c')]]

    def test_lone_trailing_space_is_the_8px_band_space(self):
        assert enc('hi ') == [B[('h', 'i')], H[' ']]

    def test_lone_space_never_uses_the_16px_blank(self):
        out = enc('hi ')
        assert 0 not in out, 'tile 0 (16px full-width blank) is banned'

    def test_ellipsis_is_zenkaku(self):
        assert enc('…') == [ft.ELLIPSIS_TILE]
        assert enc('...') == [ft.ELLIPSIS_TILE]

    def test_zenkaku_singles_pass_through(self):
        # '•' has no band tile -> zenkaku single (16px), like today
        assert enc('•') == [ft.CHAR_TILE_MAP['•']]

    def test_control_codes_pass_through(self):
        assert enc('<$FFFC>') == [0xFFFC]
        assert enc('ab<$FFFC>cd') == [B[('a', 'b')], 0xFFFC, B[('c', 'd')]]

    def test_player_name_token(self):
        assert enc("[diehardt's name]") == [0xF600, 0x0000]

    def test_ctrl_codes_break_pairing(self):
        # 'a' left alone by the ctrl boundary -> band tile, never (a,space)
        out = enc('a<$FFFC>b')
        assert out == [H['a'], 0xFFFC, H['b']]


@pytest.mark.skipif(not PRESENT, reason='module absent (RED)')
class TestWidthIdentity:
    """Hybrid unit cost == per-glyph hankaku unit cost, by construction."""

    CASES = ['word', 'words', 'a bc', 'hi there', 'It is no use...',
             'Enemy Cavalry Unit', "Freya's Level"]
    # width identity must hold for ANY map — use the real one here
    MAP = ft.BIGRAM_TILE_MAP

    @staticmethod
    def _units(tiles):
        n = 0
        for t in tiles:
            if t in (0xF600, 0x0000):        # token pair, not width
                continue
            n += 1 if ft.HANKAKU_BASE <= t <= 1349 else 2
        return n

    def test_unit_cost_equals_char_count(self):
        from hankaku_encoder import encode_hankaku
        for text in self.CASES:
            hy = self._units(words(encode_hybrid(text, self.MAP)))
            hk = self._units(words(encode_hankaku(text)))
            assert hy == hk, (
                f'{text!r}: hybrid {hy} units vs hankaku {hk} — the FFFC '
                'breaks and balloon budgets must not move')


@pytest.mark.skipif(not PRESENT, reason='module absent (RED)')
class TestNoPhantomBlankProperty:
    """Sweep real script lines: the encoder must never emit a (c,space)
    bigram unless the source text has that space."""

    def test_sample_scen_lines(self):
        import re
        esc = re.compile(r"<\$[0-9A-Fa-f]*>|\[[^\]]*\]")
        rev = {t: p for p, t in ft.BIGRAM_TILE_MAP.items()}
        f = PROJECT / 'scripts' / 'en' / 'scen001E.txt'
        lines = [l for l in f.read_text(encoding='utf-8').splitlines()
                 if l.strip()][:80]
        for line in lines:
            visible = esc.sub('', line).replace('...', '…')
            out = words(encode_hybrid(line, ft.BIGRAM_TILE_MAP))
            # reconstruct: every emitted tile maps back to its chars
            rebuilt = []
            for t in out:
                if t in (0xF600,):
                    rebuilt.append('￹')   # name token marker
                elif t == 0x0000 or t >= 0xF000:
                    continue   # token tail / structural codes / tile-0 blank
                elif ft.HANKAKU_BASE <= t <= 1349:
                    inv = {v: k for k, v in H.items()}
                    rebuilt.append(inv[t])
                elif t in rev:
                    rebuilt.append(''.join(rev[t]))
                elif t == ft.ELLIPSIS_TILE:
                    rebuilt.append('…')
                else:
                    ch = ft.TILE_CHAR_MAP.get(t)
                    rebuilt.append(ch if ch else '')
            got = ''.join(rebuilt)
            want = re.sub(r"<\$[0-9A-Fa-f]*>", '', line)
            want = re.sub(r"\[[^\]]*\]", '￹', want).replace('...', '…')
            # drop chars the encoder legitimately drops
            want = ''.join(c for c in want if (c in H or c == '￹'
                                               or c in ft.CHAR_TILE_MAP or c == '…'))
            assert got == want, (
                f'{line[:40]!r}: rebuilt {got[:40]!r} != source '
                f'{want[:40]!r} — a phantom or lost char')


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
