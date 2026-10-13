"""test_d00_offsets_jp_format.py — the D00 entry-offset table stays JP format.

Playtest bug 2026-10-09 (Ralf, scen002 map-mode objectives window): Victory
Conditions showed "Liffany", Defeat Conditions showed "na". The Piece D
"x2" table (stored offset = real/2) was read by the patched PROG_3 readers
only; PROG_5 has its own unpatched readers (0x0608E2E6 / 0x0608E334, the
objectives window, and 0x0608EF16, the F600 D00-reference expansion). They
read the halved offset and landed in the name entries at the section start.
The hybrid encoder keeps every section far below the u16 ceiling (largest,
scen124, ~39 KB), so the table goes back to the JP format and EVERY engine
reader in every binary works unmodified.

Red state: build with Piece D (stored offsets halved, PROG_3 readers
patched, scen002 #25 read raw = entry 1 "Liffany").
"""
import struct
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

PROG3_BASE = 0x06052800

# JP bytes of the five PROG_3 sites Piece D rewrote (the D00 table readers).
_PROG3_JP_READERS = {
    0x0606267E: "6193316c311c71046013017dd22b611d317c",
    0x060626B2: "6193316c311c71046013017d611d317c",
    0x06062B16: "611d319c311c71046013013dd216611d313c",
    0x0607F49C: "0603d570",
    0x0607F418: "2149311c710462226013012d611d",
}

from font_tools import NAKAGURO_TILE  # noqa: E402  `・`, the objectives bullet


def _built():
    from iso_tools import build_file_index, extract_file_data
    builds = list((PROJECT / "build").glob("*/track01.bin"))
    if not builds:
        pytest.skip("no build/*/track01.bin (run build.py first)")
    img = max(builds, key=lambda p: p.stat().st_mtime).read_bytes()
    idx = build_file_index(img)

    def grab(suffix):
        return next(extract_file_data(img, e.extent, e.size)
                    for p, e in idx.items() if p.upper().endswith(suffix))
    return grab


def _jp_reader_view(d00, sec):
    """What an UNPATCHED engine reader sees: base + u16 table[idx]."""
    ta = sec.text_area_offset
    n = sec.entry_count
    stored = [struct.unpack_from(">H", d00, ta + 6 + j * 2)[0] for j in range(n)]
    return ta, stored


def test_every_table_offset_is_the_real_entry_start():
    from d00_tools import parse_d00
    d00 = _built()("SCEN/D00.DAT")
    bad = []
    for sec in parse_d00(d00):
        ta, stored = _jp_reader_view(d00, sec)
        for j, entry in enumerate(sec.entries):
            got = d00[ta + stored[j]:ta + stored[j] + len(entry)]
            if got != entry:
                bad.append(f"sec{sec.index}#{j}")
    assert not bad, f"{len(bad)} entries unreachable by a JP reader: {bad[:8]}"


def test_scen002_objectives_read_as_objectives():
    """The playtest screen: scen002 #25/#26 must start `<$0000>・`."""
    from d00_tools import parse_d00
    d00 = _built()("SCEN/D00.DAT")
    sec = parse_d00(d00)[1]                      # scen002 = section 1
    ta, stored = _jp_reader_view(d00, sec)
    for j in (25, 26):
        head = struct.unpack_from(">HH", d00, ta + stored[j])
        assert head == (0x0000, NAKAGURO_TILE), (
            f"scen002 #{j} read by the JP reader starts {head}, "
            f"not <$0000>・ (the objectives line)")


def test_prog3_table_readers_are_jp():
    prog3 = _built()("LANG/PROG_3.BIN")
    for addr, jp_hex in _PROG3_JP_READERS.items():
        jp = bytes.fromhex(jp_hex)
        off = addr - PROG3_BASE
        assert prog3[off:off + len(jp)] == jp, f"PROG_3 0x{addr:08X} not JP"
