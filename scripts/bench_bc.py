#!/usr/bin/env python3
"""Serial texture-conversion microbenchmark, never a gameplay/FPS benchmark."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import tempfile
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', default='269d61ff974b2e8e073d7357466ae130c3f6812f')
    ap.add_argument('--repeats', type=int, default=7)
    args = ap.parse_args()
    if not 3 <= args.repeats <= 100:
        ap.error('repeats must be 3..100')
    root = Path(__file__).resolve().parents[1]
    compiler = shutil.which('clang') or shutil.which('cc')
    if not compiler:
        ap.error('a C compiler is required')
    sources = {'baseline': subprocess.check_output(['git', 'show', f'{args.baseline}:dm/gfx/tex/bc_soft.c'], cwd=root),
               'candidate': (root / 'dm/gfx/tex/bc_soft.c').read_bytes()}
    report = {'kind': 'serial component microbenchmark; not gameplay', 'machine': platform.machine(),
              'platform': platform.platform(), 'compiler': subprocess.check_output([compiler, '--version'], text=True).splitlines()[0],
              'baseline': args.baseline, 'participants': 1, 'repeats': args.repeats, 'results': []}
    with tempfile.TemporaryDirectory(prefix='nx-bc-bench-') as td:
        temp = Path(td); libs = {}
        for name, data in sources.items():
            # Exclude dispatch policy from this arithmetic comparison on every
            # OS; the A16 worker budget requires gameplay/contended CPU tests.
            p = temp / f'{name}.c'; p.write_bytes(data.replace(b'#ifdef __APPLE__', b'#if 0 /* serial component benchmark */'))
            lib = temp / f'{name}.so'
            subprocess.run([compiler, '-O2', '-ffp-contract=off', '-fPIC', '-shared', '-I', str(root / 'dm/gfx/tex'), str(p), '-o', str(lib)], check=True)
            libs[name] = ctypes.CDLL(str(lib))
            libs[name].bc_soft_decode.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_size_t]
        for pf in (130, 134, 152):
            rng = random.Random(pf); bs = 8 if pf == 130 else 16; side = 512
            src = bytes(rng.getrandbits(8) for _ in range(side * side // 16 * bs)); outputs, times = {}, {}
            for name, lib in libs.items():
                out = ctypes.create_string_buffer(side * side); elapsed = []
                for _ in range(args.repeats + 1):
                    t = time.perf_counter_ns()
                    rc = lib.bc_soft_decode(pf, src, side // 4 * bs, side, side, out, side * 4)
                    elapsed.append((time.perf_counter_ns() - t) / 1e6)
                    if rc: raise RuntimeError('decoder rejected benchmark input')
                outputs[name] = out.raw; times[name] = statistics.median(elapsed[1:])
            if outputs['baseline'] != outputs['candidate']:
                raise RuntimeError('candidate differs from baseline')
            report['results'].append({'format': pf, 'width': side, 'height': side, 'input': 'seeded random blocks',
                                      'baseline_ms': times['baseline'], 'candidate_ms': times['candidate'],
                                      'speedup': times['baseline'] / times['candidate'],
                                      'identical_output_sha256': hashlib.sha256(outputs['candidate']).hexdigest()})
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
