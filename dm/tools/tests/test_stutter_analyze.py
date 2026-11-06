"""Displayed pacing uses actual callbacks, includes skipped tickets and excludes pauses."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('stutter_analyze', ROOT / 'scripts/stutter_analyze.py')
if spec is None or spec.loader is None: raise ImportError('stutter_analyze')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)


def fixture(intervals, gpu=5, compile_ms=0):
    now = 1_000_000_000
    rows = [{'kind': 'header', 'schema': 1, 'generated_fps': 0},
            {'kind': 'present', 'ticket': 1, 'frame': 1, 'timestamp_ns': now}]
    for i, interval in enumerate(intervals, 2):
        now += round(interval * 1e6)
        rows.append({'kind': 'frame', 'frame': i, 'timestamp_ns': now,
                     'frame_ms': interval, 'gpu_ms': gpu, 'compile_ms': compile_ms})
        rows.append({'kind': 'present', 'ticket': i, 'frame': i, 'timestamp_ns': now})
    rows.append({'kind': 'status', 'capped': False, 'lost': 0})
    return rows


class Analyze(unittest.TestCase):
    def test_rolling_segments_and_journal_preserve_memory_transition(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = fixture([16, 16, 16])
            header = {'kind': 'header', 'schema': 2, 'generated_fps': 0, 'session': 456, 'segment': 2, 'events_only': False}
            first = [header] + rows[1:4] + [rows[-1]]
            second = [dict(header, segment=3)] + rows[4:]
            memory = {'kind': 'memory', 'timestamp_ns': 1_020_000_000, 'level': 2, 'os_pressure': 2, 'reason': 1}
            for name, data in [('old', first), ('new', second), ('events', [dict(header, events_only=True), memory])]:
                (root / name).write_text(''.join(json.dumps(r) + '\n' for r in data))
            merged = a.read_segments(root / 'new', root / 'old', [root / 'events'])
            out = a.analyze(merged)
            self.assertEqual(out['displayed_real_frames']['samples'], 3)
            self.assertEqual(out['memory_events'][0]['level'], 2)
            self.assertTrue(out['retained_window']); self.assertFalse(out['complete'])
            second[0]['session'] = 457
            (root / 'new').write_text(''.join(json.dumps(r) + '\n' for r in second))
            with self.assertRaisesRegex(ValueError, 'different sessions'): a.read_segments(root / 'new', root / 'old')

    def test_duplicate_ticket_at_a_different_timestamp_is_not_a_new_real_frame(self):
        rows = fixture([16, 16])
        rows.append(dict(rows[1], timestamp_ns=1_008_000_000))
        self.assertEqual(a.analyze(rows)['displayed_real_frames']['samples'], 2)

    def test_known_percentiles_and_tail_means(self):
        stats = a.summarize([10] * 98 + [50, 100])
        self.assertEqual(stats['p95_ms'], 10)
        self.assertEqual(stats['p99_ms'], 50)
        self.assertEqual(stats['one_percent_low_fps'], 10)
        self.assertAlmostEqual(stats['mean_fps'], 1000 / 11.3)
        self.assertEqual(stats['over_50_ms'], 1)
        self.assertEqual(stats['over_100_ms'], 0)

    def test_zero_negative_and_nan_are_not_fps(self):
        self.assertEqual(a.summarize([0, -1, float('nan')]), {'samples': 0})

    def test_missing_tickets_do_not_hide_a_display_hitch(self):
        rows = fixture([16, 16, 150])
        rows[-2]['ticket'] = 7
        out = a.analyze(rows)
        self.assertEqual(out['displayed_real_frames']['max_ms'], 150)
        self.assertEqual(out['unpresented_ticket_gaps'], 3)
        self.assertEqual(out['hitch_correlations'], {'unknown': 1})
        self.assertEqual(out['generated_fps'], 0)

    def test_timestamp_order_and_duplicate_callbacks(self):
        rows = fixture([16, 18, 55])
        self.assertEqual(a.analyze(rows)['displayed_real_frames'],
                         a.analyze([rows[0]] + list(reversed(rows[1:])) + [rows[1]])['displayed_real_frames'])

    def test_frame_time_alone_does_not_mean_gpu_bound(self):
        out = a.analyze(fixture([120], gpu=5, compile_ms=70))
        self.assertEqual(out['hitch_correlations'], {'compile_ms': 1})
        self.assertEqual(out['worst_hitches'][0]['root_cause'], 'not_established')

    def test_nearby_memory_thermal_are_correlations(self):
        rows = fixture([200], gpu=180)
        rows.append({'kind': 'system', 'timestamp_ns': 1_100_000_000,
                     'headroom_bytes': 200 * 1024**2, 'footprint_bytes': 3000 * 1024**2, 'thermal': 2})
        out = a.analyze(rows)
        self.assertEqual(set(out['hitch_correlations']), {'gpu_work', 'low_memory_headroom', 'serious_thermal_state'})

    def test_background_does_not_become_a_six_second_game_hitch(self):
        rows = fixture([16, 6000, 16])
        rows.append({'kind': 'boundary', 'timestamp_ns': 2_000_000_000})
        out = a.analyze(rows)
        self.assertEqual(out['displayed_real_frames']['samples'], 2)
        self.assertEqual(out['guest_produced_intervals']['max_ms'], 16)

    def test_window_does_not_join_to_previous_phase(self):
        out = a.analyze(fixture([100, 200, 300]), start=.1, seconds=.21)
        self.assertEqual(out['displayed_real_frames']['samples'], 1)
        self.assertEqual(out['displayed_real_frames']['max_ms'], 200)

    def test_incomplete_and_capped_traces_are_marked(self):
        for status in ({'kind': 'status', 'lost': 1}, {'kind': 'status', 'lost': 0, 'capped': True}):
            rows = fixture([16, 50]); rows[-1] = status
            self.assertFalse(a.analyze(rows)['complete'])

    def test_reader_accepts_only_supported_schema_and_finite_durations(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'trace.jsonl'
            rows = fixture([16, 16]); path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            self.assertTrue(a.analyze(a.read_trace(path))['complete'])
            rows[0]['generated_fps'] = 30; path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'generated frames'): a.read_trace(path)
            rows[0]['generated_fps'] = 0; rows[2]['frame_ms'] = float('nan')
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'invalid duration'): a.read_trace(path)

    def test_partial_last_line_marks_the_trace_incomplete(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'trace.jsonl'
            path.write_text(''.join(json.dumps(r) + '\n' for r in fixture([16, 16])) + '{"kind":')
            self.assertFalse(a.analyze(a.read_trace(path))['complete'])


if __name__ == '__main__': unittest.main()
