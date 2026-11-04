"""Untrusted upstream metadata stays data, and private/unavailable sources stay out."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('upstream_monitor', Path(__file__).resolve().parents[3] / 'scripts/upstream_monitor.py')
if spec is None or spec.loader is None: raise ImportError('upstream_monitor')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
SHA = 'a' * 40
CONFIG = {'sources': [{'repo': 'public/source', 'ref': 'fix/race', 'reviewed_sha': SHA}]}


class Monitor(unittest.TestCase):
    def api(self, endpoint):
        if '/commits/' in endpoint: return {'sha': 'b' * 40}
        if '/pulls?' in endpoint:
            return [{'number': 12, 'title': 'Fix texture race $(do-not-execute) <script>',
                     'head': {'sha': 'c' * 40}, 'labels': [{'name': 'memory'}], 'body': 'private-looking arbitrary text'}]
        return {'private': False, 'license': {'spdx_id': 'MIT'}}

    def test_only_whitelisted_metadata_is_returned(self):
        state = m.collect(CONFIG, {}, self.api)
        self.assertFalse(state['automatic_code_integration'])
        source = state['observations'][0]
        self.assertEqual(source['observed_sha'], 'b' * 40)
        self.assertEqual(source['pull_candidates'][0]['areas'], ['correctness', 'memory', 'textures'])
        self.assertNotIn('do-not-execute', str(state)); self.assertNotIn('private-looking', str(state))

    def test_private_source_is_never_followed(self):
        calls = []
        def private(endpoint): calls.append(endpoint); return {'private': True}
        source = m.collect(CONFIG, {}, private)['observations'][0]
        self.assertEqual(calls, ['repos/public/source'])
        self.assertEqual(source['status'], 'unavailable-no-integration')
        self.assertEqual(source['observed_sha'], SHA)

    def test_unavailable_branch_retains_known_state(self):
        previous = m.collect(CONFIG, {}, self.api)
        def failed(endpoint): raise OSError('untrusted diagnostic that must not be published')
        source = m.collect(CONFIG, previous, failed)['observations'][0]
        self.assertEqual(source['observed_sha'], 'b' * 40)
        self.assertNotIn('untrusted diagnostic', str(source))

    def test_invalid_repo_is_rejected_before_network(self):
        config = {'sources': [{'repo': '../secrets', 'ref': 'main', 'reviewed_sha': SHA}]}
        with self.assertRaisesRegex(ValueError, 'configured upstream'): m.collect(config, {}, self.api)


if __name__ == '__main__': unittest.main()
