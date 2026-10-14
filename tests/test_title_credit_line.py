"""The title credit line is written by the build, from VERSION, over the JP logo.

Red state: title_dg2 read map cell bits 12/13 as flips and had no
apply_credit_line; the build pasted a hand-made 320x224 PNG of the whole logo
(assets/title_credit/title_credit_indexed.png) whose "0.7" never followed
VERSION (0.7.2).

Cell bits (proved 2026-10-13 against a Ymir dump: the title sky plane vs VDP2
VRAM 0x44000 and CRAM 0x500): 0-11 tile, 12-13 palette bank, 14 H flip,
15 V flip. The glyphs come from data/fonts/title_credit_atlas.json (DejaVu
Sans Bold 8 px with a 1 px outline, made by the separate
langrisser3-graphics-extractor repo); the build itself needs no Pillow.
"""
import os
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'tools'))

import title_dg2  # noqa: E402
from iso_tools import build_file_index, extract_file_data  # noqa: E402

JP_DIR = os.environ.get('LANG3_JP_DIR')
SAMPLE = 'English patch 9.9.9 / Hexerkat & RalfGuth • 2026'


def _title(img_path):
    img = Path(img_path).read_bytes()
    idx = build_file_index(img)
    e = idx['LANG/TITLE.DG2']
    return extract_file_data(img, e.extent, e.size)


@pytest.fixture(scope='module')
def jp():
    if not JP_DIR:
        pytest.skip('LANG3_JP_DIR not set')
    return _title(sorted(Path(JP_DIR).glob('*rack*01*.bin'))[0])


def _res(dg2, i):
    c = title_dg2.parse_container(dg2)
    r = c.resources[i]
    return dg2[r.offset:r.offset + r.size]


def _palette(dg2):
    r1 = _res(dg2, 1)
    return [struct.unpack_from('>H', r1, title_dg2.PALETTE_RES1_OFFSET + 2 * i)[0] for i in range(256)]


def _footer_pixels(dg2):
    """(x, y) -> palette index of the logo plane's footer, as VDP2 draws it."""
    grid = title_dg2.decode_logo_grid(dg2)
    res0 = _res(dg2, 0)
    px = {}
    for row in range(title_dg2.FOOTER_ROW_START, title_dg2.GRID_H):
        for col in range(title_dg2.GRID_W):
            t = grid.tile(row, col)
            if not t:
                continue
            hf, vf = grid.flips(row, col)
            for y in range(8):
                for x in range(8):
                    v = res0[t * 64 + (7 - y if vf else y) * 8 + (7 - x if hf else x)]
                    if v:
                        px[col * 8 + x, row * 8 + y] = v
    return px


def test_cell_bits():
    grid = title_dg2.LogoGrid([0] * (title_dg2.GRID_W * title_dg2.GRID_H))
    grid.cells[0], grid.cells[1], grid.cells[2] = 0x4005, 0x8005, 0x1005
    assert grid.flips(0, 0) == (True, False)
    assert grid.flips(0, 1) == (False, True)
    assert grid.flips(0, 2) == (False, False)
    assert grid.bank(0, 2) == 1 and grid.tile(0, 2) == 5


def test_logo_and_sky_untouched(jp):
    out = title_dg2.apply_credit_line(jp, SAMPLE)
    a, b = title_dg2.decode_logo_grid(jp), title_dg2.decode_logo_grid(out)
    top = title_dg2.FOOTER_ROW_START * title_dg2.GRID_W
    assert b.cells[:top] == a.cells[:top]
    r0a, r0b = _res(jp, 0), _res(out, 0)
    assert r0b[:len(r0a)] == r0a and (len(r0b) - len(r0a)) % 64 == 0      # append-only
    assert _res(out, 2) == _res(jp, 2) and _res(out, 3) == _res(jp, 3)    # GAME OVER
    sky_off = title_dg2.GRID_BASE + title_dg2.GRID_W * title_dg2.GRID_H * 2
    assert _res(out, 1)[sky_off:] == _res(jp, 1)[sky_off:]                # sky map


def test_palette_only_gains_the_credit_ramp(jp):
    a, b = _palette(jp), _palette(out := title_dg2.apply_credit_line(jp, SAMPLE))
    ramp = range(title_dg2.CREDIT_RAMP_BASE + 1, title_dg2.CREDIT_RAMP_BASE + 16)
    assert [b[i] for i in range(256) if i not in ramp] == [a[i] for i in range(256) if i not in ramp]
    assert b[title_dg2.CREDIT_RAMP_BASE + 15] == 0xFFFF            # fill: white (MSB set)
    assert len({b[i] for i in ramp}) > 8


def test_one_centered_line_ending_on_the_last_row(jp):
    px = _footer_pixels(title_dg2.apply_credit_line(jp, SAMPLE))
    xs, ys = [x for x, _ in px], [y for _, y in px]
    assert px and max(ys) == 223 and max(ys) - min(ys) < 14
    assert abs(min(xs) - (319 - max(xs))) <= 1
    assert set(px.values()) <= set(range(title_dg2.CREDIT_RAMP_BASE + 1, title_dg2.CREDIT_RAMP_BASE + 16))


def test_text_changes_the_line(jp):
    assert _footer_pixels(title_dg2.apply_credit_line(jp, SAMPLE)) != \
        _footer_pixels(title_dg2.apply_credit_line(jp, SAMPLE.replace('9.9.9', '0.7.2')))


def test_too_long_is_refused(jp):
    with pytest.raises(ValueError):
        title_dg2.apply_credit_line(jp, 'x' * 90)


def test_built_title_carries_the_version(jp):
    """What the player gets: the built disc's title = the JP title with the
    credit line naming the version in VERSION."""
    builds = list((REPO / 'build').glob('*/track01.bin'))
    if not builds:
        pytest.skip('no build/*/track01.bin (run build.py first)')
    built = _title(max(builds, key=lambda p: p.stat().st_mtime))
    version = (REPO / 'VERSION').read_text().strip()
    import build
    assert version in build.TITLE_CREDIT_TEXT.format(version=version)
    assert built == title_dg2.apply_credit_line(jp, build.TITLE_CREDIT_TEXT.format(version=version))
