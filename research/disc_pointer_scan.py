#!/usr/bin/env python3
"""Which files on the disc point into an address range?

Scans every file in the JP Track 01 for aligned big-endian u32 words whose
value falls in [LO, HI). SH-2 code reaches an address through a literal pool
(an aligned u32 next to the code) and data tables store aligned pointers, so
an empty result means no static reference anywhere on the disc. It cannot see
an address built at runtime (base + offset arithmetic), so a "free" verdict
still needs RAM dumps and an in-game canary.

  python3 research/disc_pointer_scan.py 0x254000 0x254400
  python3 research/disc_pointer_scan.py 0x254000 0x254400 --track build/.../track01.bin
  python3 research/disc_pointer_scan.py 0x06034D90 0x06034DA2 --context

Matches an address and its cache-through mirror both ways (0x0xxxxxxx and
0x2xxxxxxx), so 0x25C10000 and 0x05C10000 find each other.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from iso_tools import _find_jp_track, build_file_index, extract_file_data  # noqa: E402


def scan(track: Path, lo: int, hi: int):
    img = bytearray(track.read_bytes())
    idx = build_file_index(img)
    hits = {}
    for path, e in sorted(idx.items()):
        if e.is_dir or e.size < 4:
            continue
        data = extract_file_data(img, e.extent, e.size)
        for off in range(0, len(data) - 3, 4):
            v = int.from_bytes(data[off:off + 4], "big")
            if lo <= v < hi or lo <= (v & 0xDFFFFFFF) < hi or lo <= (v | 0x20000000) < hi:
                hits.setdefault(path, []).append((off, v))
    return len(idx), hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lo")
    ap.add_argument("hi")
    ap.add_argument("--track", help="Track 01 .bin (default: JP disc from $LANG3_JP_DIR)")
    ap.add_argument("--context", action="store_true", help="print each hit")
    a = ap.parse_args()
    lo, hi = int(a.lo, 16), int(a.hi, 16)
    track = Path(a.track) if a.track else _find_jp_track(Path(os.environ["LANG3_JP_DIR"]), 1)
    nfiles, hits = scan(track, lo, hi)
    print(f"scanned {nfiles} files of {track.name} for u32 in [0x{lo:08X}, 0x{hi:08X})")
    if not hits:
        print("  no aligned pointer into the range in any file")
    for path, lst in hits.items():
        print(f"  {path}: {len(lst)} hit(s)")
        if a.context:
            for off, v in lst:
                print(f"    file+0x{off:05X} -> 0x{v:08X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
