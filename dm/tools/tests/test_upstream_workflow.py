"""Execute the workflow's actual branch guard against GitHub CLI responses."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

REPO = Path(__file__).resolve().parents[3]


class BranchGuard(unittest.TestCase):
    def check_guard(self, *, exists=False, number='', files='docs/upstream-observations.json', sha='a' * 40):
        workflow = (REPO / '.github/workflows/upstream.yml').read_text()
        start = workflow.index('          branch="automation/upstream-observations"')
        end = workflow.index('          git switch -c "$branch"', start)
        script = textwrap.dedent(workflow[start:end]) + 'printf "ready:%s\\n" "$old"\n'
        with tempfile.TemporaryDirectory() as td:
            gh = Path(td) / 'gh'
            gh.write_text('#!/bin/sh\n'
                          'case "$1 $2" in\n'
                          '  "pr list") printf "%s\\n" "$TEST_PR";;\n'
                          '  "pr view") printf "%s\\n" "$TEST_FILES";;\n'
                          '  "api "*) if [ "$TEST_EXISTS" = 1 ]; then printf "%s\\n" "$TEST_SHA"; else '
                          'printf \'{"message":"Not Found","status":"404"}\\n\'; exit 1; fi;;\n'
                          '  *) exit 99;;\nesac\n')
            gh.chmod(0o755)
            env = dict(os.environ, PATH=td + os.pathsep + os.environ.get('PATH', ''),
                       GITHUB_REPOSITORY='example/repo', TEST_EXISTS='1' if exists else '0',
                       TEST_PR=number, TEST_FILES=files, TEST_SHA=sha)
            return subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
                                  env=env, capture_output=True, text=True)

    def test_absent_branch_error_json_is_not_an_existing_ref(self):
        result = self.check_guard()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stdout.strip(), 'ready:')

    def test_existing_branch_without_an_open_proposal_is_preserved(self):
        result = self.check_guard(exists=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('without an open bot PR', result.stdout)

    def test_existing_observation_only_proposal_can_be_refreshed(self):
        result = self.check_guard(exists=True, number='2')
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(result.stdout.strip(), 'ready:' + 'a' * 40)

    def test_manual_source_edits_are_never_overwritten(self):
        result = self.check_guard(exists=True, number='2', files='docs/upstream-observations.json\ndm/host/loader.c')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('manual source edits', result.stdout)

    def test_invalid_ref_is_not_used_as_a_lease(self):
        result = self.check_guard(exists=True, number='2', sha='unexpected API output')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Invalid observation branch hash', result.stdout)


if __name__ == '__main__': unittest.main()
