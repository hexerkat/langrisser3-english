# Font sources

External font assets used by the build pipeline. All third-party fonts
listed here are used under their original licenses; this directory is the
canonical project location for them so anyone can reproduce the build
without hunting external URLs.

## Mx437_CL_EagleIII_8x16.ttf

- **Family**: Mx437 CL Eagle III 8x16
- **Variant**: Mx (mixed outline + embedded bitmap; the embedded bitmap is
  pulled when PIL rasterizes at SIZE=16 with mode `'1'` / FreeType
  `FT_LOAD_TARGET_MONO`).
- **Source pack**: VileR — *The Ultimate Oldschool PC Font Pack*, **v2.2**
- **Pack URL**: <https://int10h.org/oldschool-pc-fonts/download/>
- **Pack file fetched**: `oldschool_pc_font_pack_v2.2_linux.zip`
  (SHA256 `b30dc3ecc9931ad2dd8be7517dd01813c8834a1911b582ab7643191b41a3d759`)
- **Path inside zip**: `ttf - Mx (mixed outline+bitmap)/Mx437_CL_EagleIII_8x16.ttf`
- **TTF SHA256**: `2cd0c5dce071b8518fcf7b476cc32abc59a09636f9b09f748f00e86d8fc2dc9b`
- **TTF size**: 50,412 bytes (mtime 2020-11-21)
- **Original face origin**: Cirrus Logic CL-GD5320 video BIOS (v3.08), 8×16 ROM glyphs.
- **License**: CC BY-SA 4.0 (per VileR, "All fonts here are free for use under
  the CC BY-SA 4.0 license"). Attribution: VileR / int10h.org.

### How it is used

The **eagle** font style (`build.py --font eagle`, the font of v0.6 to v0.8).
Its 8x16 glyphs live in `tools/font_style_eagle.py` as `bytes.fromhex()`
literals: this TTF re-rasterized, moved one row down (baseline row 12), with
hand-tuned punctuation. The build does **not** import the TTF, and the bytes
are not regenerated from it (the hand tuning would be lost). The TTF itself
is read by `tools/movie_tools.py` to burn the opening movie subtitles of an
eagle build.

## Mx437_DOS-V_re_ANK16.ttf

- **Family**: Mx437 DOS/V re. ANK16 (VileR's re-creation of the IBM DOS/V
  Japanese half-width "ANK" font, 8x16).
- **Source pack**: VileR, *The Ultimate Oldschool PC Font Pack*, **v2.2**
  (same pack file and URL as above).
- **Path inside zip**: `ttf - Mx (mixed outline+bitmap)/Mx437_DOS-V_re_ANK16.ttf`
- **TTF SHA256**: `394a8f01ce2b1b64940b1a739b2a26f488432a63466915cbcf1334379d9e9ef8`
- **TTF size**: 53,972 bytes
- **License**: CC BY-SA 4.0. Attribution: VileR / int10h.org.
- **Why this face**: of the 361 faces in the pack, its letters and digits are
  the closest in shape to the Latin glyphs of the Japanese game's own font
  (thin strokes, no serifs). Chosen by the user on 2026-10-23.

### How it is used

The **dosv** font style, the default (`build.py --font dosv`).
`tools/font_style_generate.py dosv` (needs Pillow) rasterizes the embedded
8x16 bitmap and moves it one row up so its baseline sits on row 12, like the
eagle style. It writes `tools/font_style_dosv.py`, which the build reads
(standard library only). `tests/test_font_styles.py` checks that the stored
bytes are exactly what the generator draws from this TTF. The TTF itself is
read by `tools/movie_tools.py` to burn the opening movie subtitles of a dosv
build.

```bash
python3 tools/font_style_generate.py dosv > tools/font_style_dosv.py
```

## title_credit_atlas.json

- **Family**: DejaVu Sans Bold (`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`),
  8 px, +0.25 px tracking, white fill with a 1 px dark brown outline.
- **License**: Bitstream Vera / DejaVu license (free to use, modify and
  redistribute, including as bitmaps). Attribution: DejaVu fonts team.
- **Made by**: `scripts/build_credit_atlas.py` in the separate
  `langrisser3-graphics-extractor` repo (needs Pillow). Each glyph is stored as
  ramp levels 0 (transparent) .. 15 (fill); level 1 is the outline color.

### How it is used

`tools/title_dg2.apply_credit_line` draws `build.TITLE_CREDIT_TEXT` (with the
VERSION number) from this JSON into the empty footer of the JP title logo, and
writes the 15 ramp colors into title palette slots 17..31. The build needs no
Pillow and no TTF.
