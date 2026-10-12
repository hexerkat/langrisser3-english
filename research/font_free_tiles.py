#!/usr/bin/env python3
"""Count the FONT.BIN tiles nothing uses: room for new code caves or data.

Conservative. A tile is free only if it is
  - not a value of any encoder map (CHAR, BIGRAM, HANKAKU, TWIN),
  - not preserved (engine-fixed / kept specials) and not in the v0.8 reserved
    band 1265..1434 (caves live there and are tracked by hand), and
  - never seen as a word of TEXT in the built D00 entries, FNT_SYS records,
    SYSWIN records or PLOT blocks (parsed with the project's own parsers, so
    offset tables do not count as text). Control codes are >= 0xF000 and
    never collide with tile ids.
Code caves and engine patches that point at a tile by number (mov #imm,
pool words) are NOT seen here: they live in the reserved band 1265..1434 or
in PRESERVED_TILES, both counted as used. Tiles below 0x80 are counted as
used too: engine code can draw them with a sign-safe `mov #imm8` and never
show up in text (tile 43, the 8px glue space, is one).
Reports free runs in the built track01 and how many bytes they give (32/tile).

  python3 research/font_free_tiles.py [--track build/.../track01.bin]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import font_tools as ft  # noqa: E402
from d00_tools import parse_d00  # noqa: E402
from fnt_sys_tools import parse_fnt_sys  # noqa: E402
from iso_tools import build_file_index, extract_file_data  # noqa: E402
from plot_tools import parse_plot  # noqa: E402
from syswin_tools import parse_syswin  # noqa: E402

TILE_BYTES = 32


def newest_track():
    tracks = sorted(ROOT.glob("build/*/track01.bin"), key=lambda p: p.stat().st_mtime)
    return tracks[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", type=Path)
    a = ap.parse_args()
    track = a.track or newest_track()
    img = bytearray(track.read_bytes())
    idx = build_file_index(img)
    font = extract_file_data(img, idx["LANG/FONT.BIN"].extent, idx["LANG/FONT.BIN"].size)
    ntiles = len(font) // TILE_BYTES

    used = set(ft.PRESERVED_TILES) | set(ft.V08_RESERVED_TILES) | set(range(0x80))
    for m in (ft.CHAR_TILE_MAP, ft.BIGRAM_TILE_MAP, ft.HANKAKU_TILE_MAP, ft.TWIN_TILE_MAP):
        used |= {v for v in m.values() if isinstance(v, int)}
    def get(name):
        e = idx[name]
        return extract_file_data(img, e.extent, e.size)

    def words(b):
        return {int.from_bytes(b[i:i + 2], "big") for i in range(0, len(b) - 1, 2)}

    seen = set()
    for sec in parse_d00(get("LANG/SCEN/D00.DAT")):
        for entry in sec.entries:
            seen |= words(entry)
    for pair in parse_fnt_sys(get("LANG/FNT_SYS.BIN")).pairs:
        for rec in pair.records:
            seen |= words(rec)
    for rec in parse_syswin(get("LANG/BATTLE/SYSWIN.BIN")).records:
        seen |= set(rec)
    for block in parse_plot(get("LANG/PLOT.DAT")):
        seen |= words(block.raw_bytes[4:])     # skip the FFF8xxxx header
    used |= seen

    free = [t for t in range(ntiles) if t not in used]
    runs, start = [], None
    for t in free + [None]:
        if start is None:
            start = prev = t
        elif t is not None and t == prev + 1:
            prev = t
        else:
            runs.append((start, prev))
            start = prev = t
    runs = [r for r in runs if r[0] is not None]
    print(f"{track.parent.name}: FONT.BIN {len(font)} B, {ntiles} tiles")
    print(f"free tiles: {len(free)} = {len(free) * TILE_BYTES} bytes, in {len(runs)} runs")
    for s, e in sorted(runs, key=lambda r: r[0] - r[1]):
        n = e - s + 1
        print(f"  {s:4d}..{e:4d}  {n:3d} tiles  {n * TILE_BYTES:5d} B  "
              f"LWRAM 0x{0x288000 + s * TILE_BYTES:08X}")
    reserved_free = sorted(set(ft.V08_RESERVED_TILES) - seen
                           - {v for m in (ft.HANKAKU_TILE_MAP, ft.TWIN_TILE_MAP) for v in m.values()})
    print(f"reserved band 1265..1434 not used by text or maps (caves/headroom, check by hand): "
          f"{reserved_free}")


if __name__ == "__main__":
    main()
