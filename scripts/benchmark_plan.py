#!/usr/bin/env python3
"""Write controlled one-variable A16 experiments; never benchmarks a device implicitly."""
import argparse
from pathlib import Path
import re

BASE = {
    'DM_RENDER_SCALE': '1.0', 'DM_OPMODE': '0', 'DM_OUTPUT_HEIGHT': '720',
    'DM_FPS_TARGET': '60', 'DM_PRESENT_UPSCALE': 'off', 'DM_PRESENT_SNAP': '1',
    'DM_PSO_MTL4': '1', 'DM_PSO_PREBUILD': '0', 'DM_NVN_ENC_THREAD': '1', 'DM_FPS_HOLD': 'on',
    'DM_BC_WORKERS': '2', 'DM_BC_CACHE': 'on', 'DM_PSO_PREPARE_THREADS': '2',
    'DM_PSO_USER_WARM': '1', 'DM_PSO_USER_WARM_LIMIT': '1024', 'DM_STUTTER': '1', 'DM_METAL_HUD': '1',
}
VARIANTS = {
    'baseline': {}, 'bc-1': {'DM_BC_WORKERS': '1'}, 'bc-4': {'DM_BC_WORKERS': '4'},
    'prepare-1': {'DM_PSO_PREPARE_THREADS': '1'}, 'prepare-4': {'DM_PSO_PREPARE_THREADS': '4'},
    'learned-512': {'DM_PSO_USER_WARM_LIMIT': '512'}, 'learned-2048': {'DM_PSO_USER_WARM_LIMIT': '2048'},
    'cache-off': {'DM_BC_CACHE': 'off'}, 'buffer-off': {'DM_PRESENT_SNAP': '0'},
    'classic-pso': {'DM_PSO_MTL4': '0'}, 'full-prebuild': {'DM_PSO_PREBUILD': '1'},
    'hold-off': {'DM_FPS_HOLD': 'off'}, 'metalfx': {'DM_PRESENT_UPSCALE': 'metalfx'},
    'cap-30': {'DM_FPS_TARGET': '30'}, 'recording-off': {'DM_STUTTER': '0'},
}


def profiles():
    return {name: {**BASE, **delta} for name, delta in VARIANTS.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--variant', choices=list(VARIANTS), action='append')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.out.name):
        ap.error('use a simple output folder name')
    for name in args.variant or VARIANTS:
        path = args.out / f'{name}.txt'
        with path.open('x') as out:
            out.write('# Copy ONE profile as Documents/env.txt while the app is stopped.\n')
            out.write('# Restart between trials; nominal handheld 720p. BOTW retains its own dynamic resolution at scale 1.0.\n')
            out.write('# DM_DYNAMIC_RESOLUTION is not a BOTW control. See docs/performance.md for measurement limits.\n')
            out.writelines(f'{key}={value}\n' for key, value in profiles()[name].items())
    print('Profiles written. These are experiments, not measured device recommendations.')


if __name__ == '__main__': main()
