"""Selected downloads, immutable same-repo data references and atomic failure."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('cloud_ipa', Path(__file__).resolve().parents[3] / 'scripts/cloud_ipa.py')
if spec is None or spec.loader is None: raise ImportError('cloud_ipa')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)


def entry(name, content, asset, **extra):
    digest = hashlib.sha256(content).hexdigest()
    return {'path': name, 'size': len(content), 'sha256': digest,
            'parts': [{'asset': asset, 'size': len(content), 'sha256': digest}], **extra}


class Selection(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup); self.root = Path(td.name)
        self.manifest = {'version': 2, 'kind': 'output', 'files': [
            entry('BOTW-A16.ipa', b'ipa', 'part-000-000.bin'),
            entry('build.json', b'{}', 'part-001-000.bin'),
            entry('romfs.img', b'data', 'part-001-000.bin', source_tag='old-output')]}
        self.assets = {('new-output', 'part-000-000.bin'): b'ipa', ('new-output', 'part-001-000.bin'): b'{}',
                       ('old-output', 'part-001-000.bin'): b'data'}
        self.downloads = []
        patcher = mock.patch.object(c, 'gh', self.gh); patcher.start(); self.addCleanup(patcher.stop)

    def gh(self, *args, capture=False):
        if args[0] == 'api': return '{"private":true}'
        self.assertEqual(args[:2], ('release', 'download'))
        tag, pattern = args[2], args[args.index('--pattern') + 1]
        out = Path(args[args.index('--dir') + 1]); self.downloads.append((tag, pattern))
        content = json.dumps(self.manifest).encode() if pattern == 'manifest.json' else self.assets[tag, pattern]
        (out / pattern).write_bytes(content)

    def test_only_ipa_never_downloads_data(self):
        out = self.root / 'selected'
        c.restore('owner/private', 'new-output', out, ['BOTW-A16.ipa'])
        self.assertEqual((out / 'BOTW-A16.ipa').read_bytes(), b'ipa')
        self.assertEqual(sorted(p.name for p in out.iterdir()), ['BOTW-A16.ipa'])
        self.assertNotIn(('old-output', 'part-001-000.bin'), self.downloads)

    def test_reference_uses_its_tag_with_part_name_collisions(self):
        out = self.root / 'complete'
        c.restore('owner/private', 'new-output', out)
        self.assertEqual((out / 'romfs.img').read_bytes(), b'data')
        self.assertEqual((out / 'build.json').read_bytes(), b'{}')

    def test_corrupt_download_never_becomes_a_complete_ipa(self):
        self.assets['new-output', 'part-000-000.bin'] = b'bad'
        out = self.root / 'broken'
        with self.assertRaisesRegex(ValueError, 'integrity'): c.restore('owner/private', 'new-output', out, ['BOTW-A16.ipa'])
        self.assertEqual(list(out.iterdir()), [])

    def test_reference_is_flattened_without_transferring_romfs(self):
        ref = c.data_reference('owner/private', 'new-output')
        self.assertEqual(ref['source_tag'], 'old-output')
        self.assertEqual(self.downloads, [('new-output', 'manifest.json')])

    def test_references_cannot_select_another_repo_or_keys(self):
        for tag in ('../other', 'owner/repo', '--repo=other', 'https://example.test', ['old-output']):
            case = copy.deepcopy(self.manifest); case['files'][2]['source_tag'] = tag
            with self.assertRaises(ValueError): c.validate_manifest(case)
        case = copy.deepcopy(self.manifest); case['files'][0]['source_tag'] = 'old-output'
        with self.assertRaises(ValueError): c.validate_manifest(case)

    def test_partial_inputs_and_unknown_output_names_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'existing output'):
            c.restore('owner/private', 'new-output', self.root / 'unknown', ['prod.keys'])

    def test_invalid_types_fail_before_download(self):
        for mutate in (lambda m: m['files'][0].update(parts=None), lambda m: m['files'][0].update(size=True),
                       lambda m: m['files'][0]['parts'][0].update(asset=None), lambda m: m['files'][0].update(sha256=[])):
            m = copy.deepcopy(self.manifest); mutate(m)
            with self.assertRaises(ValueError): c.validate_manifest(m)


if __name__ == '__main__': unittest.main()
