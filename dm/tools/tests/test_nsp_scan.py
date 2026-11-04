"""Internal metadata grouping. All records and containers are synthetic."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('build_ipa_from_nsp', REPO / 'scripts/build_ipa_from_nsp.py')
if spec is None or spec.loader is None: raise ImportError('build_ipa_from_nsp')
nsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(nsp)
APP = 0x01007EF00011E000


def record(kind='Application', version=0, app=APP):
    title = app if kind == 'Application' else app + (0x800 if kind == 'Patch' else 0x1001)
    return {'type': kind, 'title_id': f'{title:016X}', 'application_id': f'{app:016X}',
            'patch_id': f'{app + 0x800:016X}' if kind == 'Application' else None,
            'version': version, 'metadata_sha256': ('a' if kind == 'Application' else 'b') * 64}


class Scan(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        self.tmp, self.records, self.seen = Path(td.name), {}, []
        cm = mock.patch.object(nsp, 'say'); cm.start(); self.addCleanup(cm.stop)

    def package(self, name, *records):
        p = self.tmp / name
        p.write_bytes(bytes(0x100) + b'HEAD' if p.suffix.lower() in ('.xci', '.xcz') else b'PFS0' + bytes(0x100))
        self.records[p] = list(records)
        return p

    def inspect(self, p):
        self.seen.append(p)
        return copy.deepcopy(self.records[p])

    def scan(self): return nsp.scan_nsps(self.tmp, self.inspect)

    def test_wrong_filename_cannot_turn_base_into_update(self):
        base = self.package('wrong [01007EF00011E800][BASE].XCI', record())
        update = self.package('arbitrary.NSP', record('Patch', 1114112))
        app, fam = self.scan()
        self.assertEqual(app, APP)
        self.assertEqual(fam, {'base': base, 'updates': [(1114112, update)], 'dlc': []})
        self.assertEqual(nsp.nsp_versions(fam, {}), {'v0': None, 'v1114112': update})

    def test_missing_package_version_is_not_guessed_from_profile(self):
        fam = {'base': Path('base.nsp'), 'updates': [(None, Path('update [v999].nsp'))], 'dlc': []}
        with self.assertRaisesRegex(nsp.BuildError, 'internal package version'):
            nsp.nsp_versions(fam, {'v999': {}})

    def test_bundled_cartridge_base_update_and_dlc(self):
        p = self.package('card.xci', record(), record('Patch', 1114112), record('AddOnContent', 65536))
        self.assertEqual(self.scan()[1], {'base': p, 'updates': [(1114112, p)], 'dlc': [(APP + 0x1001, 65536, p)]})

    def test_update_only_is_not_a_base(self):
        self.package('fake [BASE].nsp', record('Patch', 1114112))
        with self.assertRaisesRegex(nsp.BuildError, 'Patch is not a base'): self.scan()

    def test_parent_association_not_low_title_bits(self):
        self.package('base.nsp', record())
        self.package('patch.nsp', record('Patch', 1114112, APP + 0x2000))
        with self.assertRaisesRegex(nsp.BuildError, 'mismatch'): self.scan()

    def test_patch_must_match_application_patch_id(self):
        self.package('base.nsp', record())
        wrong = record('Patch', 1114112); wrong['title_id'] = f'{APP + 0x900:016X}'
        self.package('update.nsp', wrong)
        with self.assertRaisesRegex(nsp.BuildError, 'patch ID'): self.scan()

    def test_ambiguous_base_versions_rejected(self):
        self.package('one.nsp', record()); self.package('two.nsp', record(version=65536))
        with self.assertRaisesRegex(nsp.BuildError, 'expected one base'): self.scan()

    def test_identical_metadata_prefers_uncompressed_after_checking_both(self):
        a = self.package('a.nsz', record()); b = self.package('different.nsp', record())
        self.assertEqual(self.scan()[1]['base'], b)
        self.assertCountEqual(self.seen, [a, b])

    def test_conflicting_same_version_is_not_chosen_by_size(self):
        self.package('base.nsp', record())
        other = record(); other['metadata_sha256'] = 'c' * 64
        self.package('bigger.nsp', other)
        with self.assertRaisesRegex(nsp.BuildError, 'conflicting'): self.scan()

    def test_failed_metadata_is_never_replaced_by_filename_guess(self):
        self.package('Game [01007EF00011E000][v0].nsp', record())
        with self.assertRaisesRegex(nsp.BuildError, 'required'): nsp.scan_nsps(self.tmp)
        with self.assertRaisesRegex(nsp.BuildError, 'bad metadata'):
            nsp.scan_nsps(self.tmp, lambda p: (_ for _ in ()).throw(nsp.BuildError('bad metadata')))

    def test_invalid_metadata_rejected(self):
        p = self.package('base.nsp', record())
        for name, value in [('title_id', 'wrong'), ('version', True), ('version', -1), ('metadata_sha256', 'x')]:
            with self.subTest(name=name, value=value):
                bad = record(); bad[name] = value; self.records[p] = [bad]
                with self.assertRaisesRegex(nsp.BuildError, 'invalid internal'): self.scan()

    def test_appledouble_empty_and_nonpackages_not_inspected(self):
        base = self.package('valid.nsp', record())
        (self.tmp / '._valid.nsp').write_bytes(bytes(4096))
        (self.tmp / 'empty.nsp').touch()
        (self.tmp / 'page [01007EF00011E000].nsp').write_bytes(b'<html>missing</html>')
        self.assertEqual(self.scan()[1]['base'], base); self.assertEqual(self.seen, [base])

    def test_inspector_rejects_wrong_schema(self):
        result = mock.Mock(returncode=0, stdout='{"schema":9}', stderr='')
        with mock.patch.object(nsp.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(nsp.BuildError, 'invalid package'): nsp.inspect_package('nx', 'private.keys', Path('base.nsp'), {})


if __name__ == '__main__': unittest.main()
