"""Opcodes tools/sh2_mini.py gained for the 16-letter name task (2026-10-12).

Red state: the interpreter raised `unimplemented` on these encodings, so the
tests that execute the JP name-entry append path (mul.l / sts macl for the
keyboard index, mov.b for the pos byte, R0-indexed mov.w for name[pos]) and
the save pack/unpack caves could not run. Each test pins the SH-2 manual
semantics of one opcode on a two-instruction program.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))

from sh2_mini import Sh2  # noqa: E402

CODE = 0x06000000
DATA = 0x06010000


def _run(words, regs, data=b''):
    prog = b''.join(w.to_bytes(2, 'big') for w in words + [0x000B, 0x0009])
    vm = Sh2({CODE: prog, DATA: bytearray(data) + bytearray(0x100)})
    vm.call(CODE, regs)
    return vm


class TestNewOpcodes(unittest.TestCase):

    def test_mov_b_at_rm_sign_extends(self):
        vm = _run([0x6120], {2: DATA}, b'\x85')          # mov.b @r2,r1
        self.assertEqual(vm.R[1], 0xFFFFFF85)

    def test_mov_b_at_rm_postinc(self):
        vm = _run([0x6124], {2: DATA}, b'\x05')          # mov.b @r2+,r1
        self.assertEqual((vm.R[1], vm.R[2]), (5, DATA + 1))

    def test_mul_l_and_sts_macl(self):
        vm = _run([0x0127, 0x031A], {1: 7, 2: 3})        # mul.l r2,r1; sts macl,r3
        self.assertEqual(vm.R[3], 21)

    def test_mov_w_r0_indexed_load_sign_extends(self):
        vm = _run([0x013D], {0: 2, 3: DATA}, b'\x00\x00\xff\xfe')  # mov.w @(r0,r3),r1
        self.assertEqual(vm.R[1], 0xFFFFFFFE)

    def test_mov_w_r0_indexed_store(self):
        vm = _run([0x0365], {0: 4, 3: DATA, 6: 0x1234})  # mov.w r6,@(r0,r3)
        self.assertEqual(vm.rw(DATA + 4), 0x1234)

    def test_mov_b_r0_indexed_load_sign_extends(self):
        """Name check task (2026-10-13): the case-fold table lookup."""
        vm = _run([0x013C], {0: 1, 3: DATA}, b'\x05\xff')  # mov.b @(r0,r3),r1
        self.assertEqual(vm.R[1], 0xFFFFFFFF)
        vm = _run([0x013C], {0: 0, 3: DATA}, b'\x05\xff')
        self.assertEqual(vm.R[1], 5)

    def test_tst_sets_t_when_and_is_zero(self):
        vm = _run([0x2128], {1: 0xF0, 2: 0x0F})          # tst r2,r1
        self.assertEqual(vm.T, 1)
        vm = _run([0x2128], {1: 0xF1, 2: 0x0F})
        self.assertEqual(vm.T, 0)

    def test_or(self):
        vm = _run([0x212B], {1: 0xF0, 2: 0x0F})          # or r2,r1
        self.assertEqual(vm.R[1], 0xFF)


if __name__ == '__main__':
    unittest.main()
