"""test_repo_layout.py — where code lives, and what may depend on what.

RED STATE (2026-08-11): `tools/` held 84 scripts side by side — the 39
the build actually reaches, ~10 editorial/QA tools used while authoring
the translation, and 35 pieces of archaeology (Chinese-disc exploration,
ISO dumpers, font previews, RE probes). Nothing told a reader, or a
fork, which was which.

GREEN: archaeology moves to `research/`. `tools/` keeps the build plus
the living editorial workflow. The dependency arrow is one-way —
research may read the project's tools, never the reverse — so the build
can never be broken by exploratory code.
"""

import ast
import py_compile
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
RESEARCH = PROJ / 'research'

# The archaeology, pinned by name: Chinese-disc exploration, ISO/text
# dumpers, font preview & audit probes, RE helpers, and the encoding
# fixer for the old Akari Dawn script.
RESEARCH_TOOLS = {
    'build_cn_tile_map', 'build_trilateral_table', 'cn_complete_seed',
    'cn_decoder_analysis', 'cn_denoise', 'cn_disasm_map', 'cn_font_render',
    'cn_font_render_lsb', 'cn_ocr_mosaic', 'cn_render_entry',
    'cn_render_unmapped', 'cn_seed_review', 'cn_seed_screenshots',
    'cn_used_tiles', 'cn_vram_hunt', 'dump_cn_en_pairs', 'dump_cn_extras',
    'dump_cn_prog4', 'dump_cn_scripts', 'dump_en_scripts', 'dump_jp_scripts',
    'extract_cn_files', 'fnt_sys_coverage', 'font_dump_png',
    'font_jbm_generate', 'font_preview', 'font_slot_audit', 'font_visualize',
    'jp_dumper', 'jp_text_dump', 'jp_tile_crack', 'screenshot_decode',
    'script_cleaner', 'signature_compare', 'v06_handler_analyzer',
}


def test_research_directory_holds_the_archaeology():
    assert RESEARCH.is_dir(), 'research/ does not exist'
    present = {p.stem for p in RESEARCH.glob('*.py')}
    assert RESEARCH_TOOLS <= present, (
        'missing from research/: ' + ', '.join(sorted(RESEARCH_TOOLS - present))
    )


def test_tools_no_longer_holds_the_archaeology():
    left = {p.stem for p in (PROJ / 'tools').glob('*.py')} & RESEARCH_TOOLS
    assert not left, 'still under tools/: ' + ', '.join(sorted(left))


def _module_names(source: str) -> set:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split('.')[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split('.')[0])
    return out


def test_the_build_never_depends_on_research():
    """One-way arrow: exploratory code can never break the build."""
    offenders = []
    for path in [PROJ / 'build.py', *(PROJ / 'tools').rglob('*.py')]:
        src = path.read_text(encoding='utf-8')
        if 'research' in _module_names(src) or 'research/' in src:
            offenders.append(str(path.relative_to(PROJ)))
    assert not offenders, 'build-side code referencing research/:\n' + '\n'.join(offenders)


@pytest.mark.parametrize('path', sorted(RESEARCH.glob('*.py')) if RESEARCH.is_dir() else [])
def test_research_scripts_still_compile(path, tmp_path):
    """Moving must not silently break them — they stay runnable."""
    py_compile.compile(str(path), cfile=str(tmp_path / 'out.pyc'), doraise=True)


def test_research_scripts_can_reach_the_tools_they_import():
    """RED: two scripts imported a `tools/` neighbour by relying on
    living in that directory — `extract_cn_files` inserted its own
    SCRIPT_DIR, `jp_dumper` leaned on the working directory. Moving
    them to research/ silently breaks the import at run time, which no
    other test would catch."""
    tools_mods = {p.stem for p in (PROJ / 'tools').glob('*.py')} | {'layout_qa'}
    broken = []
    for path in sorted(RESEARCH.glob('*.py')):
        src = path.read_text(encoding='utf-8')
        needed = _module_names(src) & tools_mods
        if not needed:
            continue
        if "'tools'" not in src and '"tools"' not in src:
            broken.append(f'{path.name}: imports {sorted(needed)} '
                          'without putting tools/ on sys.path')
    assert not broken, '\n'.join(broken)


def test_no_source_file_warns_on_parse():
    """RED: `prog4_field_box_geometry.py` drew an ASCII brace in a
    non-raw docstring, so every parse of the tree emitted
    `SyntaxWarning: invalid escape sequence '\\ '` — noise that trains
    the reader to ignore warnings."""
    import warnings
    offenders = []
    for path in sorted([*(PROJ / 'tools').rglob('*.py'),
                        *RESEARCH.glob('*.py'), PROJ / 'build.py']):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                ast.parse(path.read_text(encoding='utf-8'))
            except SyntaxError:
                continue
            for w in caught:
                offenders.append(f'{path.relative_to(PROJ)}: {w.message}')
    assert not offenders, '\n'.join(offenders)
