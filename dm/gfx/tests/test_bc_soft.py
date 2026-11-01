"""CPU upload tests, including inherited decoder references and packed-byte goldens."""
import ctypes
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class BcUpload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.path = Path(cls.tmp.name) / 'bc.so'
        subprocess.run([shutil.which('clang') or 'cc', '-O2', '-ffp-contract=off', '-shared', '-fPIC',
                        str(ROOT / 'dm/gfx/tex/bc_soft.c'), '-o', str(cls.path)], check=True)
        cls.lib = ctypes.CDLL(str(cls.path))
        cls.lib.bc_soft_decode.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t,
                                          ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.bc_soft_out_block.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        cls.lib.bc_soft_block.argtypes = cls.lib.bc_soft_out_block.argtypes
        cls.lib.bc_soft_rows.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        cls.lib.bc_soft_rows.restype = ctypes.c_size_t

    def test_inherited_packed_bytes(self):
        """Golden hashes were generated from untouched 269d61f, not this encoder."""
        golden = json.loads((Path(__file__).with_name('bc_soft_golden.json')).read_text())
        for pf in (130, 131, 132, 133, 134, 135, 152, 153):
            rnd = random.Random(pf)
            h = hashlib.sha256()
            for _ in range(1000):
                b = bytes(rnd.getrandbits(8) for _ in range(8 if pf in (130, 131) else 16))
                out = ctypes.create_string_buffer(16)
                self.assertEqual(self.lib.bc_soft_out_block(pf, b, out, 16), 0)
                h.update(out.raw)
            self.assertEqual(h.hexdigest(), golden[str(pf)], str(pf))

    def test_rows_match_individual_blocks_with_padding_and_odd_mips(self):
        """Exercise ASTC, scalar channels and HDR; row guards catch overwrite."""
        rnd = random.Random(42)
        for astc in (0, 1):
            ctypes.c_int.in_dll(self.lib, 'nvn_bc_astc').value = astc
            for pf, bpp in ((130, 4), (131, 4), (132, 4), (134, 4), (140, 1), (141, 1),
                            (142, 2), (143, 2), (150, 8), (151, 4 if astc else 8), (152, 4)):
                for w, h in ((1, 1), (7, 9), (64, 64), (260, 129), (512, 512)):
                    bw, bh = (w + 3) // 4, (h + 3) // 4
                    bsz = 8 if pf in (130, 131, 140, 141) else 16
                    packed = astc and pf in (130, 131, 132, 134, 152)
                    sp, dp = bw * bsz + 11, bw * 4 * bpp + 13
                    # Last source row needs no trailing padding.
                    src = bytes(rnd.getrandbits(8) for _ in range((bh - 1) * sp + bw * bsz))
                    rows = self.lib.bc_soft_rows(pf, h)
                    out = ctypes.create_string_buffer(bytes([0xA5]) * (rows * dp + 32))
                    self.assertEqual(self.lib.bc_soft_decode(pf, src, sp, w, h, out, dp), 0)
                    for by in range(bh):
                        for bx in range(bw):
                            block = src[by * sp + bx * bsz:by * sp + (bx + 1) * bsz]
                            ref = ctypes.create_string_buffer(16 if packed else 16 * bpp)
                            self.lib.bc_soft_out_block(pf, block, ref, 16 if packed else 4 * bpp)
                            for y in range(1 if packed else 4):
                                i = (by * (1 if packed else 4) + y) * dp + bx * 4 * bpp
                                self.assertEqual(out.raw[i:i + 4 * bpp], ref.raw[y * 4 * bpp:(y + 1) * 4 * bpp])
                    for y in range(rows):
                        self.assertEqual(out.raw[y * dp + bw * 4 * bpp:(y + 1) * dp], bytes([0xA5]) * 13)
                    self.assertEqual(out.raw[rows * dp:rows * dp + 32], bytes([0xA5]) * 32)
        ctypes.c_int.in_dll(self.lib, 'nvn_bc_astc').value = 1

    def test_invalid_inputs_and_empty_regions(self):
        dst = ctypes.create_string_buffer(16)
        self.assertEqual(self.lib.bc_soft_decode(130, None, 8, 0, 4, None, 16), 0)
        self.assertEqual(self.lib.bc_soft_decode(130, None, 8, 4, 4, dst, 16), -1)
        self.assertEqual(self.lib.bc_soft_decode(130, bytes(8), 7, 4, 4, dst, 16), -1)
        self.assertEqual(self.lib.bc_soft_decode(130, bytes(8), 8, 4, 4, dst, 15), -1)
        self.assertEqual(self.lib.bc_soft_decode(999, bytes(8), 8, 4, 4, dst, 16), -1)

    def test_bc1_astc_with_independent_decoder(self):
        import texture2ddecoder
        rnd = random.Random(29)
        for _ in range(1000):
            b = bytes(rnd.getrandbits(8) for _ in range(8))
            if int.from_bytes(b[:2], 'little') <= int.from_bytes(b[2:4], 'little'):
                b = b[2:4] + b[:2] + b[4:]
            a, raw = ctypes.create_string_buffer(16), ctypes.create_string_buffer(64)
            self.lib.bc_soft_out_block(130, b, a, 16)
            self.lib.bc_soft_block(130, b, raw, 16)
            bgra = texture2ddecoder.decode_astc(a.raw, 4, 4, 4, 4)
            rgba = bytes(v for i in range(16) for v in (bgra[i*4+2], bgra[i*4+1], bgra[i*4], bgra[i*4+3]))
            self.assertLessEqual(max(abs(x-y) for x, y in zip(raw.raw, rgba)), 2)


if __name__ == '__main__':
    unittest.main()
