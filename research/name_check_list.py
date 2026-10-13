#!/usr/bin/env python3
"""The names the JP name-entry check refuses, as the EN patch would see them.

RE (PROG_4 FUN_060923A8, 2026-10-12): pressing END compares the typed name
with FNT_SYS strings and refuses a match ("That name can't be used"):
  table 1 = pair 10 (fntsys11, character names), ids 1..0x17B, skipping
            0x28 and 0x30 (both "Diehärte", the default name; id 0 too)
  table 2 = pair 9 (fntsys10, item names), ids 13 and 14
The patch can only revive this with its own compare (the D00/FNT_SYS names
are bigram-encoded, the typed name is hankaku band tiles). This tool builds
the list such a compare would need and measures it.

A name the keyboard cannot type can never match, so it is dropped: the
keyboard has A-Z a-z 0-9 ! ? and space only, and names cap at MAX_LEN.

  python3 research/name_check_list.py [--max-len 16] [--fold-case] [--list]
"""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE1 = ("fntsys11E.txt", [i for i in range(1, 0x17C) if i not in (0x28, 0x30)])
TABLE2 = ("fntsys10E.txt", [13, 14])
KEYBOARD = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!? ")


def records(name):
    text = (ROOT / "scripts" / "en" / name).read_text(encoding="utf-8")
    return [line.replace("<$FFFF>", "") for line in text.split("\n")]


def checked_names():
    out = []
    for fname, ids in (TABLE1, TABLE2):
        recs = records(fname)
        out += [(fname, i, recs[i]) for i in ids]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-len", type=int, default=16)
    ap.add_argument("--fold-case", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    names = checked_names()
    typeable, dropped = [], []
    for f, i, n in names:
        if n and set(n) <= KEYBOARD and len(n) <= a.max_len:
            typeable.append(n.lower() if a.fold_case else n)
        else:
            dropped.append((f, i, n))
    unique = sorted(set(typeable))
    size = sum(len(n) + 1 for n in unique)      # 1 byte per letter + 0 terminator
    print(f"checked ids: {len(names)}  typeable: {len(typeable)}  unique: {len(unique)}")
    print(f"list size: {size} bytes (1 byte per letter, 0-terminated)")
    print(f"dropped (not typeable or > {a.max_len}): {len(dropped)}")
    for f, i, n in dropped:
        print(f"  {f} 0x{i:03X} {n!r}")
    if a.list:
        print("names:", ", ".join(unique))


if __name__ == "__main__":
    main()
