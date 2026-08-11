# research/ — exploration, not the build

Scripts here answered a question once: how the Chinese disc encodes its text, what
a Japanese binary holds, how a font tile actually looks. They are kept because the
answers may be needed again — not because the patch needs them.

**Nothing in `research/` is part of building the patch.** `build.py` and everything
under `tools/` are self-contained; the dependency arrow points one way only
(research may import the project's tools, never the reverse). `tests/test_repo_layout.py`
enforces that, so exploratory code can never break a build.

What lives here:

| Group | What it explored |
|---|---|
| `cn_*`, `extract_cn_files`, `dump_cn_*`, `build_cn_tile_map`, `build_trilateral_table` | The Chinese release: font decoding, tile mapping, JP/EN/CN comparison |
| `dump_jp_scripts`, `dump_en_scripts`, `jp_dumper`, `jp_text_dump`, `jp_tile_crack` | Pulling text tables out of the original binaries |
| `font_preview`, `font_visualize`, `font_dump_png`, `font_slot_audit`, `font_jbm_generate`, `fnt_sys_coverage` | Looking at glyphs and font-slot usage |
| `screenshot_decode`, `signature_compare`, `v06_handler_analyzer` | Reverse-engineering aids |
| `script_cleaner` | One-off encoding fixes for the old Akari Dawn script |

`data/` holds their output that is worth keeping (e.g. `cn_unmapped_ranking.txt`,
the ranking of Chinese entries by undecoded tiles).

Run them from the project root, e.g. `python3 research/font_preview.py`. Most expect
a Japanese disc image or an extracted binary and will tell you what they need.
