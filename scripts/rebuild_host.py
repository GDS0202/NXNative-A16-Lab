#!/usr/bin/env python3
"""Rebuild only the host of an own private, external-RomFS NVN IPA on a Mac runner.

Guest code and shader data remain private and byte-identical. This is not a
shader cache converter or a way to restamp incompatible libraries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import stat
import struct
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
PAGE = 0x4000
MAX_IMAGE = 1024**3
MAX_UNPACKED = 8 * 1024**3
SHA = re.compile('[0-9a-f]{40}')


def digest_file(path):
    h = hashlib.sha256()
    with path.open('rb') as src:
        for block in iter(lambda: src.read(8 << 20), b''): h.update(block)
    return h.hexdigest()


def macho_sections(path):
    """Bounded thin arm64 Mach-O reader; offsets and names are never executed."""
    size = path.stat().st_size
    with path.open('rb') as src:
        header = src.read(32)
        if len(header) != 32: raise ValueError('truncated Mach-O header')
        magic, cpu, _, kind, commands, length, _, _ = struct.unpack('<8I', header)
        if magic != 0xfeedfacf or cpu != 0x0100000c or kind != 2:
            raise ValueError('reuse requires one thin arm64 executable')
        if not 0 < commands <= 4096 or not 0 < length <= 16 << 20 or length > size - 32:
            raise ValueError('invalid Mach-O load commands')
        data, at, sections = src.read(length), 0, {}
        for _ in range(commands):
            if at + 8 > len(data): raise ValueError('truncated load command')
            cmd, count = struct.unpack_from('<II', data, at)
            if count < 8 or count % 4 or count > len(data) - at: raise ValueError('invalid load command length')
            if cmd == 0x19:
                if count < 72: raise ValueError('truncated 64-bit segment')
                nsect = struct.unpack_from('<I', data, at + 64)[0]
                if nsect > 255 or 72 + nsect * 80 > count: raise ValueError('invalid section count')
                for i in range(nsect):
                    off = at + 72 + i * 80
                    sect, seg = (data[off + j:off + j + 16].split(b'\0')[0].decode('ascii') for j in (0, 16))
                    extent, fileoff = struct.unpack_from('<QI', data, off + 40)
                    flags = struct.unpack_from('<I', data, off + 64)[0]
                    if (seg, sect) in sections: raise ValueError('duplicate Mach-O section')
                    sections[seg, sect] = (fileoff, extent, flags & 0xff)
            at += count
        if at != len(data): raise ValueError('inconsistent load command table')
    return sections


def read_fixups(path):
    rows = {}
    for line in path.read_text().splitlines():
        if not line.startswith('# '): raise ValueError('unexpected rewritten-module metadata')
        fields = line[2:].split()
        if len(fields) != 2 or fields[0] in rows: raise ValueError('invalid rewritten-module metadata')
        rows[fields[0]] = fields[1]
    for key in ('TEXT_END', 'PATCH_OFF', 'KEY_PAGE_OFF', 'KEY_PAGE_SIZE', 'BUILD_ID'):
        if key not in rows: raise ValueError('incomplete rewritten-module layout')
    if not re.fullmatch('[0-9a-f]{32,64}', rows['BUILD_ID']): raise ValueError('invalid module build ID')
    return rows


def recover_module(executable, sections, name, fixups, destination):
    if not re.fullmatch('[A-Za-z0-9_]{1,10}', name): raise ValueError('unsupported embedded module name')
    header = read_fixups(fixups)
    text = (int(header['TEXT_END'], 0) + PAGE - 1) & ~(PAGE - 1)
    patch, key, key_size = (int(header[k], 0) for k in ('PATCH_OFF', 'KEY_PAGE_OFF', 'KEY_PAGE_SIZE'))
    names = [('__TEXT', f'__dm{name}x0'), (f'__DM{name}W', '__img'), ('__TEXT', f'__dm{name}x1')]
    pieces = [sections[pair] for pair in names if pair in sections]
    if len(pieces) != 3: raise ValueError('missing embedded module section; full rebuild required')
    if text <= 0 or text % PAGE or key < text or key % PAGE or key_size != PAGE or patch % PAGE:
        raise ValueError('invalid embedded module alignment')
    middle_end = int(header['FILE_IMAGE_LEN'], 0) if patch < 0 else patch
    if patch < 0 and (middle_end % PAGE or key < middle_end): raise ValueError('invalid front patch layout')
    expected = (text, middle_end - text)
    if expected[1] < 0 or tuple(piece[1] for piece in pieces[:2]) != expected:
        raise ValueError('embedded sections do not match the rewriter layout')
    if patch >= 0 and key + key_size > patch: raise ValueError('key page overlaps the patch')
    total = sum(piece[1] for piece in pieces)
    if total > MAX_IMAGE or not pieces[2][1] or total % PAGE: raise ValueError('invalid module extent')
    size = executable.stat().st_size
    for offset, extent, kind in pieces:
        if kind != 0 or extent % PAGE or offset % PAGE or offset + extent > size:
            raise ValueError('embedded code is not a complete regular section')
    with executable.open('rb') as src, destination.open('xb') as out:
        for offset, extent, _ in pieces:
            src.seek(offset)
            while extent:
                block = src.read(min(extent, 8 << 20))
                if not block: raise ValueError('truncated embedded module')
                out.write(block); extent -= len(block)
    return digest_file(destination)


def unpack_ipa(path, root):
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 80000 or sum(item.file_size for item in members) > MAX_UNPACKED:
            raise ValueError('IPA exceeds reuse limits; full-input build required')
        seen, apps = set(), set()
        for item in members:
            name = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if item.filename in seen or '\\' in item.filename or name.is_absolute() or '..' in name.parts:
                raise ValueError('unsafe or duplicate IPA member')
            seen.add(item.filename)
            if stat.S_ISLNK(mode): raise ValueError('symlinked IPA resources require a full-input build')
            if len(name.parts) < 2 or name.parts[0] != 'Payload' or not name.parts[1].endswith('.app'):
                if item.is_dir() and name.parts == ('Payload',): continue
                raise ValueError('unexpected IPA layout')
            apps.add(name.parts[1])
        if len(apps) != 1: raise ValueError('one app per IPA is required')
        for item in members:
            dest = root / item.filename
            if item.is_dir(): dest.mkdir(parents=True, exist_ok=True); continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as src, dest.open('xb') as out: shutil.copyfileobj(src, out, 8 << 20)
            dest.chmod(0o755 if (item.external_attr >> 16) & 0o111 else 0o644)
    return root / 'Payload' / next(iter(apps))


def compatible_source(previous, current, game):
    if not SHA.fullmatch(previous) or not SHA.fullmatch(current) or not re.fullmatch('[0-9A-Fa-f]{16}', game):
        raise ValueError('reuse requires exact source revisions and a game ID')
    subprocess.run(['git', '-C', str(REPO), 'merge-base', '--is-ancestor', previous, current], check=True)
    # Deliberately conservative. Host service/loader ABI, rewriting, serialized
    # reflection, profiles and embedding contracts must not change under reuse.
    guarded = ['dm/host', ':(glob)dm/tools/*.py', ':(glob)dm/games/*.py',
               f'dm/games/{game}', 'dm/ios/tools/gen_embed.py', 'dm/ios/Sources/main.m',
               'dm/gfx/nvn/dmsh_chain.h', 'dm/gfx/nvn/nvn_mtl.h', 'dm/gfx/nvn/nvn_tex.h',
               'dm/gfx/nvn/nvn_refl.h', 'dm/gfx/tools', 'dm/third_party']
    changes = subprocess.check_output(['git', '-C', str(REPO), 'diff', '--name-only', previous, current, '--', *guarded], text=True)
    relevant = [p for p in changes.splitlines() if not p.endswith(('.md', 'validated.tsv'))]
    if relevant: raise ValueError('guest/shader/ABI inputs changed; full-input build required: ' + ', '.join(relevant[:8]))


def verify_shader_snapshot(app, game, chain):
    lib = app / 'msl' / f'b-{chain}'
    stamp = dict(line.split('\t', 1) for line in (lib / 'inputs.tsv').read_text().splitlines() if not line.startswith('#') and '\t' in line)
    if stamp.get('game') != game or not re.fullmatch('[0-9a-f]{12}', stamp.get('inputs', '')):
        raise ValueError('shader snapshot has no matching game/input stamp')
    prefix = f'# chain b-{chain} inputs {stamp["inputs"]} '
    for table in ('c1_full.tsv', 'cb_extent.tsv'):
        with (app / 'dm' / table).open() as src:
            if not src.readline().startswith(prefix): raise ValueError('shader table stamp mismatch; never restamp it')
    if not any(lib.glob('*_b.metallib')): raise ValueError('missing compiled NVN libraries')
    return stamp['inputs']


def build(args):
    if sys.platform != 'darwin': raise ValueError('host compilation runs on the private Mac runner, not on the Mac client')
    sys.path.insert(0, str(REPO / 'scripts')); import cloud_ipa
    cloud_ipa.private_repo(args.repo)
    args.work.mkdir(parents=True)  # refuse to overwrite any previous working build
    previous = args.work / 'previous'
    manifest = cloud_ipa.restore(args.repo, args.from_tag, previous, ('BOTW-A16.ipa', 'build.json'))
    metadata = json.loads((previous / 'build.json').read_text())
    source = subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()
    game, package = metadata['game'], metadata['package']
    compatible_source(metadata.get('guest_source', metadata['source']), source, game)
    app = unpack_ipa(previous / 'BOTW-A16.ipa', args.work / 'unpacked')
    if (app / 'romfs.img').exists() or (app / 'romfs').exists(): raise ValueError('reuse needs an external-data IPA')
    identity_text = (app / 'romfs.id').read_text()
    sys.path.insert(0, str(REPO / 'dm/tools')); import romfs_image
    identity = romfs_image.parse_identity(identity_text)
    data = next(f for f in manifest['files'] if f['path'] == 'romfs.img')
    if identity.get('title') != game or identity.get('build') != package or identity['size'] != data['size']:
        raise ValueError('IPA and previous data image identity do not match')
    match = re.search(r'^#define DMSH_CHAIN "([0-9a-f]+)"', (REPO / 'dm/gfx/nvn/dmsh_chain.h').read_text(), re.M)
    if match is None: raise ValueError('missing current shader chain')
    chain = match[1]
    inputs = verify_shader_snapshot(app, game, chain)
    info = plistlib.loads((app / 'Info.plist').read_bytes())
    executable_name = info['CFBundleExecutable']
    if not re.fullmatch('[A-Za-z0-9_.-]+', executable_name): raise ValueError('invalid app executable name')
    executable = app / executable_name
    sys.path.insert(0, str(REPO / 'dm/games')); import game as gamemod
    profile = gamemod.load(game); modules = profile.words('modules')
    wanted = profile.builds().get(package)
    if not wanted: raise ValueError('previous package is not registered by the current profile')
    tables = app / 'dm'
    if (tables / 'nro.tsv').exists(): raise ValueError('packed NRO modules need the full-input build path')
    sections = macho_sections(executable)
    patched = args.work / 'patched'; patched.mkdir()
    module_hashes = {}
    for name in modules:
        fixups = tables / f'{name}.fixups.tsv'
        if read_fixups(fixups)['BUILD_ID'] != wanted.get(name): raise ValueError('module build ID does not match the registered package')
        module_hashes[name] = recover_module(executable, sections, name, fixups, patched / f'{name}.patched.bin')
        for table in tables.glob(f'{name}.*.tsv'): shutil.copyfile(table, patched / table.name)
    if metadata.get('main_build') != wanted['main']: raise ValueError('previous build provenance does not match its code')
    project = args.work / 'project'; gen = project / 'Gen'; gen.mkdir(parents=True)
    for name in ('Sources', 'tools'): (project / name).symlink_to(REPO / 'dm/ios' / name, target_is_directory=True)
    shutil.copyfile(REPO / 'dm/ios/project.yml', project / 'project.yml')
    shutil.copytree(tables, gen / 'dm')
    assets = gen / 'Assets.xcassets'; assets.mkdir()
    (assets / 'Contents.json').write_text(json.dumps({'info': {'author': 'xcode', 'version': 1}}))
    env = dict(os.environ, GAME=game, DM_GAME=game, GFXAPI='nvn', SETTINGS_PLATFORM='ios',
               DM_BUNDLE_ID=info['CFBundleIdentifier'], DM_DISPLAY_NAME=info.get('CFBundleDisplayName', 'NXNative Lab'),
               DM_APP_VERSION=info['CFBundleShortVersionString'], DM_APP_CATEGORY=profile.get('app_category'),
               DM_SHOW_FPS='YES' if info.get('DMShowFPS') else 'NO', DM_LANG=info.get('DMLanguage', 'en-US'),
               DM_TEAM_ID='', DM_SCHEME_NAME='DmIOS', DM_APPICON='')
    def run(*cmd, capture=False):
        return subprocess.run(list(map(str, cmd)), env=env, cwd=project, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None).stdout
    config = run(sys.executable, project / 'tools/gen_build.py', REPO / 'dm/host', gen, capture=True)
    flags = run(sys.executable, project / 'tools/gen_embed.py', patched, gen / 'embed.S', *modules, capture=True).strip()
    (gen / 'dm.xcconfig').write_text(config + '\nOTHER_LDFLAGS = $(inherited) $(DM_FRAMEWORKS) ' + flags + '\n')
    # Keep game-language choices from its actual NACP; regenerate all other rows
    # from the current source, including the opt-in trace setting.
    import settings
    old_launcher = json.loads((tables / 'launcher.json').read_text())
    launcher = settings.build(game, patched, args.work / 'no-control.nacp')
    languages = [row for row in old_launcher['settings'] if row['env'] == 'DM_LANG']
    launcher['settings'].extend(languages)
    (tables / 'launcher.json').write_text(json.dumps(launcher, indent=2) + '\n')
    (gen / 'dm/launcher.json').write_text(json.dumps(launcher, indent=2) + '\n')
    run('xcodegen', 'generate')
    derived = args.work / 'derived'
    with (args.work / 'host-build.log').open('w') as log:
        subprocess.run(['xcodebuild', '-project', str(project / 'DmIOS.xcodeproj'), '-scheme', 'DmIOS',
                        '-configuration', 'Release', '-destination', 'generic/platform=iOS', '-derivedDataPath', str(derived),
                        '-jobs', '3', 'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'CODE_SIGN_IDENTITY=',
                        'DM_COPY_GAME_RESOURCES=NO', f'DM_XCODE_OUTPUT_ROOT={derived}', f'SYMROOT={derived}/Build/Products',
                        f'OBJROOT={derived}/Build/Intermediates.noindex', 'build'], env=env, cwd=project,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    linked = derived / 'Build/Products/Release-iphoneos/DmIOS.app/DmIOS'
    checked = args.work / 'roundtrip'; checked.mkdir()
    after = macho_sections(linked)
    for name in modules:
        actual = recover_module(linked, after, name, tables / f'{name}.fixups.tsv', checked / f'{name}.patched.bin')
        if actual != module_hashes[name]: raise ValueError('relinked guest code changed; refusing publication')
    shutil.copyfile(linked, executable); executable.chmod(0o755)
    info['NXNativeSourceRevision'] = source; info['NXNativeBuildChannel'] = 'experimental'
    info['NXNativeGameId'] = game; info['NXNativeGamePackage'] = package
    (app / 'Info.plist').write_bytes(plistlib.dumps(info))
    shutil.rmtree(app / '_CodeSignature', ignore_errors=True)
    (app / 'embedded.mobileprovision').unlink(missing_ok=True)
    entitlements = args.work / 'entitlements.plist'
    entitlements.write_bytes(plistlib.dumps({'com.apple.developer.kernel.increased-memory-limit': True}))
    run('codesign', '--force', '--sign', '-', '--entitlements', entitlements, executable)
    args.output.mkdir(parents=True)
    run(sys.executable, project / 'tools/pack_ipa.py', args.output / 'BOTW-A16.ipa', '--no-reuse', f'Payload/{app.name}={app}')
    metadata.update(source=source, guest_source=metadata.get('guest_source', metadata['source']), reused_data_tag=args.from_tag,
                    reused_ipa_sha256=digest_file(previous / 'BOTW-A16.ipa'), module_sha256=module_hashes,
                    build_mode='host-only-roundtrip-verified', device_validation='pending', shader_chain=chain,
                    shader_inputs=inputs, cpu='apple-a14', cpu_tune='apple-a16',
                    xcode=subprocess.check_output(['xcodebuild', '-version'], text=True))
    (args.output / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print('Host-only IPA built; guest code, shader stamps and external-data identity preserved. Device validation pending.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', required=True); ap.add_argument('--from-tag', required=True)
    ap.add_argument('--work', type=Path, required=True); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(); args.work = args.work.resolve(); args.output = args.output.resolve()
    try:
        if args.work.is_relative_to(REPO) or args.output.is_relative_to(REPO):
            raise ValueError('private build files must live outside the source repository')
        build(args)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as e:
        sys.exit(f'host-only build: {e}; the previous output is untouched')


if __name__ == '__main__': main()
