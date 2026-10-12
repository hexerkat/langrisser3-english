#!/usr/bin/env python3
"""Read a Ymir memory dump by Saturn address.

A Ymir dump folder holds wram-hi.bin (HWRAM, 1 MiB at 0x06000000) and
wram-lo.bin (LWRAM, 1 MiB at 0x00200000). This maps both so RE scripts and
the command line can ask "what is at 0x0604EB68" in runtime terms.

  python3 research/saturn_ram.py DUMP ptr 0x0604EB68 [0x0604E9FC ...]
  python3 research/saturn_ram.py DUMP hex 0x06034D90 0x40
  python3 research/saturn_ram.py DUMP find 00110012FFFF
  python3 research/saturn_ram.py DUMP zeros 0x06034A50 0x06035000 [minlen]

DUMP is a folder with wram-hi.bin / wram-lo.bin. Ymir always writes its dump
to the root of ~/Jogos/emulacao/tools/ymir-dumps, so move each dump into its
own subfolder right away: the next dump overwrites the root (the 2026-07-15
name entry dump was lost that way). Known dumps: ymir-dumps/{jp,0.7,
font-hankaku-per-gliph} (scen005 battle, 2026-07-08), ymir-dumps/name-cap16/
{titulo,treatment} (2026-10-12, with VRAM), lang3_tests/dump1, dump2 (town).
"""
import sys
from pathlib import Path

DEFAULT_DUMP = Path.home() / "Jogos/emulacao/tools/ymir-dumps/name-cap16/titulo"
REGIONS = (("wram-hi.bin", 0x06000000), ("wram-lo.bin", 0x00200000))


class SaturnRam:
    def __init__(self, folder=DEFAULT_DUMP):
        self.folder = Path(folder)
        self.blocks = []
        for name, base in REGIONS:
            p = self.folder / name
            if p.exists():
                self.blocks.append((base, p.read_bytes()))
        if not self.blocks:
            raise FileNotFoundError(f"no wram dumps in {self.folder}")

    def _locate(self, addr, n=1):
        addr &= 0x0FFFFFFF          # cache-through mirror 0x2xxxxxxx -> same RAM
        if addr >= 0x06000000:
            addr = 0x06000000 | (addr & 0xFFFFF)
        for base, data in self.blocks:
            if base <= addr and addr + n <= base + len(data):
                return data, addr - base
        raise ValueError(f"0x{addr:08X} is not in a dumped RAM region")

    def read(self, addr, n):
        data, off = self._locate(addr, n)
        return data[off:off + n]

    def u16(self, addr):
        return int.from_bytes(self.read(addr, 2), "big")

    def u32(self, addr):
        return int.from_bytes(self.read(addr, 4), "big")

    def find(self, needle: bytes, step=1):
        for base, data in self.blocks:
            i = data.find(needle)
            while i >= 0:
                if i % step == 0:
                    yield base + i
                i = data.find(needle, i + 1)

    def zero_runs(self, lo, hi, minlen=34):
        data, off = self._locate(lo, hi - lo)
        run = None
        for i in range(hi - lo):
            if data[off + i] == 0:
                run = i if run is None else run
            else:
                if run is not None and i - run >= minlen:
                    yield lo + run, i - run
                run = None
        if run is not None and hi - lo - run >= minlen:
            yield lo + run, hi - lo - run


def _hexdump(ram, addr, n):
    raw = ram.read(addr, n)
    for i in range(0, n, 16):
        chunk = raw[i:i + 16]
        print(f"  0x{addr + i:08X}: " + " ".join(f"{b:02X}" for b in chunk))


def main(argv):
    args = list(argv)
    folder = DEFAULT_DUMP
    if args and not args[0] in ("ptr", "hex", "find", "zeros"):
        folder = Path(args.pop(0))
    if not args:
        print(__doc__)
        return 2
    ram = SaturnRam(folder)
    cmd, rest = args[0], args[1:]
    if cmd == "ptr":
        for a in rest:
            v = ram.u32(int(a, 16))
            print(f"  [0x{int(a, 16):08X}] = 0x{v:08X}")
    elif cmd == "hex":
        _hexdump(ram, int(rest[0], 16), int(rest[1], 16) if len(rest) > 1 else 0x40)
    elif cmd == "find":
        for a in ram.find(bytes.fromhex(rest[0])):
            print(f"  0x{a:08X}")
    elif cmd == "zeros":
        minlen = int(rest[2]) if len(rest) > 2 else 34
        for a, n in ram.zero_runs(int(rest[0], 16), int(rest[1], 16), minlen):
            print(f"  0x{a:08X}  {n} zero bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
