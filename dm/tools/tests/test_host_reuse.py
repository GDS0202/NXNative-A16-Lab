"""Recover the actual gen_embed layout from synthetic arm64 Mach-O sections."""
import importlib.util
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('rebuild_host', ROOT / 'scripts/rebuild_host.py')
if spec is None or spec.loader is None: raise ImportError('rebuild_host')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)


def image(path, parts):
    commands = bytearray()
    for seg, sect, offset, payload in parts:
        cmd = struct.pack('<II16sQQQQIIII', 0x19, 152, seg.encode(), 0, len(payload), offset, len(payload), 7, 5, 1, 0)
        sec = struct.pack('<16s16sQQIIIIIIII', sect.encode(), seg.encode(), 0, len(payload), offset, 14, 0, 0, 0, 0, 0, 0)
        commands += cmd + sec
    size = max(offset + len(payload) for _, _, offset, payload in parts)
    data = bytearray(size)
    data[:32] = struct.pack('<8I', 0xfeedfacf, 0x0100000c, 0, 2, len(parts), len(commands), 0, 0)
    data[32:32 + len(commands)] = commands
    for _, _, offset, payload in parts: data[offset:offset + len(payload)] = payload
    path.write_bytes(data)


class Reuse(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)

    def roundtrip(self, front):
        exe, table = self.root / 'exe', self.root / 'main.fixups.tsv'
        table.write_text('# TEXT_END 0x4000\n# PATCH_OFF ' + ('-0x4000' if front else '0xc000') +
                         '\n# KEY_PAGE_OFF 0x8000\n# KEY_PAGE_SIZE 0x4000\n# BUILD_ID ' + 'a' * 32 +
                         ('\n# FILE_IMAGE_LEN 0x8000\n# IMAGE_SIZE 0xc000\n' if front else '\n'))
        payload = [b'A' * r.PAGE, b'B' * r.PAGE * (1 if front else 2), b'C' * r.PAGE]
        parts = [('__TEXT', '__dmmainx0', 0x4000, payload[0]),
                 ('__DMmainW', '__img', 0x8000, payload[1]),
                 ('__TEXT', '__dmmainx1', 0x10000, payload[2])]
        image(exe, parts)
        recovered = self.root / 'main.patched.bin'
        r.recover_module(exe, r.macho_sections(exe), 'main', table, recovered)
        self.assertEqual(recovered.read_bytes(), b''.join(payload))
        # Different host/section offsets must not change any guest byte.
        image(self.root / 'newexe', [(seg, sec, off + 0x4000, data) for seg, sec, off, data in parts])
        r.recover_module(self.root / 'newexe', r.macho_sections(self.root / 'newexe'), 'main', table, self.root / 'again.bin')
        self.assertEqual(r.digest_file(recovered), r.digest_file(self.root / 'again.bin'))
        return exe, table

    def test_trailing_patch_roundtrip(self): self.roundtrip(False)
    def test_front_patch_roundtrip(self): self.roundtrip(True)

    def test_malformed_layout_and_section_bounds_fail_closed(self):
        exe, table = self.roundtrip(False)
        sections = r.macho_sections(exe)
        sections['__TEXT', '__dmmainx1'] = (exe.stat().st_size, r.PAGE, 0)
        with self.assertRaisesRegex(ValueError, 'complete regular'):
            r.recover_module(exe, sections, 'main', table, self.root / 'bad.bin')
        self.assertFalse((self.root / 'bad.bin').exists())
        sections = r.macho_sections(exe); del sections['__TEXT', '__dmmainx1']
        with self.assertRaisesRegex(ValueError, 'missing embedded'):
            r.recover_module(exe, sections, 'main', table, self.root / 'bad.bin')
        table.write_text(table.read_text().replace('0xc000', '0xc001'))
        with self.assertRaisesRegex(ValueError, 'alignment'):
            r.recover_module(exe, r.macho_sections(exe), 'main', table, self.root / 'bad.bin')

    def test_truncated_and_non_arm64_macho_rejected(self):
        path = self.root / 'short'; path.write_bytes(b'not a macho')
        with self.assertRaisesRegex(ValueError, 'truncated'): r.macho_sections(path)
        path.write_bytes(struct.pack('<8I', 0xfeedfacf, 7, 0, 2, 1, 4, 0, 0))
        with self.assertRaisesRegex(ValueError, 'thin arm64'): r.macho_sections(path)

    def test_ipa_paths_links_and_duplicates_are_rejected(self):
        for name in ('../escape', '/Payload/a.app/Info.plist', 'Payload/a.app/../../escape', 'Unexpected/data'):
            path = self.root / 'bad.ipa'
            with zipfile.ZipFile(path, 'w') as z: z.writestr(name, b'x')
            with self.assertRaises(ValueError): r.unpack_ipa(path, self.root / 'unpacked')
            self.assertFalse((self.root / 'unpacked').exists())
        path = self.root / 'link.ipa'
        with zipfile.ZipFile(path, 'w') as z:
            info = zipfile.ZipInfo('Payload/a.app/link'); info.external_attr = 0o120777 << 16; z.writestr(info, '/private')
        with self.assertRaisesRegex(ValueError, 'symlinked'): r.unpack_ipa(path, self.root / 'unpacked')

    def test_shader_stamps_are_preserved_not_restamped(self):
        app = self.root / 'a.app'; lib = app / 'msl/b-abcdef'; lib.mkdir(parents=True); (app / 'dm').mkdir()
        stamp = lib / 'inputs.tsv'; stamp.write_text('game\t01007EF00011E000\ninputs\t123456789abc\n')
        (lib / 'x_b.metallib').write_bytes(b'synthetic')
        for name in ('c1_full.tsv', 'cb_extent.tsv'):
            (app / 'dm' / name).write_text('# chain b-abcdef inputs 123456789abc synthetic\n')
        self.assertEqual(r.verify_shader_snapshot(app, '01007EF00011E000', 'abcdef'), '123456789abc')
        before = stamp.read_bytes()
        (app / 'dm/c1_full.tsv').write_text('# chain b-abcdef inputs aaaaaaaaaaaa wrong\n')
        with self.assertRaisesRegex(ValueError, 'never restamp'): r.verify_shader_snapshot(app, '01007EF00011E000', 'abcdef')
        self.assertEqual(stamp.read_bytes(), before)

    def test_launcher_uses_build_api_and_keeps_actual_language_choices(self):
        tables = self.root / 'dm'; tables.mkdir()
        patched = self.root / 'patched'; patched.mkdir()
        language = {'env': 'DM_LANG', 'default': 'it', 'choices': [{'value': 'it', 'label': 'Italian'}]}
        (tables / 'launcher.json').write_text(json.dumps({'settings': [language]}))
        target = self.root / 'launcher.json'
        with patch.dict(os.environ, {'GFXAPI': 'gl', 'DM_SHOW_FPS': 'NO'}):
            env = dict(os.environ, GFXAPI='nvn', SETTINGS_PLATFORM='ios', DM_SHOW_FPS='YES')
            r.regenerate_launcher('01007EF00011E000', patched, tables, target, env)
        rows = {row['env']: row for row in json.loads(target.read_text())['settings']}
        self.assertIn('DM_STUTTER', rows)
        self.assertIn('DM_BC_WORKERS', rows)
        self.assertEqual(rows['DM_SHOW_FPS']['default'], '1')
        self.assertEqual(rows['DM_LANG'], language)
        self.assertEqual(target.read_bytes(), (tables / 'launcher.json').read_bytes())


if __name__ == '__main__': unittest.main()
