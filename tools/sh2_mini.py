"""tools/sh2_mini.py — tiny SH-2 interpreter for executing patch bytes in tests.

Runs REAL code bytes (JP baselines, our rewrites, our font caves) over a flat
big-endian memory, so a test can pin what the engine computes instead of what
a hand-written model says it computes. Only the instructions our text-path
patches use are implemented; anything else raises, so a patch that grows a new
opcode fails loudly instead of being mis-simulated.

Memory: `Sh2(mem)` where mem maps base address -> bytes (bytearray copies).
Calls: `call(entry, regs, stop=None)` runs from `entry` with PR = a sentinel
and returns when the code returns to it (or reaches `stop`).
"""

M32 = 0xFFFFFFFF
RETURN_SENTINEL = 0x0FFFFFF0
STACK_TOP = 0x060FFF00


def _sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class Sh2:

    def __init__(self, regions):
        self.regions = [(base, bytearray(data)) for base, data in regions.items()]
        self.regions.append((STACK_TOP - 0x1000, bytearray(0x1100)))
        self.R = [0] * 16
        self.T = 0
        self.PR = 0
        self.MACL = 0
        self.MACH = 0
        self.steps = 0

    # -- memory ---------------------------------------------------------------
    def _loc(self, addr):
        for base, data in self.regions:
            if base <= addr < base + len(data):
                return data, addr - base
        raise AssertionError(f'unmapped address 0x{addr:08X}')

    def rb(self, a):
        data, o = self._loc(a)
        return data[o]

    def rw(self, a):
        data, o = self._loc(a)
        return (data[o] << 8) | data[o + 1]

    def rl(self, a):
        return (self.rw(a) << 16) | self.rw(a + 2)

    def ww(self, a, v):
        data, o = self._loc(a)
        data[o], data[o + 1] = (v >> 8) & 0xFF, v & 0xFF

    def wl(self, a, v):
        self.ww(a, v >> 16)
        self.ww(a + 2, v)

    def wb(self, a, v):
        data, o = self._loc(a)
        data[o] = v & 0xFF

    # -- execution ------------------------------------------------------------
    def call(self, entry, regs=None, stop=None, max_steps=200000):
        self.R = [0] * 16
        for k, v in (regs or {}).items():
            self.R[k] = v & M32
        self.R[15] = STACK_TOP
        self.PR = RETURN_SENTINEL
        pc = entry
        while pc != RETURN_SENTINEL and pc != stop:
            self.steps += 1
            if self.steps > max_steps:
                raise AssertionError('runaway (bad branch?)')
            pc = self._step(pc)
        return self

    def _step(self, pc):
        w = self.rw(pc)
        hi = w >> 8
        if hi in (0x89, 0x8B):                                   # bt / bf
            taken = self.T == (1 if hi == 0x89 else 0)
            return pc + 4 + _sx(w & 0xFF, 8) * 2 if taken else pc + 2
        if hi in (0x8D, 0x8F):                                   # bt/s / bf/s
            taken = self.T == (1 if hi == 0x8D else 0)
            self._exec(pc + 2, pc + 2)
            return pc + 4 + _sx(w & 0xFF, 8) * 2 if taken else pc + 4
        if (w & 0xF000) == 0xA000:                               # bra
            self._exec(pc + 2, pc + 2)
            return pc + 4 + _sx(w & 0xFFF, 12) * 2
        if (w & 0xF000) == 0xB000:                               # bsr
            self.PR = pc + 4
            self._exec(pc + 2, pc + 2)
            return pc + 4 + _sx(w & 0xFFF, 12) * 2
        if (w & 0xF0FF) == 0x400B:                               # jsr @Rm
            target = self.R[(w >> 8) & 0xF]
            self.PR = pc + 4
            self._exec(pc + 2, pc + 2)
            return target
        if (w & 0xF0FF) == 0x402B:                               # jmp @Rm
            target = self.R[(w >> 8) & 0xF]
            self._exec(pc + 2, pc + 2)
            return target
        if w == 0x000B:                                          # rts
            target = self.PR
            self._exec(pc + 2, pc + 2)
            return target
        self._exec(pc, pc)
        return pc + 2

    def _exec(self, pc, at):
        R, w = self.R, self.rw(at)
        n, m = (w >> 8) & 0xF, (w >> 4) & 0xF
        top, low = w >> 12, w & 0xF
        if w == 0x0009:                                          # nop
            return
        if top == 0xE:                                           # mov #imm,Rn
            R[n] = _sx(w & 0xFF, 8) & M32
        elif top == 0x7:                                         # add #imm,Rn
            R[n] = (R[n] + _sx(w & 0xFF, 8)) & M32
        elif top == 0x9:                                         # mov.w @(d,PC)
            R[n] = _sx(self.rw(at + 4 + (w & 0xFF) * 2), 16) & M32
        elif top == 0xD:                                         # mov.l @(d,PC)
            R[n] = self.rl(((at + 4) & ~3) + (w & 0xFF) * 4)
        elif (w & 0xFF00) == 0xC700:                             # mova @(d,PC),r0
            R[0] = (((at + 4) & ~3) + (w & 0xFF) * 4) & M32
        elif top == 0x0 and (w & 0xFF) == 0x29:                  # movt Rn
            R[n] = self.T
        elif (w & 0xFF00) == 0x8800:                             # cmp/eq #imm,r0
            self.T = int(R[0] == (_sx(w & 0xFF, 8) & M32))
        elif top == 0x0 and low == 0x7:                         # mul.l Rm,Rn
            self.MACL = (R[n] * R[m]) & M32
        elif top == 0x0 and (w & 0xFF) == 0x1A:                  # sts macl,Rn
            R[n] = self.MACL
        elif top == 0x0 and (w & 0xFF) == 0x0A:                  # sts mach,Rn
            R[n] = self.MACH
        elif top == 0x0 and low == 0x4:                          # mov.b Rm,@(r0,Rn)
            self.wb((R[0] + R[n]) & M32, R[m])
        elif top == 0x0 and low == 0xD:                          # mov.w @(r0,Rm),Rn
            R[n] = _sx(self.rw((R[0] + R[m]) & M32), 16) & M32
        elif top == 0x0 and low == 0xC:                          # mov.b @(r0,Rm),Rn
            R[n] = _sx(self.rb((R[0] + R[m]) & M32), 8) & M32
        elif top == 0x0 and low == 0x5:                          # mov.w Rm,@(r0,Rn)
            self.ww((R[0] + R[n]) & M32, R[m])
        elif top == 0x6:
            if low == 0x0:
                R[n] = _sx(self.rb(R[m]), 8) & M32               # mov.b @Rm
            elif low == 0x4:                                     # mov.b @Rm+
                R[n] = _sx(self.rb(R[m]), 8) & M32
                if n != m:
                    R[m] = (R[m] + 1) & M32
            elif low == 0x3:
                R[n] = R[m]                                      # mov
            elif low == 0x1:
                R[n] = _sx(self.rw(R[m]), 16) & M32              # mov.w @Rm
            elif low == 0x5:                                     # mov.w @Rm+
                R[n] = _sx(self.rw(R[m]), 16) & M32
                if n != m:
                    R[m] = (R[m] + 2) & M32
            elif low == 0x2:
                R[n] = self.rl(R[m])                             # mov.l @Rm
            elif low == 0x6:                                     # mov.l @Rm+
                R[n] = self.rl(R[m])
                if n != m:
                    R[m] = (R[m] + 4) & M32
            elif low == 0xD:
                R[n] = R[m] & 0xFFFF                             # extu.w
            elif low == 0xC:
                R[n] = R[m] & 0xFF                               # extu.b
            elif low == 0xF:
                R[n] = _sx(R[m] & 0xFFFF, 16) & M32              # exts.w
            elif low == 0xE:
                R[n] = _sx(R[m] & 0xFF, 8) & M32                 # exts.b
            elif low == 0x7:
                R[n] = ~R[m] & M32                               # not
            elif low == 0xB:
                R[n] = -R[m] & M32                               # neg
            else:
                raise AssertionError(f'unimplemented {w:04X} @0x{at:X}')
        elif top == 0x1:                                         # mov.l Rm,@(d,Rn)
            self.wl((R[n] + low * 4) & M32, R[m])
        elif top == 0x5:                                         # mov.l @(d,Rm),Rn
            R[n] = self.rl((R[m] + low * 4) & M32)
        elif top == 0x2:
            if low == 0x1:
                self.ww(R[n], R[m])                              # mov.w Rm,@Rn
            elif low == 0x2:
                self.wl(R[n], R[m])                              # mov.l Rm,@Rn
            elif low == 0x6:                                     # mov.l Rm,@-Rn
                R[n] = (R[n] - 4) & M32
                self.wl(R[n], R[m])
            elif low == 0x0:
                self.wb(R[n], R[m])                              # mov.b Rm,@Rn
            elif low == 0x8:
                self.T = int((R[n] & R[m]) == 0)                 # tst Rm,Rn
            elif low == 0xB:
                R[n] = R[n] | R[m]                               # or Rm,Rn
            elif low == 0x9:
                R[n] = R[n] & R[m]                               # and Rm,Rn
            else:
                raise AssertionError(f'unimplemented {w:04X} @0x{at:X}')
        elif top == 0x3:
            if low == 0xC:
                R[n] = (R[n] + R[m]) & M32                       # add
            elif low == 0x8:
                R[n] = (R[n] - R[m]) & M32                       # sub
            elif low == 0x5:                                     # dmulu.l
                prod = R[n] * R[m]
                self.MACH, self.MACL = prod >> 32, prod & M32
            elif low == 0x0:
                self.T = int(R[n] == R[m])                       # cmp/eq
            elif low == 0x6:
                self.T = int(R[n] > R[m])                        # cmp/hi
            elif low == 0x2:
                self.T = int(R[n] >= R[m])                       # cmp/hs
            elif low == 0x3:
                self.T = int(_sx(R[n], 32) >= _sx(R[m], 32))     # cmp/ge
            elif low == 0x7:
                self.T = int(_sx(R[n], 32) > _sx(R[m], 32))      # cmp/gt
            else:
                raise AssertionError(f'unimplemented {w:04X} @0x{at:X}')
        elif top == 0x4:
            lo8 = w & 0xFF
            if lo8 == 0x00:
                R[n] = (R[n] << 1) & M32                         # shll
            elif lo8 == 0x08:
                R[n] = (R[n] << 2) & M32                         # shll2
            elif lo8 == 0x18:
                R[n] = (R[n] << 8) & M32                         # shll8
            elif lo8 == 0x01:
                self.T, R[n] = R[n] & 1, R[n] >> 1               # shlr
            elif lo8 == 0x09:
                R[n] = R[n] >> 2                                 # shlr2
            elif lo8 == 0x10:
                R[n] = (R[n] - 1) & M32                          # dt
                self.T = int(R[n] == 0)
            elif lo8 == 0x22:
                R[n] = (R[n] - 4) & M32                          # sts.l pr,@-Rn
                self.wl(R[n], self.PR)
            elif lo8 == 0x26:
                self.PR = self.rl(R[n])                          # lds.l @Rn+,pr
                R[n] = (R[n] + 4) & M32
            else:
                raise AssertionError(f'unimplemented {w:04X} @0x{at:X}')
        else:
            raise AssertionError(f'unimplemented {w:04X} @0x{at:X}')
