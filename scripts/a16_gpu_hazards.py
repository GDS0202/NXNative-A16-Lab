#!/usr/bin/env python3
"""Summarize NVN uniform GPU-write hazards alongside measured GPU frame windows.

Read a single host log.txt/log.prev.txt from the same build/run. A row is a
~300-frame logging window, NOT a count of unique render passes or proof that
a GPU-write hazard caused the observed frame time. No game files are needed.
"""
import argparse
import json
from pathlib import Path
import re

MAX_BYTES = 32 * 1024 * 1024
TIMING = re.compile(
    r'\[nvn\] timing up to frame (\d+):.*?\bGPU p50 ([\d.]+) / p95 ([\d.]+)')
RESIDENCY = re.compile(
    r'\[nvn\] residency set up to frame (\d+):.*?'
    r'passes ended to land them for a read (\d+), '
    r'partly covered blocks read from memory (\d+) '
    r'\(cached (\d+), refused (\d+): other GPU writes (\d+), '
    r'earlier submission running (\d+), copy or fill queued (\d+), '
    r'size (\d+), unreadable (\d+)\)')
SBW = re.compile(
    r'\[nvn\] uniform GPU-write analysis up to frame (\d+): '
    r'unknown/invalid writes (\d+), known writes over 16 MiB (\d+), '
    r'page-table capacity failures (\d+); '
    r'shadows refused by conservative global overflow (\d+), '
    r'confirmed 16-byte tile conflicts (\d+), '
    r'same-page but disjoint ranges spared (\d+)')
SBW_FIELDS = ('unknown_writes', 'large_writes', 'capacity_failures',
              'global_overflow_denials', 'confirmed_tile_conflicts',
              'disjoint_same_page_spared')
# New optional counters are observational: they do NOT change the old log
# parser, GPU timings, or per-window safety statistics.
ORIGINS = re.compile(
    r'\[nvn\] uniform GPU-write origins up to frame (\d+): '
    r'storage notes (\d+) \(unknown (\d+), large (\d+), capacity (\d+)\); '
    r'bindless notes (\d+) \(unknown (\d+), large (\d+), capacity (\d+)\); '
    r'texture-copy notes (\d+) \(unknown (\d+), large (\d+), capacity (\d+)\)')
ORIGIN_NAMES = ('storage', 'bindless', 'texture_copy')
ORIGIN_FIELDS = ('notes', 'unknown', 'large', 'capacity')


def parse(lines):
    """Join by frame index only. Duplicate frames in a concatenated session
    are rejected rather than silently joined across runs."""
    rows = {}
    seen = {'timing': set(), 'residency': set(), 'sbw': set(), 'origins': set()}
    for line in lines:
        for typ, regex in (('timing', TIMING), ('residency', RESIDENCY),
                           ('sbw', SBW), ('origins', ORIGINS)):
            match = regex.search(line)
            if not match:
                continue
            frame = int(match.group(1))
            if frame in seen[typ]:
                raise ValueError(f'duplicate {typ} window frame {frame}; analyze sessions separately')
            seen[typ].add(frame)
            row = rows.setdefault(frame, {'frame': frame})
            values = match.groups()[1:]
            if typ == 'timing':
                row.update(gpu_p50_ms=float(values[0]), gpu_p95_ms=float(values[1]))
            elif typ == 'residency':
                fields = ('pass_cuts', 'partly_covered', 'shadows_cached',
                          'shadow_refusals', 'gpu_write_refusals',
                          'prior_submission_refusals', 'copy_fill_refusals',
                          'size_refusals', 'unreadable_refusals')
                row.update(zip(fields, map(int, values)))
            elif typ == 'sbw':
                row['gpu_write_diagnostics'] = dict(zip(SBW_FIELDS, map(int, values)))
            else:
                counts = list(map(int, values))
                row['gpu_write_origins'] = {
                    origin: dict(zip(ORIGIN_FIELDS, counts[4 * i:4 * (i + 1)]))
                    for i, origin in enumerate(ORIGIN_NAMES)
                }
            break
    complete = [rows[f] for f in sorted(rows)
                if 'gpu_p50_ms' in rows[f] and 'shadow_refusals' in rows[f]]
    if not complete:
        raise ValueError('no matched NVN timing/residency windows; check the log and format')
    return complete


def summarize(rows, top=8):
    if top < 1 or top > 100:
        raise ValueError('top must be between 1 and 100')
    total = lambda k: sum(row[k] for row in rows)
    bad = [row for row in rows if row['gpu_p50_ms'] > 1000 / 30]
    with_sb = [row for row in rows if 'gpu_write_diagnostics' in row]
    with_origins = [row for row in rows if 'gpu_write_origins' in row]
    samples = total('shadows_cached') + total('shadow_refusals')
    result = {
        'window_count': len(rows),
        'windows_above_30fps_gpu_budget': len(bad),
        'sum_uniform_pass_cuts': total('pass_cuts'),
        'sum_shadow_refusals': total('shadow_refusals'),
        'sum_gpu_write_refusals': total('gpu_write_refusals'),
        'shadow_refusal_fraction_of_cached_plus_refused': (
            round(total('shadow_refusals') / samples, 6) if samples else None),
        'detailed_gpu_write_windows': len(with_sb),
        'source_diagnostic_windows': len(with_origins),
        'most_shadow_refusals': sorted(rows, key=lambda r: (-r['shadow_refusals'], r['frame']))[:top],
        'highest_gpu_p95_ms': sorted(rows, key=lambda r: (-r['gpu_p95_ms'], r['frame']))[:top],
    }
    if with_sb:
        result['sum_gpu_write_diagnostics'] = {
            k: sum(row['gpu_write_diagnostics'][k] for row in with_sb)
            for k in SBW_FIELDS
        }
    if with_origins:
        result['sum_gpu_write_origins'] = {
            origin: {
                field: sum(row['gpu_write_origins'][origin][field]
                           for row in with_origins)
                for field in ORIGIN_FIELDS
            }
            for origin in ORIGIN_NAMES
        }
    return result


def inspect(path, top=8):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError('log missing or exceeds 32 MiB limit')
    with path.open(encoding='utf-8', errors='replace') as f:
        rows = parse(f)
    return {'source': path.name, 'summary': summarize(rows, top), 'windows': rows,
            'interpretation': (
                'Per-window diagnostic counts. Correlation is not causation. '
                'Confirmed tile conflicts are not necessarily distinct render-pass cuts. '
                'Source notes count bindings/copies, not unique GPU writes. '
                'The opt-in DM_NVN_SBW_TRACE may add CPU overhead; avoid comparing its FPS '
                'with uninstrumented runs. Compare only matching gameplay scenes, '
                'settings, and cache state.')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path, help='NXNative log.txt or log.prev.txt')
    parser.add_argument('--out', type=Path, help='write JSON report (no source paths or game files)')
    parser.add_argument('--top', type=int, default=8)
    args = parser.parse_args()
    try:
        report = inspect(args.log, args.top)
    except ValueError as exc:
        parser.error(str(exc))
    summary = report['summary']
    print(f"Matched {summary['window_count']} NVN windows; "
          f"{summary['windows_above_30fps_gpu_budget']} exceed 33.33 ms GPU p50")
    print(f"Uniform cuts {summary['sum_uniform_pass_cuts']}; "
          f"GPU-write shadow refusals {summary['sum_gpu_write_refusals']}")
    for row in summary['most_shadow_refusals']:
        tag = row.get('gpu_write_diagnostics')
        extra = (f" / global-overflow denials {tag['global_overflow_denials']}, "
                 f"true 16-B conflicts {tag['confirmed_tile_conflicts']}, "
                 f"disjoint-page savings {tag['disjoint_same_page_spared']}") if tag else ''
        print(f"  frame {row['frame']}: GPU p50/p95 "
              f"{row['gpu_p50_ms']:.2f}/{row['gpu_p95_ms']:.2f} ms; "
              f"uniform cuts {row['pass_cuts']}; "
              f"GPU-write refusals {row['gpu_write_refusals']}{extra}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        print(f"JSON report: {args.out}")


if __name__ == '__main__':
    main()
