"""test_layout_qa_hankaku_units.py — layout QA counts mixed 8/16px steps (TDD).

v0.8 width classes (branch font-hankaku-per-glyph): the balloon renderer now
steps per glyph — hankaku band tile = 1 column (8px), ANY other drawable tile
= 2 columns (16px, drawn by the zenkaku dispatch cave). Line budgets are in
8px COLUMNS: narration 34, dialogue 26 (= the old 17/13 tile budgets x2).

Bigram entries keep the old tile arithmetic (1 tile = 2 columns, budgets
17/13 — same maths, nothing changes). But entries ROUTED THROUGH THE HANKAKU
ENCODER (d00_tools routing, today the scen001 spike line) are mixed: the QA
must count hankaku chars as 1 unit and zenkaku ('…' tile 906, `<$0000>`
full-width space, any non-band tile) as 2 units against a 2x-wide budget —
that is how WE keep control of line budgets during the incremental
conversion ("layout qa tem que ser esperto e saber contar o que é hankaku
(1) o que é zenkaku (2)", Ralf 2026-07-07).

Red state: iter_hankaku_units doesn't exist and simulate_entry measures a
hankaku-routed entry with the bigram iterator (wrong unit, wrong budget).
"""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

from layout_qa.parser import Entry, _terminator_of, _tokenize  # noqa: E402

# The real routed spike line (scripts/en/scen001E.txt entry): 3 explicit lines.
YOUTH = ("…Youth aspiring to knighthood,<$FFFC>…Young man who weaves history,"
         "<$FFFC>Open your eyes.<$FFFE>")

NARRATION_SPEC = {"name": "NARRATION_16X4", "width": 17, "max_lines": 4}


def _entry(raw, scen_id="scen001", index=18):
    segs = _tokenize(raw)
    return Entry(scen_id=scen_id, index=index, raw=raw,
                 terminator=_terminator_of(segs), segments=segs)


def test_iter_hankaku_units_costs():
    """hankaku char = 1 unit; '…' (zenkaku ellipsis 906) = 2 units."""
    from text_measure import iter_hankaku_units
    parts = list(iter_hankaku_units("…Youth aspiring to knighthood,"))
    assert parts[0] == ("…", 2)
    assert all(cost == 1 for _, cost in parts[1:])
    assert sum(c for _, c in parts) == 2 + len("Youth aspiring to knighthood,")
    # substring concat reproduces the source (word-wrap detection needs it)
    assert "".join(s for s, _ in parts) == "…Youth aspiring to knighthood,"


def test_iter_hankaku_units_matches_the_real_encoder():
    """Unit sum == what encode_hankaku actually emits (1/band, 2/zenkaku) —
    measure the real artifact, never a shadow."""
    import struct
    from hankaku_encoder import encode_hankaku
    from text_measure import iter_hankaku_units
    import font_tools as ft
    text = "…Youth aspiring to knighthood, 123!"
    data = encode_hankaku(text)
    codes = [struct.unpack_from(">H", data, k)[0] for k in range(0, len(data), 2)]
    band = set(ft.HANKAKU_TILE_MAP.values())
    real = sum(1 if c in band else 2 for c in codes if c < 0xF000)
    assert sum(c for _, c in iter_hankaku_units(text)) == real


def test_simulator_measures_routed_entry_in_units():
    """The routed spike entry passes clean: its longest line is 31 units
    (2 + 29) against the 34-unit narration budget."""
    from layout_qa.simulator import simulate_entry
    issues, usage = simulate_entry(_entry(YOUTH), NARRATION_SPEC)
    assert not [i for i in issues if i.severity == "error"], issues
    lines = usage.balloons[0]["lines"]
    assert lines[0]["tiles"] == 2 + len("Youth aspiring to knighthood,")
    assert abs(lines[0]["fillRatio"] - lines[0]["tiles"] / 34) < 1e-4


def test_simulator_flags_line_past_34_units():
    """35 units on one narration line (…=2 + 33 chars) must wrap -> error."""
    from layout_qa.simulator import simulate_entry
    long_line = "…Youth aspiring to knighthoodxxxx"      # 2 + 32 = 34 ok
    over_line = "…Youth aspiring to knighthoodxxxxx"     # 2 + 33 = 35 over
    ok = _entry(f"{long_line}<$FFFE>")
    over = _entry(f"{over_line}<$FFFE>")
    ok_issues, _ = simulate_entry(ok, NARRATION_SPEC)
    over_issues, _ = simulate_entry(over, NARRATION_SPEC)
    assert not [i for i in ok_issues
                if i.code == "implicit_wrap_without_fffc"]
    assert [i for i in over_issues
            if i.code == "implicit_wrap_without_fffc"], over_issues


def test_full_width_space_counts_two_units():
    """<$0000> renders as a 16px blank via the zenkaku class -> 2 units in a
    hankaku-routed entry (it was 0 in the bigram arithmetic)."""
    from layout_qa.simulator import simulate_entry
    raw = "…Youth aspiring<$0000>x<$FFFE>"
    _, usage = simulate_entry(_entry(raw), NARRATION_SPEC)
    line = usage.balloons[0]["lines"][0]
    assert line["tiles"] == 2 + len("Youth aspiring") + 2 + 1


def test_explicit_bigram_arithmetic_is_preserved():
    """v0.8 full conversion routes EVERYTHING hankaku, but the bigram tile
    arithmetic stays available behind hankaku=False (simulator mechanics
    tests + any future unrouted surface, e.g. PLOT)."""
    from layout_qa.simulator import simulate_entry
    raw = "…Youth aspiring to knighthood,<$FFFE>"
    entry = _entry(raw, scen_id="scen002", index=3)
    _, usage = simulate_entry(entry, NARRATION_SPEC, hankaku=False)
    line = usage.balloons[0]["lines"][0]
    # bigram: '…' 1 tile + "Youth aspiring to knighthood," greedily packed
    assert line["tiles"] <= 17
    assert abs(line["fillRatio"] - line["tiles"] / 17) < 1e-4
    # and the same entry auto-routes to unit measurement (full conversion)
    _, usage_auto = simulate_entry(entry, NARRATION_SPEC)
    auto_line = usage_auto.balloons[0]["lines"][0]
    assert auto_line["tiles"] == 2 + len("Youth aspiring to knighthood,")
