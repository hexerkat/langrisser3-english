#!/usr/bin/env python3
"""Guess where an SH-2 overlay is loaded, from its own pointers to functions.

Code calls its own functions through pool literals (jsr @rn). Only words a
`mov.l @(d,PC),Rn` actually loads are considered (PC-relative, so finding them
does not depend on the base); for the right base many of them point at a
function prologue inside the file (sts.l pr,@-r15 / mov.l rN,@-r15 /
mov r15,r14). Scores every base in [lo, hi) by that count.
Validated on PROG_3 (0x06052800), PROG_4 (0x06089000), A0LANG (0x0600E000).

  python3 research/guess_load_base.py FILE [--lo 0x06000000 --hi 0x06100000 --step 0x800]
"""
import argparse
from pathlib import Path

PROLOGUES = {0x4F22, 0x2FE6, 0x2FD6, 0x2FC6, 0x2FB6, 0x2FA6, 0x2F96, 0x2F86, 0x6EF3}


def pool_words(data):
    """Values loaded by mov.l @(d,PC) anywhere in the file (base 4-aligned)."""
    out = set()
    for pc in range(0, len(data) - 1, 2):
        op = int.from_bytes(data[pc:pc + 2], "big")
        if op >> 12 == 0xD:
            ea = (pc & ~3) + 4 + (op & 0xFF) * 4
            if ea + 4 <= len(data):
                out.add(int.from_bytes(data[ea:ea + 4], "big"))
    return out


def score(data, base, words):
    n = len(data)
    hits = 0
    for w in words:
        v = w - base
        if 0 <= v < n - 1 and v % 2 == 0 and int.from_bytes(data[v:v + 2], "big") in PROLOGUES:
            hits += 1
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--lo", default="0x06000000")
    ap.add_argument("--hi", default="0x06100000")
    ap.add_argument("--step", default="0x800")
    a = ap.parse_args()
    data = a.file.read_bytes()
    lo, hi, step = (int(x, 16) for x in (a.lo, a.hi, a.step))
    words = pool_words(data)
    ranked = sorted(((score(data, b, words), b) for b in range(lo, hi, step)), reverse=True)
    print(f"{a.file.name} ({len(data)} B): best bases by pointers-to-prologue")
    for s, b in ranked[:5]:
        print(f"  0x{b:08X}  {s}")


if __name__ == "__main__":
    main()
