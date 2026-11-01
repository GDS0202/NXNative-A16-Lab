"""Large-file transfer boundaries and untrusted manifest validation, no network."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cloud_ipa', Path(__file__).resolve().parents[3] / 'scripts/cloud_ipa.py')
assert spec and spec.loader
cloud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud)


class Transfers(unittest.TestCase):
    def test_single_part_disk_budget_and_exact_reassembly(self):
        for size in (1, 31, 32, 33, 96, 97):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td); src = root / 'input.nsp'; src.write_bytes(bytes(range(size)))
                parts = []
                def accept(p, root=root, parts=parts):
                    self.assertEqual(len(list(root.glob('part-*.bin'))), 1)
                    parts.append(p.read_bytes())
                info = cloud.split_file(src, 0, root, accept, limit=32)
                self.assertEqual(b''.join(parts), src.read_bytes())
                self.assertEqual(info['sha256'], hashlib.sha256(src.read_bytes()).hexdigest())
                self.assertEqual(info['size'], size)
                self.assertEqual(list(root.glob('part-*.bin')), [])
                self.assertTrue(all(p['size'] <= 32 for p in info['parts']))

    def test_manifest_rejects_traversal_duplicates_and_inconsistent_lengths(self):
        h = hashlib.sha256(b'x').hexdigest()
        def entry(path, asset):
            return {'path': path, 'size': 1, 'sha256': h, 'parts': [{'asset': asset, 'size': 1, 'sha256': h}]}
        m = {'version': 1, 'kind': 'inputs', 'files': [entry('prod.keys', 'part-000-000.bin'), entry('game/input000.nsp', 'part-001-000.bin')]}
        self.assertEqual(cloud.validate_manifest(m), 2)
        import copy
        for mutate in (lambda x: x['files'][0].update(path='../prod.keys'),
                       lambda x: x['files'][0].update(path='/prod.keys'),
                       lambda x: x['files'][0].update(path='game/../../prod.keys'),
                       lambda x: x['files'][0]['parts'][0].update(asset='../part.bin'),
                       lambda x: x['files'][1]['parts'][0].update(asset='part-000-000.bin'),
                       lambda x: x['files'][0].update(size=2),
                       lambda x: x['files'][0].update(sha256='not a digest'),
                       lambda x: x.update(kind='public'),
                       lambda x: x['files'].append(x['files'][0])):
            case = copy.deepcopy(m); mutate(case)
            with self.assertRaises(ValueError): cloud.validate_manifest(case)


if __name__ == '__main__':
    unittest.main()
