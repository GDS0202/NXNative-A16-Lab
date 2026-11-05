"""Generate BOTW 1.9.0 button assets from the player's own RomFS.

No game assets or external fonts are shipped. The app's physical-position map
is Nintendo A=east, B=south, X=north, Y=west. Generated assets follow that map.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile

import botw_icon_layout as layout
import romfs

BUILD = 'cd57b23fa4bbad65803d9788c01821ee'
FORMAT = 'nxnative-controller-icons-v1'
FACE = {0xe040: 'east', 0xe041: 'south', 0xe042: 'north', 0xe043: 'west'}
LETTERS = {'east': 'B', 'south': 'A', 'north': 'Y', 'west': 'X'}
SYMBOLS = {'east': 'circle', 'south': 'cross', 'north': 'triangle', 'west': 'square'}
BITMAP = {
    'A': ('01110','10001','10001','11111','10001','10001','10001'),
    'B': ('11110','10001','10001','11110','10001','10001','11110'),
    'X': ('10001','10001','01010','00100','01010','10001','10001'),
    'Y': ('10001','10001','01010','00100','00100','00100','00100'),
    'L': ('10000','10000','10000','10000','10000','10000','11111'),
    'R': ('11110','10001','10001','11110','10100','10010','10001'),
    'T': ('11111','00100','00100','00100','00100','00100','00100'),
    '1': ('00100','01100','00100','00100','00100','00100','01110'),
    '2': ('01110','10001','00001','00010','00100','01000','11111'),
    '3': ('11110','00001','00001','01110','00001','00001','11110'),
}


def yaz0(data):
    if data[:4] != b'Yaz0': return data
    size = struct.unpack_from('>I', data, 4)[0]
    if size > 64 << 20: raise ValueError('Yaz0 archive exceeds 64 MiB')
    out, at = bytearray(), 16
    while len(out) < size:
        flags = data[at]; at += 1
        for bit in range(8):
            if len(out) == size: break
            if flags & (128 >> bit): out.append(data[at]); at += 1
            else:
                a, b = data[at:at + 2]; at += 2
                count = a >> 4
                if count: count += 2
                else: count = data[at] + 18; at += 1
                back = ((a & 15) << 8 | b) + 1
                if back > len(out) or len(out) + count > size: raise ValueError('invalid Yaz0 back reference')
                for _ in range(count): out.append(out[-back])
    return bytes(out)


def names(data):
    if data[:4] != b'SARC': raise ValueError('expected SARC')
    count = struct.unpack_from('<H', data, 26)[0]; base = 40 + count * 16
    result = []
    for i in range(count):
        attr = struct.unpack_from('<I', data, 36 + i * 16)[0]
        at = base + (attr & 0xffffff) * 4
        result.append(data[at:data.index(0, at)].decode())
    return result


def bntx_textures(data):
    if data[:4] != b'BNTX': raise ValueError('expected BNTX')
    count, table = struct.unpack_from('<I', data, 0x24)[0], struct.unpack_from('<Q', data, 0x28)[0]
    if not 0 < count <= 4096: raise ValueError('BNTX texture count')
    out = []
    for i in range(count):
        p = struct.unpack_from('<Q', data, table + i * 8)[0]
        if data[p:p + 4] != b'BRTI': raise ValueError('BNTX texture pointer')
        n = struct.unpack_from('<Q', data, p + 0x60)[0]; length = struct.unpack_from('<H', data, n)[0]
        ptr = struct.unpack_from('<Q', data, p + 0x70)[0]; offset = struct.unpack_from('<Q', data, ptr)[0]
        w, h = struct.unpack_from('<II', data, p + 0x24)
        fmt = struct.unpack_from('<I', data, p + 0x1c)[0]
        tile = struct.unpack_from('<H', data, p + 0x12)[0]
        bh = struct.unpack_from('<I', data, p + 0x34)[0] & 7
        out.append({'name': data[n + 2:n + 2 + length].decode().rstrip('\0'), 'width': w, 'height': h,
                    'format': fmt, 'tile': tile, 'bh': 1 << bh, 'offset': offset,
                    'mips': struct.unpack_from('<H', data, p + 0x16)[0]})
    return out


def gob(x, y, width_bytes, bh):
    """Tegra X1 block-linear byte address; x is a byte coordinate."""
    width_gobs = (width_bytes + 63) // 64
    return ((y // (8 * bh)) * 512 * bh * width_gobs + (x // 64) * 512 * bh +
            (y % (8 * bh) // 8) * 512 + (x % 64 // 32) * 256 + (y % 8 // 2) * 64 +
            (x % 32 // 16) * 32 + (y % 2) * 16 + x % 16)


def bc4_decode(block):
    a, b = block[:2]
    palette = [a, b] + ([(a * (7 - i) + b * i) // 7 for i in range(1, 7)] if a > b else
                        [(a * (5 - i) + b * i) // 5 for i in range(1, 5)] + [0, 255])
    indices = int.from_bytes(block[2:8], 'little')
    return [palette[(indices >> (3 * i)) & 7] for i in range(16)]


def bc4_encode(pixels):
    a, b = max(pixels), min(pixels)
    palette = [a, b] + ([(a * (7 - i) + b * i) // 7 for i in range(1, 7)] if a > b else [a] * 6)
    bits = 0
    for i, value in enumerate(pixels): bits |= min(range(8), key=lambda j: abs(palette[j] - value)) << (3 * i)
    return bytes((a, b)) + bits.to_bytes(6, 'little')


def paint(data, texture, changes):
    """Change only named R8/BC4 mip-zero pixels, preserving size and all other textures."""
    w, h, fmt, bh = (texture[k] for k in ('width', 'height', 'format', 'bh'))
    if fmt not in (0x201, 0x1d01) or texture['mips'] != 1 or texture['tile'] != 0 or bh > 32:
        raise ValueError(f'unsupported glyph texture: {texture["name"]}')
    out = bytearray(data); blocks = {}
    for (x, y), value in changes.items():
        if not (0 <= x < w and 0 <= y < h and 0 <= value <= 255): raise ValueError('glyph pixel bounds')
        if fmt == 0x201:
            offset = texture['offset'] + gob(x, y, w, bh)
            if offset >= len(out): raise ValueError('R8 texture bounds')
            out[offset] = value
        else:
            offset = texture['offset'] + gob(x // 4 * 8, y // 4, (w + 3) // 4 * 8, bh)
            if offset + 8 > len(out): raise ValueError('BC4 texture bounds')
            if offset not in blocks: blocks[offset] = bc4_decode(out[offset:offset + 8])
            blocks[offset][(y % 4) * 4 + x % 4] = value
    for offset, pixels in blocks.items(): out[offset:offset + 8] = bc4_encode(pixels)
    return bytes(out)


def line_distance(x, y, a, b):
    ax, ay = a; bx, by = b; dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - ax - t * dx, y - ay - t * dy)


def mask(symbol, size):
    """Original monochrome controller glyphs, supersampled; no third-party font."""
    def ink(x, y):
        dx, dy = x - 25, y - 25
        if symbol == 'circle': return abs(math.hypot(dx, dy) - 14) <= 1.7
        if symbol == 'square': return abs(max(abs(dx), abs(dy)) - 13) <= 1.7
        if symbol == 'cross': return max(abs(dx), abs(dy)) <= 14 and min(abs(dx - dy), abs(dx + dy)) <= 2.5
        if symbol == 'triangle': return min(line_distance(x, y, a, b) for a, b in [((25, 9), (9, 38)), ((9, 38), (41, 38)), ((41, 38), (25, 9))]) <= 1.7
        if symbol == 'menu': return abs(dx) <= 13 and any(abs(dy - a) <= 1.5 for a in (-9, 0, 9))
        if symbol == 'view': return (abs(max(abs(x - 21), abs(y - 21)) - 10) <= 1.3 or abs(max(abs(x - 29), abs(y - 29)) - 10) <= 1.3)
        text = symbol
        scale = 3 if len(text) == 1 else 2
        left = (50 - (len(text) * 6 - 1) * scale) / 2; top = (50 - 7 * scale) / 2
        for i, ch in enumerate(text):
            cx, cy = int((x - left - i * 6 * scale) // scale), int((y - top) // scale)
            if 0 <= cx < 5 and 0 <= cy < 7 and BITMAP[ch][cy][cx] == '1': return True
        return False
    return [round(255 * sum(ink((x + (sx + .5) / 4) * 50 / size, (y + (sy + .5) / 4) * 50 / size)
                             for sy in range(4) for sx in range(4)) / 16) for y in range(size) for x in range(size)]


def font_icons(font, style):
    table, lo, hi = layout.cmap_table(font)
    t = font.index(b'TGLP'); cw, ch, sheets = font[t + 8:t + 11]
    columns, rows, width, height = struct.unpack_from('<4H', font, t + 0x14)
    start = struct.unpack_from('<I', font, t + 0x1c)[0]
    if (cw, ch, sheets, columns, rows, width, height) != (50, 50, 1, 5, 20, 256, 1024): raise ValueError('unsupported BOTW glyph atlas')
    textures = bntx_textures(font[start:])
    if len(textures) != 1 or textures[0]['format'] != 0x1d01: raise ValueError('expected single BC4 glyph sheet')
    symbols = {cp: (LETTERS if style == 'xbox' else SYMBOLS)[slot] for cp, slot in FACE.items()}
    symbols.update({0xe044: 'LB' if style == 'xbox' else 'L1', 0xe045: 'RB' if style == 'xbox' else 'R1',
                    0xe046: 'LT' if style == 'xbox' else 'L2', 0xe047: 'RT' if style == 'xbox' else 'R2',
                    0xe04b: 'menu', 0xe04c: 'view', 0xe053: 'L3', 0xe054: 'R3'})
    changes = {}
    for cp, symbol in symbols.items():
        if not lo <= cp <= hi: raise ValueError('glyph code point outside CMAP')
        index = struct.unpack_from('<H', font, table + 2 * (cp - lo))[0]
        if index >= columns * rows: raise ValueError('glyph index outside sheet')
        pixels = mask(symbol, 50); ox, oy = (index % columns) * 51, (index // columns) * 51
        for y in range(50):
            for x in range(50): changes[(ox + x, height - 1 - oy - y)] = pixels[y * 50 + x]
    changed = paint(font[start:], textures[0], changes)
    return font[:start] + changed


def playstation_layout(flyt):
    """Use the external icon font for the three unselected face-button labels."""
    sections, k = [], struct.unpack_from('<H', flyt, 6)[0]
    while k < len(flyt):
        size = struct.unpack_from('<I', flyt, k + 4)[0]
        if size < 8 or k + size > len(flyt): raise ValueError('BFLYT block bounds')
        sections.append(bytearray(flyt[k:k + size])); k += size
    fonts = []
    for block in sections:
        if block[:4] != b'fnl1': continue
        count = struct.unpack_from('<H', block, 8)[0]
        for i in range(count):
            p = 12 + struct.unpack_from('<I', block, 12 + 4 * i)[0]
            fonts.append(block[p:block.index(0, p)].decode())
    if not fonts: raise ValueError('action-guide font list missing')
    if 'External_00.bffnt' not in fonts: fonts.append('External_00.bffnt')
    font_index = fonts.index('External_00.bffnt')
    font_strings = bytearray(); offsets = []
    for font in fonts:
        offsets.append(4 * len(fonts) + len(font_strings)); font_strings += font.encode() + b'\0'
    font_data = struct.pack('<HH', len(fonts), 0) + struct.pack(f'<{len(fonts)}I', *offsets) + font_strings
    font_data += bytes(-len(font_data) % 4)
    labels = {ord(c): cp for c, cp in zip('ABXY', range(0xe040, 0xe044))}
    changed = 0
    for i, block in enumerate(sections):
        if block[:4] == b'fnl1': sections[i] = bytearray(b'fnl1' + struct.pack('<I', 8 + len(font_data)) + font_data)
        if block[:4] != b'txt1': continue
        name = block[12:36].split(b'\0')[0].decode()
        if name not in ('T_A_00', 'T_B_00', 'T_X_00', 'T_Y_00'): continue
        text = struct.unpack_from('<I', block, 0x64)[0]
        cp = struct.unpack_from('<H', block, text)[0]
        if cp not in labels: raise ValueError('unexpected action-guide label')
        struct.pack_into('<H', block, text, labels[cp]); struct.pack_into('<H', block, 0x5a, font_index); changed += 1
    if changed != 3: raise ValueError('expected three unselected face labels')
    out = bytearray(flyt[:struct.unpack_from('<H', flyt, 6)[0]]) + b''.join(sections)
    struct.pack_into('<I', out, 12, len(out))
    return bytes(out)


def guide_icons(pack, style):
    a, b = layout.sarc_member(pack, 'Layout/Common.sblarc')
    packed = pack[a:b]; common = yaz0(packed); changed = common
    if style == 'xbox':
        changed = layout.layout_remap(changed, {'a': 'right', 'b': 'bottom', 'x': 'top', 'y': 'left'})
    else:
        for part in layout.PARTS.values():
            lo, hi = layout.sarc_member(changed, part)
            changed = layout.sarc_put(changed, part, playstation_layout(changed[lo:hi]))
    # Actual BOTW inspection: these action-guide images are R8, one mip, 48x48.
    # Changing them edits the game's own HUD, not just the app's touch overlay.
    labels = {'Nt_KeyTexL_00^d': 'LB' if style == 'xbox' else 'L1',
              'Nt_KeyTexZL_00^d': 'LT' if style == 'xbox' else 'L2'}
    if style == 'playstation': labels.update({'Nt_KeyTex' + c + '_00^d': SYMBOLS[slot] for c, slot in zip('ABXY', ('east','south','north','west'))})
    found = set()
    for name in names(changed):
        if not name.endswith('.bntx'): continue
        lo, hi = layout.sarc_member(changed, name); texture_data = changed[lo:hi]
        for texture in bntx_textures(texture_data):
            symbol = labels.get(texture['name'])
            if symbol is None: continue
            w, h = texture['width'], texture['height']
            if w != h or w > 256: raise ValueError('unexpected HUD glyph dimensions')
            pixels = mask(symbol, w)
            texture_data = paint(texture_data, texture, {(x, h - 1 - y): pixels[y * w + x] for y in range(h) for x in range(w)})
            found.add(texture['name'])
        changed = changed[:lo] + texture_data + changed[hi:]
    if found != set(labels): raise ValueError('required action-guide glyph textures missing')
    # The PS font list adds a few bytes to each layout. The literal Yaz0 form
    # avoids guessed back-reference relocation; decompressed bounds stay explicit.
    compressed = layout.yaz0_patch(packed, common, changed) if len(common) == len(changed) else layout.yaz0_stored(changed, struct.unpack_from('>I', packed, 8)[0])
    return layout.sarc_put(pack, 'Layout/Common.sblarc', compressed)


class Source:
    def __init__(self, root):
        self.root = Path(root); self.image = romfs.Image(root) if self.root.is_file() else None
    def read(self, name):
        if self.image is None: return (self.root / name).read_bytes()
        a, size, _, _, kind, _ = self.image.entry(self.image.find(name))
        if not kind or size > 64 << 20: raise ValueError('resource size')
        with self.root.open('rb') as f: f.seek(a); out = f.read(size)
        if len(out) != size: raise ValueError('truncated resource')
        return out
    def fonts(self):
        names = [name for name, _ in self.image.children(self.image.find('Font'))] if self.image else [p.name for p in (self.root / 'Font').iterdir()]
        return ['Font/' + n for n in sorted(names) if n.startswith('Font_') and n.endswith('.sbfarc') and '/' not in n and '\\' not in n]


def generate(source, output, build_id):
    if build_id.lower() != BUILD: raise ValueError('controller assets require the verified BOTW 1.9.0 build')
    src = Source(source); output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        marker = output / 'generation.json'
        if not marker.is_file() or json.loads(marker.read_text()).get('format') != FORMAT: raise ValueError('refusing to replace a non-generated folder')
    fonts = src.fonts()
    if not fonts: raise ValueError('no BOTW font archives')
    # Validate and build everything before replacing an earlier working generation.
    with tempfile.TemporaryDirectory(prefix='.controller-icons-', dir=output.parent) as temporary:
        root = Path(temporary) / 'ControllerIcons'; root.mkdir()
        font_cache = {}
        for style in ('xbox', 'playstation'):
            records = []
            for name in fonts:
                packed = src.read(name); sarc = yaz0(packed); a, b = layout.sarc_member(sarc, 'External_00.bffnt')
                key = (style, hashlib.sha256(sarc[a:b]).digest())
                if key not in font_cache: font_cache[key] = font_icons(sarc[a:b], style)
                changed = sarc[:a] + font_cache[key] + sarc[b:]
                asset = layout.yaz0_patch(packed, sarc, changed)
                dest = root / style / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(asset)
                records.append({'path': name, 'sha256': hashlib.sha256(asset).hexdigest()})
            packed = src.read('Pack/Bootup.pack')
            asset = guide_icons(packed, style)
            dest = root / style / 'Pack/Bootup.pack'; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(asset)
            records.append({'path': 'Pack/Bootup.pack', 'sha256': hashlib.sha256(asset).hexdigest()})
            (root / style / 'icons.json').write_text(json.dumps({'format': FORMAT, 'build_id': BUILD, 'style': style, 'mapping': 'physical-position', 'files': records}, indent=2) + '\n')
        (root / 'generation.json').write_text(json.dumps({'format': FORMAT, 'build_id': BUILD}) + '\n')
        if output.exists(): shutil.rmtree(output)
        os.replace(root, output)
    return len(fonts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--romfs', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build-id', required=True); args = parser.parse_args()
    count = generate(args.romfs, args.out, args.build_id)
    print(f'Controller icons: {count} own font archives and the action-guide layout, Xbox / PlayStation')


if __name__ == '__main__': main()
