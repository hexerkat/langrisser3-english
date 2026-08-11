"""test_script_naming_convention.py — one naming rule per language dir.

RED STATE (2026-08-11): `scripts/jp/` and `scripts/en/` name every file
`<base><LANG>.txt` with a single-letter language suffix — `scen001J.txt`,
`plotJ.txt`, `syswinE.txt`. `scripts/cn/` alone used a different shape,
`scen001_cn.txt` / `fnt_sys_cn.txt`, so the Chinese material read as a
foreign body rather than the third language of the same corpus (user,
2026-08-11: "os scripts CN deveriam ter o mesmo padrão dos JP e EN").

GREEN: the Chinese dumps carry the `C` suffix. `_unmapped_ranking.txt`
is not a script at all — it is decoding analysis, and lives under
`research/` with the tools that produced it.
"""

import re
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
SCRIPTS = PROJ / 'scripts'

SUFFIX = {'jp': 'J', 'en': 'E', 'cn': 'C'}

# Legacy Japanese-only exceptions: raw byte-scan dumps and PROG table
# extractions that predate the convention. Listed so the debt is
# visible; not extended.
LEGACY_JP = {
    '_scan_a0lang_JP.txt', '_scan_prog_3_JP.txt', '_scan_prog_4_JP.txt',
    '_scan_prog_5_JP.txt', '_scan_prog_6_JP.txt', '_scan_syswin_JP.txt',
    'prog3_magic_JP.txt', 'prog3_skill_JP.txt',
    'prog4_magic_icon_JP.txt', 'prog4_stat_name_JP.txt',
}


@pytest.mark.parametrize('lang', sorted(SUFFIX))
def test_every_script_carries_its_language_suffix(lang):
    d = SCRIPTS / lang
    if not d.is_dir():
        pytest.skip(f'{d} not present')
    pattern = re.compile(rf'^[A-Za-z0-9_]+{SUFFIX[lang]}\.txt$')
    bad = [p.name for p in sorted(d.glob('*.txt'))
           if not pattern.match(p.name) and p.name not in LEGACY_JP]
    assert not bad, f'scripts/{lang}/ off-convention: ' + ', '.join(bad)


def test_no_file_keeps_the_old_underscore_cn_shape():
    bad = [str(p.relative_to(PROJ)) for p in SCRIPTS.rglob('*_cn.txt')]
    assert not bad, 'legacy _cn naming: ' + ', '.join(bad)


def test_the_three_languages_cover_the_same_scenarios():
    """Renaming must not lose or duplicate a scenario file."""
    def scens(lang):
        return {p.name[4:7] for p in (SCRIPTS / lang).glob('scen*.txt')}
    assert scens('cn') <= scens('jp'), 'CN scens missing a JP counterpart'
    assert len(scens('cn')) == 125, f"expected 125 CN scens, found {len(scens('cn'))}"


def test_decoding_analysis_is_not_filed_as_a_script():
    stray = SCRIPTS / 'cn' / '_unmapped_ranking.txt'
    assert not stray.exists(), (
        f'{stray.relative_to(PROJ)} is analysis output, not a script — '
        'it belongs under research/'
    )
