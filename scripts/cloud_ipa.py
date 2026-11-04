#!/usr/bin/env python3
"""Own-input private cloud builds. Mac client needs Python + gh, never Xcode.

Large files are streamed through 1.9 GB release assets: temporary client disk
use stays at one part. Manifests are committed last, with whole/part SHA-256.
No shell commands are assembled from filenames and no key contents are logged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import time

PART_SIZE = 1_900_000_000
MAX_TOTAL = 80 * 1024**3
SOURCE = Path(__file__).resolve().parents[1]


def gh(*args, capture=False):
    return subprocess.run(['gh', *map(str, args)], check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def private_repo(repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('invalid owner/repository')
    meta = json.loads(gh('api', f'repos/{repo}', capture=True))
    if not meta.get('private'):
        raise ValueError('game inputs and outputs require a private repository')


def safe_path(name, kind):
    p = PurePosixPath(name)
    if '\\' in name or p.is_absolute() or '..' in p.parts or str(p) != name:
        raise ValueError('unsafe manifest path')
    if kind == 'inputs':
        allowed = name == 'prod.keys' or (len(p.parts) == 2 and p.parts[0] == 'game'
                                         and re.fullmatch(r'input[0-9]{3}\.(nsp|xci)', p.name))
    else:
        allowed = name in ('BOTW-A16.ipa', 'romfs.img', 'build.json')
    if not allowed:
        raise ValueError('unexpected manifest member')
    return p


def valid_tag(tag):
    return isinstance(tag, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,90}', tag) is not None


def validate_manifest(m):
    if not isinstance(m, dict) or m.get('version') not in (1, 2) or m.get('kind') not in ('inputs', 'output'):
        raise ValueError('unknown manifest format')
    entries = m.get('files', [])
    if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
        raise ValueError('invalid file count')
    names, assets, total = set(), set(), 0
    for f in entries:
        if not isinstance(f, dict) or not {'path', 'size', 'sha256', 'parts'} <= f.keys():
            raise ValueError('incomplete file metadata')
        if not isinstance(f['path'], str): raise ValueError('invalid manifest path')
        safe_path(f['path'], m['kind'])
        if f['path'] in names or type(f['size']) is not int or not 0 < f['size'] <= MAX_TOTAL:
            raise ValueError('duplicate or invalid file')
        names.add(f['path']); total += f['size']
        if not isinstance(f['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', f['sha256']):
            raise ValueError('invalid file digest')
        if not isinstance(f['parts'], list) or not 1 <= len(f['parts']) <= 128:
            raise ValueError('invalid part count')
        source_tag = f.get('source_tag', '')
        if not isinstance(source_tag, str): raise ValueError('invalid data reference tag')
        if source_tag and (m['version'] != 2 or m['kind'] != 'output' or f['path'] != 'romfs.img' or not valid_tag(source_tag)):
            raise ValueError('invalid immutable data reference')
        size = 0
        for part in f['parts']:
            if not isinstance(part, dict) or not {'asset', 'size', 'sha256'} <= part.keys():
                raise ValueError('incomplete part metadata')
            asset = part['asset']
            if not isinstance(asset, str) or not re.fullmatch(r'part-[0-9]{3}-[0-9]{3}\.bin', asset) or (source_tag, asset) in assets:
                raise ValueError('invalid or duplicate asset')
            if (type(part['size']) is not int or not 0 < part['size'] <= PART_SIZE or not isinstance(part['sha256'], str)
                    or not re.fullmatch('[0-9a-f]{64}', part['sha256'])):
                raise ValueError('invalid part metadata')
            assets.add((source_tag, asset)); size += part['size']
        if size != f['size']: raise ValueError('part sizes do not match file size')
    if total > MAX_TOTAL or (m['kind'] == 'inputs' and ('prod.keys' not in names or len(names) < 2)):
        raise ValueError('incomplete or oversized payload')
    return total


def split_file(path, prefix, temp, accept, limit=PART_SIZE):
    """At most one temporary part; accept() must finish before it is removed."""
    whole, parts, total = hashlib.sha256(), [], 0
    with path.open('rb') as src:
        while True:
            data = src.read(min(1024 * 1024, limit))
            if not data:
                break
            p = temp / f'part-{prefix:03d}-{len(parts):03d}.bin'
            h, size = hashlib.sha256(), 0
            with p.open('xb') as out:
                while data:
                    out.write(data); h.update(data); whole.update(data); size += len(data)
                    if size == limit:
                        break
                    data = src.read(min(1024 * 1024, limit - size))
            accept(p)
            parts.append({'asset': p.name, 'size': size, 'sha256': h.hexdigest()})
            total += size; p.unlink()
    return {'size': total, 'sha256': whole.hexdigest(), 'parts': parts}


def publish(repo, tag, files, kind, references=()):
    private_repo(repo)
    if not valid_tag(tag):
        raise ValueError('invalid release tag')
    gh('release', 'create', tag, '--repo', repo, '--draft', '--target', 'main',
       '--title', f'Private BOTW {kind}', '--notes', 'Own-input build data. Keep this repository private.')
    manifest = {'version': 2 if references else 1, 'kind': kind, 'files': []}
    # The caller puts client temporaries beside the source game files, not home.
    with tempfile.TemporaryDirectory(prefix='nx-cloud-', dir=files[-1][1].parent) as td:
        temp = Path(td)
        for i, (name, path) in enumerate(files):
            safe_path(name, kind)
            entry = split_file(path, i, temp, lambda p: gh('release', 'upload', tag, p, '--repo', repo))
            manifest['files'].append({'path': name, **entry})
        manifest['files'].extend(references)
        validate_manifest(manifest)
        p = temp / 'manifest.json'; p.write_text(json.dumps(manifest, indent=2) + '\n')
        gh('release', 'upload', tag, p, '--repo', repo)
    return manifest


def restore(repo, tag, out, only=()):
    private_repo(repo)
    if not valid_tag(tag): raise ValueError('invalid release tag')
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('restore output must be an empty directory')
    with tempfile.TemporaryDirectory(prefix='nx-download-', dir=out.parent) as td:
        temp = Path(td)
        gh('release', 'download', tag, '--repo', repo, '--pattern', 'manifest.json', '--dir', temp)
        m = json.loads((temp / 'manifest.json').read_text()); total = validate_manifest(m)
        selected = set(only)
        if selected and (m['kind'] != 'output' or selected - {f['path'] for f in m['files']}):
            raise ValueError('select only existing output files, never partial game inputs')
        files = [f for f in m['files'] if not selected or f['path'] in selected]
        total = sum(f['size'] for f in files)
        # Leave enough space to extract the merged image and compile. If a
        # standard runner is too small, fail before transferring large inputs.
        need = total * 2 + 8 * 1024**3 if m['kind'] == 'inputs' else total + PART_SIZE
        if shutil.disk_usage(out.parent).free < need:
            raise ValueError(f'not enough disk: need {need / 1024**3:.1f} GiB free')
        for f in files:
            p = out / str(safe_path(f['path'], m['kind'])); p.parent.mkdir(parents=True, exist_ok=True)
            partial = p.with_name(p.name + '.partial')
            whole = hashlib.sha256()
            try:
                with partial.open('xb') as dst:
                    os.chmod(partial, 0o600)
                    for part in f['parts']:
                        gh('release', 'download', f.get('source_tag') or tag, '--repo', repo, '--pattern', part['asset'], '--dir', temp)
                        part_path = temp / part['asset']; h, n = hashlib.sha256(), 0
                        with part_path.open('rb') as src:
                            for block in iter(lambda: src.read(1024 * 1024), b''):
                                dst.write(block); h.update(block); whole.update(block); n += len(block)
                        part_path.unlink()
                        if n != part['size'] or h.hexdigest() != part['sha256']:
                            raise ValueError('part integrity check failed')
                if partial.stat().st_size != f['size'] or whole.hexdigest() != f['sha256']:
                    raise ValueError('file integrity check failed')
                partial.rename(p)
            finally:
                partial.unlink(missing_ok=True)

    return m


def data_reference(repo, tag):
    """Flatten a same-private-repository RomFS reference without downloading it."""
    private_repo(repo)
    if not valid_tag(tag): raise ValueError('invalid release tag')
    with tempfile.TemporaryDirectory(prefix='nx-reference-') as td:
        gh('release', 'download', tag, '--repo', repo, '--pattern', 'manifest.json', '--dir', td)
        manifest = json.loads((Path(td) / 'manifest.json').read_text()); validate_manifest(manifest)
    if manifest['kind'] != 'output': raise ValueError('data reuse needs a previous output release')
    matches = [f for f in manifest['files'] if f['path'] == 'romfs.img']
    if len(matches) != 1: raise ValueError('previous output has no unique data image')
    return {**matches[0], 'source_tag': matches[0].get('source_tag') or tag}


def upload(args):
    folder, keys = args.nsp_folder.resolve(), args.keys.resolve()
    if folder.is_relative_to(SOURCE) or keys.is_relative_to(SOURCE):
        raise ValueError('game files and keys must live outside the source repository')
    games = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.nsp', '.xci'))
    if not games or len(games) > 63 or not keys.is_file() or not 0 < keys.stat().st_size < 1024**2:
        raise ValueError('provide your base/update NSPs (or base XCI) and prod.keys')
    files = [('prod.keys', keys)] + [(f'game/input{i:03d}{p.suffix.lower()}', p) for i, p in enumerate(games)]
    tag = args.tag or f'botw-inputs-{time.strftime("%Y%m%d-%H%M%S", time.gmtime())}'
    revision = args.source_revision
    if args.start and not revision:
        revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    if args.start and not re.fullmatch('[0-9a-f]{40}', revision or ''):
        raise ValueError('provide a full published --source-revision')
    publish(args.repo, tag, files, 'inputs')
    if args.start:
        gh('workflow', 'run', 'build.yml', '--repo', args.repo, '-f', f'input_tag={tag}', '-f', f'source_revision={revision}')
    print(f'Private inputs ready: {tag}. Follow Actions in {args.repo}.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    u = sub.add_parser('upload'); u.add_argument('--repo', required=True)
    u.add_argument('--nsp-folder', type=Path, required=True); u.add_argument('--keys', type=Path, required=True)
    u.add_argument('--tag'); u.add_argument('--start', action='store_true'); u.add_argument('--source-revision')
    r = sub.add_parser('download'); r.add_argument('--repo', required=True); r.add_argument('--tag', required=True)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--only', choices=('BOTW-A16.ipa', 'build.json', 'romfs.img'), action='append', default=[])
    p = sub.add_parser('publish-output'); p.add_argument('--repo', required=True); p.add_argument('--tag', required=True)
    p.add_argument('--folder', type=Path, required=True)
    p.add_argument('--reuse-data-tag', help='Reference an unchanged RomFS from a previous private output; never re-upload it')
    args = ap.parse_args()
    try:
        if args.command == 'upload':
            upload(args)
        elif args.command == 'download':
            restore(args.repo, args.tag, args.out.resolve(), args.only)
        else:
            references = [data_reference(args.repo, args.reuse_data_tag)] if args.reuse_data_tag else []
            names = ('BOTW-A16.ipa', 'build.json') if references else ('BOTW-A16.ipa', 'romfs.img', 'build.json')
            files = [(name, args.folder / name) for name in names]
            if references:
                metadata = json.loads((args.folder / 'build.json').read_text())
                if metadata.get('reused_data_tag') != args.reuse_data_tag:
                    raise ValueError('build metadata must establish the unchanged data reference')
            publish(args.repo, args.tag, files, 'output', references)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as e:
        sys.exit(f'cloud build: {e}')


if __name__ == '__main__':
    main()
