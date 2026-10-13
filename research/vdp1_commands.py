#!/usr/bin/env python3
"""List the VDP1 command table of a Ymir dump, and dump sprite textures.

Each VDP1 command is 0x20 bytes at the start of VDP1 VRAM, chained by
CMDCTRL jump bits / CMDLINK, ending at a command with bit 15 (END) set.
For a normal/scaled/distorted sprite: texture at CMDSRCA*8, width
((CMDSIZE >> 8) & 0x3F) * 8, height CMDSIZE & 0xFF, color mode
(CMDPMOD >> 3) & 7 (0 = 4bpp bank, 1 = 4bpp LUT at CMDCOLR*8, 2..4 = 8bpp,
5 = 16bpp RGB).

  python3 research/vdp1_commands.py DUMP [--max 400]
  python3 research/vdp1_commands.py DUMP --texture IDX[,IDX...] --out DIR
        (writes each texture as a grayscale PGM: index values, not colors)
  python3 research/vdp1_commands.py DUMP --near X,Y,W,H
        (only commands whose top-left falls in that screen box)
"""
import argparse
from pathlib import Path

KIND = {0: "sprite", 1: "scaled", 2: "distorted", 4: "polygon", 5: "polyline",
        6: "line", 8: "user-clip", 9: "sys-clip", 10: "local-coord"}


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def commands(vram, limit=2000):
    out, addr, seen = [], 0, set()
    ret = None
    while len(out) < limit and addr not in seen and addr + 0x20 <= len(vram):
        seen.add(addr)
        w = [int.from_bytes(vram[addr + i:addr + i + 2], "big") for i in range(0, 0x20, 2)]
        ctrl, link = w[0], w[1]
        if ctrl & 0x8000:
            break
        jump = (ctrl >> 12) & 7
        kind = ctrl & 0xF
        if not (ctrl & 0x4000):                      # not skipped
            out.append({
                "addr": addr, "kind": KIND.get(kind, f"?{kind}"), "ctrl": ctrl,
                "pmod": w[2], "colr": w[3], "srca": w[4] * 8,
                "w": ((w[5] >> 8) & 0x3F) * 8, "h": w[5] & 0xFF,
                "x": s16(w[6]), "y": s16(w[7]), "mode": (w[2] >> 3) & 7,
            })
        nxt = addr + 0x20
        if jump in (1, 5):                           # jump assign
            nxt = link * 8
        elif jump in (2, 6):                         # call
            ret, nxt = addr + 0x20, link * 8
        elif jump in (3, 7) and ret is not None:     # return
            nxt, ret = ret, None
        addr = nxt
    return out


def texture(vram, c):
    w, h, base, mode = c["w"], c["h"], c["srca"], c["mode"]
    px = bytearray()
    if mode in (0, 1):
        for i in range(w * h // 2):
            b = vram[(base + i) & 0x7FFFF]
            px += bytes(((b >> 4) * 17, (b & 15) * 17))
    elif mode in (2, 3, 4):
        px = bytearray(vram[base:base + w * h])
    else:
        for i in range(w * h):
            v = int.from_bytes(vram[base + 2 * i:base + 2 * i + 2], "big")
            px.append((((v & 31) + ((v >> 5) & 31) + ((v >> 10) & 31)) * 255) // 93)
    return w, h, bytes(px[:w * h])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", type=Path)
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--near")
    ap.add_argument("--texture")
    ap.add_argument("--out", type=Path, default=Path("."))
    a = ap.parse_args()
    vram = (a.dump / "vdp1-vram.bin").read_bytes()
    cmds = commands(vram)
    if a.near:
        x0, y0, bw, bh = (int(v) for v in a.near.split(","))
        sel = [(i, c) for i, c in enumerate(cmds)
               if x0 <= c["x"] < x0 + bw and y0 <= c["y"] < y0 + bh]
    else:
        sel = list(enumerate(cmds))[:a.max]
    if a.texture:
        a.out.mkdir(parents=True, exist_ok=True)
        for i in (int(v) for v in a.texture.split(",")):
            w, h, px = texture(vram, cmds[i])
            p = a.out / f"tex{i:04d}_{cmds[i]['srca']:05X}_{w}x{h}.pgm"
            p.write_bytes(b"P5\n%d %d\n255\n" % (w, h) + px)
            print("wrote", p)
        return
    print(f"{len(cmds)} drawn commands")
    for i, c in sel:
        print(f"  #{i:4d} @{c['addr']:05X} {c['kind']:9} x={c['x']:4d} y={c['y']:4d} "
              f"{c['w']:3d}x{c['h']:<3d} mode={c['mode']} srca=0x{c['srca']:05X} "
              f"colr=0x{c['colr']:04X} pmod=0x{c['pmod']:04X}")


if __name__ == "__main__":
    main()
