#!/usr/bin/env python3
"""Read only controller-font/layout metadata from the owner's private build data.

Downloads verified release chunks to a temporary directory, never publishes game
content, and prints only texture names, dimensions, formats and glyph indices.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile


def yaz0(data):
    if data[:4] != b'Yaz0': return data
    size = struct.unpack_from('>I', data, 4)[0]
    if size > 64 << 20: raise ValueError('archive too large')
    out, at = bytearray(), 16
    while len(out) < size:
        code = data[at]; at += 1
        for bit in range(8):
            if len(out) == size: break
            if code & (128 >> bit): out.append(data[at]); at += 1
            else:
                a, b = data[at:at + 2]; at += 2
                count = a >> 4
                if count: count += 2
                else: count = data[at] + 18; at += 1
                back = ((a & 15) << 8 | b) + 1
                if back > len(out) or len(out) + count > size: raise ValueError('invalid Yaz0 copy')
                for _ in range(count): out.append(out[-back])
    return bytes(out)


def members(data):
    if data[:4] != b'SARC' or data[6:8] != b'\xff\xfe': raise ValueError('not little-endian SARC')
    base = struct.unpack_from('<I', data, 12)[0]
    count = struct.unpack_from('<H', data, 26)[0]; names = 40 + count * 16
    result = {}
    for k in range(count):
        _, attr, a, b = struct.unpack_from('<4I', data, 32 + k * 16)
        p = names + (attr & 0xffffff) * 4; end = data.index(0, p)
        if base + b > len(data) or a > b: raise ValueError('SARC member bounds')
        result[data[p:end].decode()] = data[base + a:base + b]
    return result


def textures(data):
    if data[:4] != b'BNTX': raise ValueError('not BNTX')
    count = struct.unpack_from('<I', data, 0x24)[0]
    table = struct.unpack_from('<Q', data, 0x28)[0]
    if count > 4096: raise ValueError('texture count')
    out = []
    for i in range(count):
        p = struct.unpack_from('<Q', data, table + i * 8)[0]
        if data[p:p + 4] != b'BRTI': raise ValueError('BRTI pointer')
        n = struct.unpack_from('<Q', data, p + 0x60)[0]
        length = struct.unpack_from('<H', data, n)[0]
        ptrs = struct.unpack_from('<Q', data, p + 0x70)[0]
        offset = struct.unpack_from('<Q', data, ptrs)[0]
        out.append({'name': data[n + 2:n + 2 + length].decode().rstrip('\0'),
                    'width': struct.unpack_from('<I', data, p + 0x24)[0],
                    'height': struct.unpack_from('<I', data, p + 0x28)[0],
                    'format': hex(struct.unpack_from('<I', data, p + 0x1c)[0]),
                    'tile_mode': struct.unpack_from('<H', data, p + 0x12)[0],
                    'mips': struct.unpack_from('<H', data, p + 0x16)[0],
                    'block_height_log2': struct.unpack_from('<I', data, p + 0x34)[0] & 7,
                    'data_offset': offset, 'container_bytes': len(data)})
    return out


class RemoteImage:
    def __init__(self, repo, tag, directory):
        self.repo, self.directory = repo, directory
        self.download(tag, 'manifest.json')
        manifest = json.loads((directory / 'manifest.json').read_text())
        self.entry = next(f for f in manifest['files'] if f['path'] == 'romfs.img')
        self.tag = self.entry.get('source_tag', tag)
        self.parts = []; offset = 0
        for part in self.entry['parts']:
            self.parts.append((offset, offset + part['size'], part)); offset += part['size']
        if offset != self.entry['size']: raise ValueError('image part sizes')

    def download(self, tag, asset):
        if Path(asset).name != asset: raise ValueError('asset name')
        subprocess.run(['gh', 'release', 'download', tag, '--repo', self.repo, '--pattern', asset,
                        '--dir', str(self.directory)], check=True, stdout=subprocess.DEVNULL)

    def read(self, offset, size):
        result = bytearray()
        for a, b, part in self.parts:
            lo, hi = max(a, offset), min(b, offset + size)
            if lo >= hi: continue
            path = self.directory / part['asset']
            if not path.exists():
                self.download(self.tag, part['asset'])
                with path.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
                if path.stat().st_size != part['size'] or digest != part['sha256']: raise ValueError('chunk digest mismatch')
            with path.open('rb') as f: f.seek(lo - a); result += f.read(hi - lo)
        if len(result) != size: raise ValueError('image range')
        return bytes(result)

    def paths(self):
        magic, offset, size, count = struct.unpack('<8sQQQ', self.read(0, 32))
        if magic != b'DMROMFS1' or size > 64 << 20 or count > size // 24: raise ValueError('image index')
        data = self.read(offset, size); rows = [struct.unpack_from('<QQIHBB', data, i * 24) for i in range(count)]
        paths = {0: ''}; files = {}
        for i, (a, b, _, _, kind, _) in enumerate(rows):
            if kind: files[paths[i]] = (a, b); continue
            for j in range(a, a + b):
                no, length = rows[j][2:4]; name = data[count * 24 + no:count * 24 + no + length].decode()
                paths[j] = paths[i] + ('/' if paths[i] else '') + name
        return files


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--repo', required=True); p.add_argument('--tag', required=True)
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        image = RemoteImage(args.repo, args.tag, Path(d)); files = image.paths(); out = {}
        packed = image.read(*files['Font/Font_EU.sbfarc'])
        font = members(yaz0(packed))['External_00.bffnt']; t = font.index(b'TGLP')
        sheet = struct.unpack_from('<I', font, t + 0x1c)[0]
        out['font'] = {'cell': list(font[t + 8:t + 12]), 'grid': list(struct.unpack_from('<4H', font, t + 0x14)),
                       'textures': textures(font[sheet:])}
        k = struct.unpack_from('<H', font, 6)[0]
        while k + 24 <= len(font):
            if font[k:k + 4] == b'CMAP':
                lo, hi, method = struct.unpack_from('<IIH', font, k + 8)
                if method == 1:
                    out['font']['face_indices'] = [struct.unpack_from('<H', font, k + 24 + 2 * (cp - lo))[0] for cp in range(0xe040, 0xe044) if lo <= cp <= hi]
                break
            size = struct.unpack_from('<I', font, k + 4)[0]
            if size < 8: raise ValueError('font block size')
            k += size
        boot = members(image.read(*files['Pack/Bootup.pack']))
        common = members(yaz0(boot['Layout/Common.sblarc'])); out['layout_textures'] = {}
        layout = common['blyt/PaDoCommandA_00.bflyt']; k = struct.unpack_from('<H', layout, 6)[0]
        out['layout_fonts'] = []; out['layout_text'] = []
        while k + 8 <= len(layout):
            magic, size = layout[k:k + 4], struct.unpack_from('<I', layout, k + 4)[0]
            if size < 8: raise ValueError('layout block')
            if magic == b'fnl1':
                count = struct.unpack_from('<H', layout, k + 8)[0]
                for i in range(count):
                    p = k + 12 + struct.unpack_from('<I', layout, k + 12 + 4 * i)[0]
                    out['layout_fonts'].append(layout[p:layout.index(0, p)].decode())
            if magic == b'txt1':
                out['layout_text'].append({'name': layout[k + 12:k + 36].split(b'\0')[0].decode(),
                                          'font_index': struct.unpack_from('<H', layout, k + 0x5a)[0]})
            k += size
        for name, body in common.items():
            if body[:4] == b'BNTX':
                matches = [v for v in textures(body) if v['name'].startswith(('Nt_KeyTex', 'Nt_KeyBtn'))]
                if matches: out['layout_textures'][name] = matches
        print(json.dumps(out, indent=2))


if __name__ == '__main__': main()
