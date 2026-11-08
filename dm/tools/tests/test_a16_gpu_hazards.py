"""CPU-only tests for per-window NVN GPU-write diagnostic reports."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('a16_gpu_hazards', ROOT / 'scripts/a16_gpu_hazards.py')
if spec is None or spec.loader is None:
    raise ImportError('a16_gpu_hazards')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def fixture(frame, gpu50, gpu95, cuts, refuses, with_sbw=False, with_origins=False):
    lines = [
        f"[dm] [nvn] timing up to frame {frame}: frame time p50 59.9 / p95 70.0 "
        f"/ max 90.0 ms (300 frames); GPU p50 {gpu50} / p95 {gpu95} / max 70 ms (300 frames);",
        f"[dm] [nvn] residency set up to frame {frame}: commits 99 / 8.1 ms; "
        f"passes ended to land them for a read {cuts}, partly covered blocks read from memory 52 "
        f"(cached 52, refused {refuses}: other GPU writes {refuses}, earlier submission running 0, "
        f"copy or fill queued 0, size 0, unreadable 0); foo"
    ]
    if with_sbw:
        lines.append(
            f"[dm] [nvn] uniform GPU-write analysis up to frame {frame}: "
            "unknown/invalid writes 2, known writes over 16 MiB 3, "
            "page-table capacity failures 4; shadows refused by conservative global overflow 5, "
            "confirmed 16-byte tile conflicts 6, same-page but disjoint ranges spared 7 "
            "(diagnostic counts, not exact saved render passes)")
    if with_origins:
        lines.append(
            f"[dm] [nvn] uniform GPU-write origins up to frame {frame}: "
            "storage notes 100 (unknown 1, large 2, capacity 3); "
            "bindless notes 45 (unknown 45, large 0, capacity 0); "
            "texture-copy notes 20 (unknown 0, large 0, capacity 0) "
            "(DM_NVN_SBW_TRACE, counts per binding/copy, not distinct writes)")
    return lines


class HazardReportTests(unittest.TestCase):
    def test_old_and_new_format_not_confused_with_frame_time(self):
        rows = report.parse(fixture(193500, "59.20", "63.12", 54993, 54993, True)
                            + fixture(193800, "59.72", "63.36", 43680, 43680))
        self.assertEqual([r['frame'] for r in rows], [193500, 193800])
        self.assertEqual(rows[0]['gpu_p50_ms'], 59.2)
        self.assertEqual(rows[0]['pass_cuts'], 54993)
        self.assertEqual(rows[1]['gpu_write_refusals'], 43680)
        self.assertNotIn('gpu_write_diagnostics', rows[1])
        self.assertEqual(rows[0]['gpu_write_diagnostics']['disjoint_same_page_spared'], 7)
        summary = report.summarize(rows)
        self.assertEqual(summary['sum_uniform_pass_cuts'], 98673)
        self.assertEqual(summary['sum_gpu_write_refusals'], 98673)
        self.assertEqual(summary['detailed_gpu_write_windows'], 1)
        self.assertEqual(summary['sum_gpu_write_diagnostics']['global_overflow_denials'], 5)
        self.assertEqual(summary['windows_above_30fps_gpu_budget'], 2)

    def test_optional_origin_attribution_and_legacy_windows(self):
        rows = report.parse(
            fixture(300, 32, 39, 8, 3, with_sbw=True, with_origins=True)
            + fixture(600, 25, 29, 4, 2, with_sbw=False, with_origins=False)
            + fixture(900, 34, 47, 18, 15, with_origins=True))
        self.assertEqual([r['frame'] for r in rows], [300, 600, 900])
        self.assertNotIn('gpu_write_origins', rows[1])
        self.assertEqual(rows[0]['gpu_write_origins']['bindless']['unknown'], 45)
        self.assertEqual(rows[2]['gpu_write_origins']['storage']['large'], 2)
        summary = report.summarize(rows)
        self.assertEqual(summary['source_diagnostic_windows'], 2)
        self.assertEqual(summary['detailed_gpu_write_windows'], 1)
        self.assertEqual(summary['sum_gpu_write_origins']['storage']['notes'], 200)
        self.assertEqual(summary['sum_gpu_write_origins']['bindless']['unknown'], 90)
        self.assertEqual(summary['sum_gpu_write_origins']['texture_copy']['notes'], 40)
        with self.assertRaisesRegex(ValueError, 'duplicate origins window'):
            report.parse(fixture(300, 20, 22, 3, 2, with_origins=True)
                         + fixture(300, 23, 24, 3, 2, with_origins=True)[-1:])

    def test_same_frame_only_joined_and_duplicate_rejected(self):
        self.assertRaises(ValueError, report.parse, ["[dm] [nvn] unrelated stuff"])
        self.assertRaises(ValueError, report.parse, fixture(300, 20, 21, 1, 1) +
                          fixture(300, 22, 23, 2, 2))
        rows = report.parse(fixture(300, 20, 21, 1, 1) +
                            ["[dm] [nvn] timing up to frame 600: GPU p50 30 / p95 40"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['frame'], 300)

    def test_report_json_roundtrip_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'log.txt'
            path.write_text('\n'.join(fixture(300, 20, 21, 15, 2, True)) + '\n',
                            encoding='utf-8')
            result = report.inspect(path)
            self.assertEqual(json.loads(json.dumps(result))['summary']['window_count'], 1)
            self.assertEqual(report.summarize(result['windows'])['shadow_refusal_fraction_of_cached_plus_refused'],
                             round(2 / 54, 6))
            with self.assertRaises(ValueError):
                report.inspect(path, 0)


if __name__ == '__main__':
    unittest.main()
