"""test_font_tools_no_cwx_attribution.py — no third-party font attribution.

Ralf 2026-07-07: "a arte atual não é herdada do CWX, nada é do CWX; 0.2 É do
CWX — se existe alguma menção no font_tools está errado. Mudamos o font para
Eagle desde a versão 0.6." The glyph art shipped since v0.6 is OUR Eagle III
re-rasterization (the old hand-drawn blobs were deleted); only the legacy
TILE LAYOUT (indices/ranges like 1500-1620) predates the rebuild. font_tools
comments must not attribute the font/art to "0.2 patch" or CWX.

Red state: font_tools.py carried ~40 "0.2 patch"/"0.2-patch" mentions (an old
mechanical rename left nonsense like "0.2 patch's v0.2 translation patch,
which 0.2 patch adopted").
"""
import re
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def test_font_tools_has_no_cwx_or_02patch_attribution():
    src = (PROJECT / "tools/font_tools.py").read_text(encoding="utf-8")
    offenders = [
        (i + 1, line.strip())
        for i, line in enumerate(src.splitlines())
        if re.search(r"0\.2[- ]patch|\bCWX\b|\bcwx\b", line)
    ]
    assert not offenders, (
        f"{len(offenders)} lines still attribute the font to 0.2/CWX: "
        f"{offenders[:5]}")
