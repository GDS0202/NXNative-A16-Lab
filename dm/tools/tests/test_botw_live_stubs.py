"""Execute the generated AArch64 stubs, including branch targets and register preservation.

Synthetic instructions/state only; no game binary. Real builds additionally
assert each original instruction through ctx.site before rewriting anything.
"""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'dm/tools'))
try:
    unicorn = importlib.import_module('unicorn')
    reg = importlib.import_module('unicorn.arm64_const')
except ImportError:
    unicorn = None


@unittest.skipIf(unicorn is None, 'install unicorn for executable AArch64 fixtures')
class LiveStubs(unittest.TestCase):
    def setUp(self):
        assert unicorn is not None
        self.engine = unicorn
        spec = importlib.util.spec_from_file_location('botw_live', ROOT / 'dm/games/01007EF00011E000/patches.py')
        assert spec and spec.loader
        self.profile = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.profile)
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        self.base = 0x10000000; self.uc.mem_map(self.base, 0x2000000)
        self.state = 0x1f80000
        owner = self
        class Context:
            render_scale = 0
            runtime_tuning = 0
            state = 0x1f80000
            def __init__(self): self.offset = 0x1f00000
            def here(self): return self.offset
            def emit(self, word): owner.uc.mem_write(owner.base + self.offset, struct.pack('<I', word)); self.offset += 4
            def site(self, offset, old): owner.assertEqual(len(bytes.fromhex(old)), 4)
            def put(self, offset, words, reason):
                owner.uc.mem_write(owner.base + offset, b''.join(struct.pack('<I', w) for w in words))
        self.ctx = Context(); self.profile.frame_step(self.ctx)
        self.uc.reg_write(reg.UC_ARM64_REG_SP, self.base + 0x1ef0000)

    def run_until(self, start, ends):
        stopped = []
        def stop(uc, address, size, _):
            if address - self.base in ends: stopped.append(address - self.base); uc.emu_stop()
        hook = self.uc.hook_add(self.engine.UC_HOOK_CODE, stop)
        self.uc.emu_start(self.base + start, 0, count=200)
        self.uc.hook_del(hook); self.assertEqual(len(stopped), 1)
        return stopped[0]

    def test_render_scale_and_verified_full_scale_flag(self):
        self.assertEqual(self.ctx.runtime_tuning, 7)
        bits = lambda f: struct.unpack('<I', struct.pack('<f', f))[0]
        for scale, flag, expected, finish in [(1, 0, .7, 0x1266950), (1, 1, 1, 0x1266884), (.8, 0, .8, 0x1266884), (.8, 1, .8, 0x1266884)]:
            with self.subTest(scale=scale, flag=flag):
                self.uc.mem_write(self.base + self.state + 0x10, struct.pack('<fI', scale, flag))
                self.uc.reg_write(reg.UC_ARM64_REG_X20, self.base + 0x1ed0000)
                self.uc.reg_write(reg.UC_ARM64_REG_S8, bits(.7))
                self.assertEqual(self.run_until(0x126686c, {0x1266950, 0x1266884}), finish)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_S8), bits(expected))

    def test_camera_clip_preserves_registers_and_original_zero_path(self):
        camera = self.base + 0x1ed0000; original = 12345.0
        for clip in (0.0, 500.0, 5000.0):
            with self.subTest(clip=clip):
                self.uc.mem_write(self.base + self.state + 0x18, struct.pack('<f', clip))
                self.uc.reg_write(reg.UC_ARM64_REG_X8, camera)
                self.uc.reg_write(reg.UC_ARM64_REG_X16, 0x123456789abcdef)
                original_bits = struct.unpack('<I', struct.pack('<f', original))[0]
                self.uc.reg_write(reg.UC_ARM64_REG_S0, original_bits)
                self.uc.reg_write(reg.UC_ARM64_REG_NZCV, 0xa0000000)
                sp = self.uc.reg_read(reg.UC_ARM64_REG_SP)
                self.run_until(0xc2dbd0, {0xc2dbd4})
                self.assertEqual(struct.unpack('<f', self.uc.mem_read(camera + 0x70, 4))[0], clip or original)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_X16), 0x123456789abcdef)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_X8), camera)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_S0), original_bits)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_SP), sp)
                self.assertEqual(self.uc.reg_read(reg.UC_ARM64_REG_NZCV), 0xa0000000)


if __name__ == '__main__': unittest.main()
