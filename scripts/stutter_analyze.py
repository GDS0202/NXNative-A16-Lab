#!/usr/bin/env python3
"""Summarize bounded NXNative traces. No Xcode, games, saves or keys are needed."""
import argparse
import bisect
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys

MAX_BYTES = 128 * 1024**2


def percentile(ordered, percent):
    return ordered[max(0, math.ceil(len(ordered) * percent / 100) - 1)] if ordered else None


def summarize(values):
    ordered = sorted(v for v in values if math.isfinite(v) and v > 0)
    if not ordered:
        return {'samples': 0}
    n = len(ordered)
    tail = lambda fraction: ordered[-max(1, math.ceil(n * fraction)):]
    return {'samples': n, 'mean_fps': 1000 / statistics.fmean(ordered),
            'one_percent_low_fps': 1000 / statistics.fmean(tail(.01)),
            'point_one_percent_low_fps': 1000 / statistics.fmean(tail(.001)),
            'one_percent_tail_samples': max(1, math.ceil(n * .01)),
            'point_one_percent_tail_samples': max(1, math.ceil(n * .001)),
            'p50_ms': percentile(ordered, 50), 'p95_ms': percentile(ordered, 95),
            'p99_ms': percentile(ordered, 99), 'max_ms': ordered[-1],
            'over_33_333_ms': sum(v > 1000 / 30 + 1e-6 for v in ordered),
            'over_50_ms': sum(v > 50 for v in ordered),
            'over_100_ms': sum(v > 100 for v in ordered),
            'over_250_ms': sum(v > 250 for v in ordered)}


def read_trace(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('trace exceeds the reader limit')
    rows = []
    with path.open(encoding='utf-8') as src:
        for line in src:
            if len(line) > 16384: raise ValueError('oversized trace record')
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # A killed app may leave one partial final line. It is not a
                # complete trace and must not certify a comparison.
                if line.endswith('\n'): raise ValueError('malformed complete trace record') from None
                rows.append({'kind': 'status', 'lost': 1, 'capped': False}); break
            if not isinstance(row, dict) or row.get('kind') not in ('header', 'frame', 'present', 'system', 'boundary', 'status', 'memory', 'policy'):
                raise ValueError('unknown trace record')
            if row['kind'] in ('frame', 'present', 'system', 'boundary', 'memory', 'policy'):
                ns = row.get('timestamp_ns')
                if type(ns) is not int or ns <= 0: raise ValueError('invalid monotonic timestamp')
            for key, value in row.items():
                if key.endswith('_ms') and (type(value) not in (int, float) or not math.isfinite(value)):
                    raise ValueError('invalid duration')
            rows.append(row)
    if not rows or rows[0].get('schema') not in (1, 2) or rows[0].get('kind') != 'header':
        raise ValueError('unsupported trace schema')
    if rows[0].get('generated_fps') != 0:
        raise ValueError('this analyzer requires separate real-frame traces; generated frames cannot be counted as real')
    if rows[0]['schema'] == 2: rows[0]['retained_window'] = rows[0].get('segment', 0) > 0
    return rows


def read_segments(path, previous=None, events=()):
    paths = ([previous] if previous else []) + [path]
    if len(events) > 2 or sum(p.stat().st_size for p in paths + list(events)) > MAX_BYTES + 2 * 1024**2:
        raise ValueError('combined trace exceeds the reader limit')
    traces = [read_trace(p) for p in paths]
    if len(traces) == 1 and not events and traces[0][0]['schema'] == 1: return traces[0]
    heads = [t[0] for t in traces]
    if any(h.get('schema') != 2 or h.get('events_only') for h in heads):
        raise ValueError('only full schema-2 segments can be joined')
    session = heads[0].get('session')
    if type(session) is not int or session <= 0 or any(h.get('session') != session for h in heads):
        raise ValueError('segments belong to different sessions')
    traces.sort(key=lambda t: t[0]['segment'])
    indices = [t[0]['segment'] for t in traces]
    if any(type(i) is not int or i < 0 for i in indices) or indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError('segments are duplicate or nonconsecutive')
    header = dict(traces[0][0], retained_window=indices[0] > 0, segment_count=len(traces))
    rows = [header] + [r for t in traces for r in t[1:]]
    known = {(r['kind'], r['timestamp_ns']) for r in rows if r['kind'] in ('memory', 'policy', 'boundary')}
    for p in events:
        extra = read_trace(p)
        if extra[0].get('session') != session or not extra[0].get('events_only'):
            raise ValueError('event journal belongs to a different session or is not an event journal')
        for r in extra[1:]:
            if r['kind'] not in ('memory', 'policy', 'boundary'): raise ValueError('unexpected journal record')
            key = (r['kind'], r['timestamp_ns'])
            if key not in known: rows.append(r); known.add(key)
    return rows


def analyze(rows, start=0, seconds=None):
    presents = sorted((r for r in rows if r['kind'] == 'present'), key=lambda r: r['timestamp_ns'])
    if len(presents) < 2: raise ValueError('at least two actual presentation callbacks are needed')
    origin = presents[0]['timestamp_ns']
    begin, end = origin + start * 1e9, origin + (start + seconds) * 1e9 if seconds is not None else math.inf
    chosen = lambda r: begin <= r['timestamp_ns'] <= end
    systems = sorted((r for r in rows if r['kind'] == 'system'), key=lambda r: r['timestamp_ns'])
    system_times = [r['timestamp_ns'] for r in systems]
    boundaries = sorted(r['timestamp_ns'] for r in rows if r['kind'] == 'boundary')
    def uninterrupted_frame(row):
        if not chosen(row): return False
        stop = row['timestamp_ns']; first = stop - max(0, row.get('frame_ms', 0)) * 1e6
        cut = bisect.bisect_right(boundaries, first)
        return first >= begin and (cut == len(boundaries) or boundaries[cut] > stop)
    frames = {r['frame']: r for r in rows if r['kind'] == 'frame' and uninterrupted_frame(r)}
    intervals, hitches, hints = [], [], Counter()
    tickets, seen = 0, set()
    previous = None
    for current in presents:
        identity = current['ticket']  # A repeated callback for one real frame is not another rendered frame.
        if identity in seen: continue
        seen.add(identity)
        if previous is not None:
            a, b = previous['timestamp_ns'], current['timestamp_ns']
            boundary = bisect.bisect_right(boundaries, a)
            crossed = boundary < len(boundaries) and boundaries[boundary] <= b
            if chosen(current) and chosen(previous) and b > a and not crossed:
                interval = (b - a) / 1e6; intervals.append(interval)
                tickets += max(0, current['ticket'] - previous['ticket'] - 1)
                if interval > 50:
                    frame = frames.get(current['frame'], {})
                    threshold = max(3, interval * .25)
                    evidence = [key for key in ('compile_ms', 'bc_decode_ms', 'bc_cache_ms', 'upload_ms',
                                'upload_gpu_ms', 'sync_ms', 'acquire_ms', 'present_wait_ms', 'drawable_ms', 'sub_cpu_ms')
                                if frame.get(key, -1) >= threshold]
                    expected = frame.get('expected_ms', 1000 / 60)
                    if frame.get('gpu_ms', -1) > max(expected, interval * .65): evidence.append('gpu_work')
                    index = bisect.bisect_right(system_times, b) - 1
                    if index >= 0 and b - system_times[index] <= 2 * 1e9:
                        system = systems[index]
                        if 0 < system.get('headroom_bytes', 0) < 512 * 1024**2: evidence.append('low_memory_headroom')
                        if system.get('thermal', -1) >= 2: evidence.append('serious_thermal_state')
                    if not evidence: evidence = ['unknown']
                    hints.update(evidence)
                    hitches.append({'at_seconds': (b - origin) / 1e9, 'frame': current['frame'],
                                    'interval_ms': interval, 'correlated_evidence': evidence,
                                    'root_cause': 'not_established'})
        previous = current
    relevant = [r for r in systems if chosen(r)]
    stats = [r for r in rows if r['kind'] == 'status']
    lost = max((r.get('lost', 0) for r in stats), default=0)
    retained = rows[0].get('retained_window', False)
    complete = bool(stats) and not lost and not retained and not any(r.get('capped') for r in stats)
    observed = lambda key: [f[key] for f in frames.values() if isinstance(f.get(key), (float, int)) and f[key] >= 0]
    mean = lambda values: statistics.fmean(values) if values else None
    warnings = []
    if retained: warnings.append('The oldest segments rotated out; statistics describe the retained window, not the whole session.')
    if not complete: warnings.append('Trace lost records, reached its cap, or has no flushed status; comparison cannot certify a gain.')
    if len(intervals) < 1000: warnings.append('Fewer than 1000 displayed intervals: 0.1% low has a very small tail.')
    warnings.append('CPU/process counters and asynchronous work can overlap; correlated evidence does not prove a root cause.')
    transitions = [{**r, 'at_seconds': (r['timestamp_ns'] - origin) / 1e9} for r in rows if r['kind'] in ('memory', 'policy') and chosen(r)]
    memory_events = sorted((r for r in transitions if r['kind'] == 'memory'), key=lambda r: r['timestamp_ns'])
    policies = sorted((r for r in transitions if r['kind'] == 'policy'), key=lambda r: r['timestamp_ns'])
    changes, previous_policy = [], None
    for r in policies:
        key = tuple(r.get(k) for k in ('requested_fps', 'effective_cap', 'cap_reasons', 'scale_percent', 'texture_filter', 'far_clip'))
        if key != previous_policy: changes.append(r); previous_policy = key
    return {'schema': 2, 'complete': complete, 'retained_window': retained, 'lost_records': lost,
            'duration_seconds': sum(intervals) / 1000, 'memory_events': memory_events, 'policy_changes': changes,
            'displayed_real_frames': summarize(intervals),
            'guest_produced_intervals': summarize(observed('frame_ms')),
            'generated_fps': 0, 'unpresented_ticket_gaps': tickets,
            'mean_gpu_ms': mean(observed('gpu_ms')), 'mean_submit_cpu_ms': mean(observed('sub_cpu_ms')),
            'mean_process_cpu_ms_per_interval': mean(observed('process_cpu_ms')),
            'compile_total_ms': sum(observed('compile_ms')), 'bc_decode_total_ms': sum(observed('bc_decode_ms')),
            'bc_cache_total_ms': sum(observed('bc_cache_ms')), 'upload_total_ms': sum(observed('upload_ms')),
            'cache_hits': sum(observed('cache_hits')), 'cache_misses': sum(observed('cache_misses')),
            'peak_footprint_bytes': max((r.get('footprint_bytes', 0) for r in relevant), default=None),
            'minimum_headroom_bytes': min((r.get('headroom_bytes', 0) for r in relevant), default=None),
            'maximum_thermal_state': max((r.get('thermal', -1) for r in relevant), default=None),
            'hitch_correlations': dict(hints), 'worst_hitches': sorted(hitches, key=lambda r: r['interval_ms'], reverse=True)[:50],
            'warnings': warnings}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace', type=Path); ap.add_argument('--compare', type=Path)
    ap.add_argument('--previous-segment', type=Path, help='Matching stutter.1.jsonl from the same session')
    ap.add_argument('--events', type=Path, action='append', default=[], help='Matching performance-events[.1].jsonl; at most two')
    ap.add_argument('--start', type=float, default=0, help='Seconds after the first actual presentation')
    ap.add_argument('--seconds', type=float); ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    try:
        if not math.isfinite(args.start) or args.start < 0 or (args.seconds is not None and (not math.isfinite(args.seconds) or args.seconds <= 0)):
            raise ValueError('use a nonnegative start and positive duration')
        result = analyze(read_segments(args.trace, args.previous_segment, args.events), args.start, args.seconds)
        if args.compare:
            baseline = analyze(read_trace(args.compare), args.start, args.seconds)
            if not result['complete'] or not baseline['complete']: raise ValueError('A/B certification requires two complete traces')
            result = {'baseline': baseline, 'candidate': result,
                      'interpretation': 'Numbers only; require matching route, save, resolution, settings, cache state and repetitions.'}
        encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
        if args.json: args.json.write_text(encoded)
        else: print(encoded, end='')
    except (OSError, KeyError, TypeError, ValueError) as e:
        sys.exit(f'stutter analyzer: {e}')


if __name__ == '__main__': main()
