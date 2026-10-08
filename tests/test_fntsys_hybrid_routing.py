"""test_fntsys_hybrid_routing.py — FNT_SYS and SYSWIN ship hybrid-encoded.

Red state (2026-10-08): both still use the v0.7 encoder, so every odd word
tail before a record end carries the phantom (c, space) tile. Ralf's playtest:
"Rigüler Commander está com um espaço em branco no final".

End state: the same bigram encoder, the phantom replaced by the 8px band tile
(real-space pairs kept, so the file does not grow). Checked on the built
track01. The name-entry keyboard (fntsys14) is its own feature and keeps its
v0.8 swap.
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

FNT_SYS_CAP = 0xE400      # load slot 0x246000..0x254400 (RAM wall RE)
KEYBOARD_PAIR = 13


def _grab(suffix):
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)
    data = next((extract_file_data(img, e.extent, e.size)
                 for p, e in idx.items() if p.upper().endswith(suffix)), None)
    assert data is not None, suffix
    return data


def _words(raw):
    return [w for (w,) in struct.iter_unpack(">H", raw)]


def test_built_fnt_sys_records_are_hybrid():
    from fnt_sys_tools import parse_fnt_sys, _parse_script_records
    from hybrid_encoder import encode_hybrid
    import font_tools as ft

    data = _grab("LANG/FNT_SYS.BIN")
    assert len(data) <= FNT_SYS_CAP
    fs = parse_fnt_sys(data)
    bad, checked = [], 0
    for i in range(15):
        if i == KEYBOARD_PAIR:
            continue
        lines = _parse_script_records(PROJECT / "scripts" / "en" / f"fntsys{i + 1}E.txt")
        recs = fs.pairs[i].records
        assert len(recs) == len(lines), f"fntsys{i + 1}: record count"
        for n, (line, rec) in enumerate(zip(lines, recs)):
            want = encode_hybrid(line, ft.FNTSYS_BIGRAM_TILE_MAP)
            if not want.endswith(b"\xff\xff"):
                want += b"\xff\xff"
            if rec != want:
                bad.append((i + 1, n, line[:30]))
            checked += 1
    assert checked > 2400
    assert not bad, f"{len(bad)} records not hybrid, e.g. {bad[:5]}"


def test_rigueler_commander_has_no_phantom_tail():
    """The reported case, decoded from the shipped bytes."""
    from fnt_sys_tools import parse_fnt_sys, _parse_script_records
    import font_tools as ft

    fs = parse_fnt_sys(_grab("LANG/FNT_SYS.BIN"))
    lines = _parse_script_records(PROJECT / "scripts" / "en" / "fntsys11E.txt")
    n = lines.index("Rigüler Commander<$FFFF>")
    tiles = [t for t in _words(fs.pairs[10].records[n]) if t != 0xFFFF]
    assert tiles[-1] == ft.HANKAKU_TILE_MAP["r"]
    assert tiles[-2] == ft.FNTSYS_BIGRAM_TILE_MAP[("d", "e")]


def test_built_syswin_records_are_hybrid():
    from syswin_tools import parse_syswin
    from hybrid_encoder import encode_hybrid
    import font_tools as ft

    sw = parse_syswin(_grab("SYSWIN.BIN"))
    lines = (PROJECT / "scripts" / "en" / "syswinE.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(sw.records)
    bad = []
    for n, (line, rec) in enumerate(zip(lines, sw.records)):
        want = _words(encode_hybrid(line, ft.FNTSYS_BIGRAM_TILE_MAP)) if line.strip() else []
        if rec != want:
            bad.append((n, line))
    assert not bad, f"syswin records not hybrid: {bad[:5]}"
