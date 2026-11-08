"""Source-only guard: two A16 GPU hazard A/B profiles differ in one switch."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('benchmark_plan', ROOT / 'scripts/benchmark_plan.py')
if spec is None or spec.loader is None:
    raise ImportError('benchmark_plan')
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)


class A16HazardProfileTests(unittest.TestCase):
    def test_fine_and_page_use_identical_graphics_and_recording_settings(self):
        profiles = plan.profiles()
        fine, page = profiles['sbw-fine'], profiles['sbw-page']
        self.assertEqual(set(fine), set(page))
        self.assertEqual([key for key in fine if fine[key] != page[key]],
                         ['DM_NVN_SBW_FINE'])
        self.assertEqual(fine['DM_NVN_SBW_FINE'], '1')
        self.assertEqual(page['DM_NVN_SBW_FINE'], '0')
        self.assertEqual({k: v for k, v in fine.items() if k != 'DM_NVN_SBW_FINE'},
                         profiles['baseline'])


if __name__ == '__main__':
    unittest.main()
