"""Own synthetic SARC/BFFNT/BNTX layouts: no game assets or keys."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'dm/tools'))
import controller_icons as icons


def sarc(members):
    names, data, nodes = bytearray(), bytearray(), bytearray()
    for name, body in members.items():
        nodes += struct.pack('<IIII', 0, 0x01000000 | len(names) // 4, len(data), len(data) + len(body))
        names += name.encode() + b'\0'; names += bytes(-len(names) % 4)
        data += body; data += bytes(-len(data) % 4)
    head = b'SFAT' + struct.pack('<HHI', 12, len(members), 0x65) + nodes + b'SFNT' + struct.pack('<HH', 8, 0) + names
    start = 0x14 + len(head); start += -start % 16
    return (b'SARC' + struct.pack('<H', 0x14) + b'\xff\xfe' + struct.pack('<IIHH', start + len(data), start, 0x100, 0) +
            head + bytes(start - 0x14 - len(head)) + data)


def bntx(name='0', width=256, height=1024, fmt=0x1d01, bh=4):
    out = bytearray(0x1000 + (131072 if fmt == 0x1d01 else 8192))
    out[:4] = b'BNTX'; struct.pack_into('<I', out, 0x24, 1); struct.pack_into('<Q', out, 0x28, 0x60)
    struct.pack_into('<Q', out, 0x60, 0x80); out[0x80:0x84] = b'BRTI'
    struct.pack_into('<H', out, 0x80 + 0x16, 1); struct.pack_into('<I', out, 0x80 + 0x1c, fmt)
    struct.pack_into('<II', out, 0x80 + 0x24, width, height); struct.pack_into('<I', out, 0x80 + 0x34, bh)
    struct.pack_into('<Q', out, 0x80 + 0x60, 0x180); struct.pack_into('<Q', out, 0x80 + 0x70, 0x200)
    struct.pack_into('<H', out, 0x180, len(name)); out[0x182:0x182 + len(name)] = name.encode()
    struct.pack_into('<Q', out, 0x200, 0x1000)
    return bytes(out)


def font():
    lo, hi = 0xe040, 0xe070
    table = struct.pack(f'<{hi-lo+1}H', *range(hi-lo+1)); table += bytes(-len(table) % 4)
    cmap = b'CMAP' + struct.pack('<IIIHHI', 24 + len(table), lo, hi, 1, 0, 0) + table
    tglp = b'TGLP' + struct.pack('<I4BI6HI', 32, 50, 50, 1, 48, 131072, 48, 0, 5, 20, 256, 1024, 0x1000)
    head = b'FFNT\xfe\xff' + struct.pack('<HIIHH', 0x14, 0x04010000, 0, 3, 0)
    metrics = b''.join(struct.pack('<bBB', 3, 31 if i in (4, 5) else 30, 36) for i in range(hi-lo+1))
    widths = b'CWDH' + struct.pack('<IHHI', 16 + len(metrics) + (-len(metrics) % 4), 0, hi-lo, 0) + metrics + bytes(-len(metrics) % 4)
    data = head + tglp + cmap + widths
    return data + bytes(0x1000 - len(data)) + bntx()


def flyt():
    # The same pane layout as the actual format, using original synthetic labels.
    def pane(magic, name, text=None):
        body = bytes((1, 0, 255, 0)) + name.encode().ljust(24, b'\0') + bytes(8) + struct.pack('<10f', 0, 0, 0, 0, 0, 0, 1, 1, 30, 30)
        if text is not None:
            string = text.encode('utf-16-le') + b'\0\0'
            body += struct.pack('<HHHHBBHfI', len(string), len(string), 0, 0, 0, 0, 0, 0, 0x6c) + bytes(4) + string
        return magic.encode() + struct.pack('<I', 8 + len(body)) + body
    textures = [b'Nt_KeyBtnSubBaseAL_00^s\0', b'Nt_KeyTexA_00^d\0']
    txl = struct.pack('<HHII', 2, 0, 8, 8 + len(textures[0])) + b''.join(textures)
    fnl = b'fnl1' + struct.pack('<IHHI', 36, 1, 0, 4) + b'NormalS_00.bffnt\0' + bytes(4)
    # Match the declared fnl1 size to its actual padding.
    fnl = fnl[:4] + struct.pack('<I', len(fnl)) + fnl[8:]
    pas, pae = b'pas1' + struct.pack('<I', 8), b'pae1' + struct.pack('<I', 8)
    sections = [b'txl1' + struct.pack('<I', 8 + len(txl)) + txl, fnl, pane('pan1', 'RootPane'), pas,
                pane('pan1', 'N_Loop_00'), pas, pane('pic1', 'P_Base_00'),
                pane('txt1', 'T_B_00', 'B'), pane('txt1', 'T_Y_00', 'Y'), pane('txt1', 'T_X_00', 'X'),
                pane('pan1', 'N_BtnA_00'), pas, pane('wnd1', 'W_BaseA_00'), pane('txt1', 'T_GuideA_01', 'Open'), pae, pae,
                pane('pan1', 'N_CaptureA_00'), pae]
    body = b''.join(sections)
    return b'FLYT\xff\xfe' + struct.pack('<HIIHH', 0x14, 0x08000000, 0x14 + len(body), len(sections), 0) + body


class ControllerIcons(unittest.TestCase):
    def test_bumper_glyphs_fit_the_actual_cwdh_sampled_width(self):
        original = font(); self.assertEqual(icons.glyph_width(original, 4), 31)
        for symbol in ('LB', 'RB', 'L1', 'R1', 'LT', 'RT', 'L2', 'R2', 'circle', 'triangle', 'square', 'cross'):
            pixels = icons.font_mask(symbol, 31)
            self.assertTrue(any(pixels))
            self.assertFalse(any(value for i, value in enumerate(pixels) if i % 50 >= 31))
        old = icons.mask('LB', 50)
        self.assertTrue(any(value for i, value in enumerate(old) if i % 50 >= 31))
        for style in ('xbox', 'playstation'):
            changed = icons.font_icons(original, style)
            self.assertEqual(changed[:0x2000], original[:0x2000])
        missing = original.replace(b'CWDH', b'NONE', 1)
        with self.assertRaisesRegex(ValueError, 'no CWDH'): icons.font_icons(missing, 'xbox')

    def test_yaz0_roundtrip_and_invalid_reference(self):
        data = bytes(range(251)) * 11
        self.assertEqual(icons.yaz0(icons.layout.yaz0_stored(data, 4096)), data)
        changed = bytearray(data); changed[100:104] = b'TEST'
        self.assertEqual(icons.yaz0(icons.layout.yaz0_patch(icons.layout.yaz0_stored(data, 4096), data, changed)), changed)
        with self.assertRaises((ValueError, IndexError)): icons.yaz0(b'Yaz0' + struct.pack('>I', 3) + bytes(8) + bytes(3))

    def test_font_shapes_change_only_the_texture_payload(self):
        original = font(); changed = icons.font_icons(original, 'playstation')
        self.assertEqual(len(original), len(changed)); self.assertEqual(original[:0x2000], changed[:0x2000])
        self.assertNotEqual(original, changed)
        self.assertEqual(icons.layout.cmap_table(original), icons.layout.cmap_table(changed))
        self.assertNotEqual(icons.mask('circle', 48), icons.mask('cross', 48))
        self.assertNotEqual(icons.mask('triangle', 48), icons.mask('square', 48))

    def test_bc4_black_white_and_atlas_bounds(self):
        pixels = [0, 255] * 8
        self.assertEqual(icons.bc4_decode(icons.bc4_encode(pixels)), pixels)
        texture = icons.bntx_textures(bntx())[0]
        with self.assertRaises(ValueError): icons.paint(bntx(), texture, {(256, 0): 255})
        bad = dict(texture, format=0x1f01)
        with self.assertRaises(ValueError): icons.paint(bntx(), bad, {(0, 0): 255})

    def test_playstation_labels_reference_external_font_without_changing_actions(self):
        original = flyt(); changed = icons.playstation_layout(original)
        self.assertEqual(struct.unpack_from('<I', changed, 12)[0], len(changed))
        self.assertIn(b'NormalS_00.bffnt\0', changed); self.assertIn(b'External_00.bffnt\0', changed)
        self.assertIn('Open'.encode('utf-16-le'), changed)
        panes = icons.layout.flyt_panes(changed)
        for _, k, name, _ in panes:
            if name in ('T_B_00', 'T_Y_00', 'T_X_00'):
                text = struct.unpack_from('<I', changed, k + 0x64)[0]
                self.assertIn(struct.unpack_from('<H', changed, k + text)[0], range(0xe040, 0xe044))
                self.assertEqual(struct.unpack_from('<H', changed, k + 0x5a)[0], 1)

    def test_wrong_build_and_existing_user_folder_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); output = root / 'mods'; output.mkdir(); (output / 'mine').write_text('keep')
            with self.assertRaises(ValueError): icons.generate(root, output, '0' * 32)
            with self.assertRaises(ValueError): icons.generate(root, output, icons.BUILD)
            self.assertEqual((output / 'mine').read_text(), 'keep')

    def test_playstation_uses_pane_roles_instead_of_part_specific_names(self):
        original = flyt().replace(b'T_B_00', b'T_B_01').replace(b'T_Y_00', b'T_Y_01').replace(b'T_X_00', b'T_X_01')
        changed = icons.playstation_layout(original)
        labels = []
        for magic, k, name, _ in icons.layout.flyt_panes(changed):
            if magic != 'txt1': continue
            text = k + struct.unpack_from('<I', changed, k + 0x64)[0]
            if name == 'T_GuideA_01': self.assertEqual(changed[text:text + 10], 'Open\0'.encode('utf-16-le'))
            else: labels.append(struct.unpack_from('<H', changed, text)[0])
        self.assertEqual(set(labels), {0xe041, 0xe042, 0xe043})

    def test_full_synthetic_pack_generates_both_controller_styles(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); source = root / 'romfs'; (source / 'Font').mkdir(parents=True); (source / 'Pack').mkdir()
            archive = sarc({'External_00.bffnt': font()})
            (source / 'Font/Font_EU.sbfarc').write_bytes(icons.layout.yaz0_stored(archive, 4096))
            parts = {name: flyt() for name in icons.layout.PARTS.values()}
            for name in ('Nt_KeyTexA_00^d','Nt_KeyTexB_00^d','Nt_KeyTexX_00^d','Nt_KeyTexY_00^d','Nt_KeyTexL_00^d','Nt_KeyTexZL_00^d'):
                parts['timg/' + name + '.bntx'] = bntx(name, 48, 48, 0x201, 0)
            common = icons.layout.yaz0_stored(sarc(parts), 4096)
            (source / 'Pack/Bootup.pack').write_bytes(sarc({'Layout/Common.sblarc': common}))
            output = root / 'generated'
            self.assertEqual(icons.generate(source, output, icons.BUILD), 1)
            for style in ('xbox', 'playstation'):
                manifest = json.loads((output / style / 'icons.json').read_text())
                self.assertEqual(manifest['mapping'], 'physical-position')
                self.assertEqual(len(manifest['files']), 2)
                boot = (output / style / 'Pack/Bootup.pack').read_bytes()
                a, b = icons.layout.sarc_member(boot, 'Layout/Common.sblarc')
                common = icons.yaz0(boot[a:b]); a, b = icons.layout.sarc_member(common, icons.layout.PARTS['a'])
                if style == 'playstation': self.assertIn(b'External_00.bffnt\0', common[a:b])


if __name__ == '__main__': unittest.main()
