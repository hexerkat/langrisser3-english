"""test_objectives_bullet_indent.py — objectives diagramming lock (TDD).

Ralf 2026-07-08 (corrected twice): every objectives bullet line renders
`<$0000>・text` — full-width blank (16px) + the JP NAKAGURO full-width bullet
(16px, rehomed glyph at font_tools.NAKAGURO_TILE) + text directly. A wrapped
bullet item's continuation line starts `<$0000><$0000>` (2 blanks = the same
32px), so the item text aligns like an indent. Only some screens had this
layout; the rest drifted across 4 styles (bare bullet, ASCII space, single
<$0000>, ideographic space) and used the small `•`.

Red state: 208 bare bullets + mixed continuation indents across 78 scen
scripts.
"""
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SCRIPTS = PROJECT / "scripts" / "en"

_SPLIT = re.compile(r"<\$FFFC>|<\$FFFD>")
_TERM = ("<$FFFE>", "<$FFFF>")


def _segments(line):
    return _SPLIT.split(line)


def _is_content(seg):
    s = seg
    for t in _TERM:
        s = s.replace(t, "")
    return bool(s.strip())


def test_every_bullet_is_blank_plus_nakaguro():
    offenders = []
    for f in sorted(SCRIPTS.glob("scen*E.txt")):
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "•" in line:                      # the small bullet is retired
                offenders.append(f"{f.name}:{ln} small-bullet")
            for m in re.finditer(r"(?<!<\$0000>)・", line):
                offenders.append(f"{f.name}:{ln} nakaguro-without-blank")
    assert not offenders, (
        f"{len(offenders)} objective bullet defects: {offenders[:8]}")


def test_bullet_continuations_are_double_blank_indented():
    """A non-empty segment following a bullet segment (same entry, not a
    header/bullet itself) must start with exactly <$0000><$0000>."""
    offenders = []
    for f in sorted(SCRIPTS.glob("scen*E.txt")):
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "・" not in line:
                continue
            segs = _segments(line)
            prev_was_item = False
            for seg in segs:
                if seg.startswith("<$0000>・"):
                    prev_was_item = True
                    continue
                if prev_was_item and _is_content(seg) and not seg.startswith("*"):
                    if not seg.startswith("<$0000><$0000>"):
                        offenders.append(f"{f.name}:{ln} {seg[:20]!r}")
                    # a continuation may itself continue further
                    prev_was_item = True
                else:
                    prev_was_item = False
    assert not offenders, (
        f"{len(offenders)} continuation lines lack <$0000><$0000>: {offenders[:8]}")
