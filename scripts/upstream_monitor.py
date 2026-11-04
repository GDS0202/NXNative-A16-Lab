#!/usr/bin/env python3
"""Observe public upstream heads/PRs. Never download or execute upstream code."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

AREAS = {
    'pacing': ('pacing', 'stutter', 'present', 'latency', 'frame rate'),
    'textures': ('texture', 'astc', 'bc4', 'bc7', 'deswizz'),
    'memory': ('memory', 'retire', 'dirty', 'pool', 'leak'),
    'pipelines': ('shader', 'pipeline', 'prewarm', 'prebuild', 'cache'),
    'correctness': ('crash', 'hang', 'race', 'artifact', 'corrupt'),
}


def github(endpoint):
    request = urllib.request.Request('https://api.github.com/' + endpoint,
                                     headers={'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                                              'User-Agent': 'NXNative-source-monitor'})
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if token: request.add_header('Authorization', 'Bearer ' + token)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(4 * 1024**2 + 1)
        if len(body) > 4 * 1024**2: raise ValueError('upstream response too large')
        return json.loads(body)


def collect(config, previous, api=github):
    observations = []
    old = {(r['repo'], r['ref']): r for r in previous.get('observations', [])}
    for source in config['sources']:
        repo, ref = source['repo'], source['ref']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', repo) or not re.fullmatch(r'[A-Za-z0-9_./-]+', ref):
            raise ValueError('invalid configured upstream')
        if not re.fullmatch('[0-9a-f]{40}', source['reviewed_sha']) or any(p in ('', '.', '..') for p in ref.split('/')):
            raise ValueError('invalid configured upstream revision')
        result = {'repo': repo, 'ref': ref, 'reviewed_sha': source['reviewed_sha']}
        try:
            metadata = api(f'repos/{repo}')
            if metadata.get('private') is not False: raise ValueError('only public upstreams are monitored')
            commit = api(f'repos/{repo}/commits/{urllib.parse.quote(ref, safe="")}')
            sha = commit['sha']
            if not re.fullmatch('[0-9a-f]{40}', sha): raise ValueError('invalid upstream commit')
            pulls = api(f'repos/{repo}/pulls?state=open&per_page=20&sort=updated&direction=desc')
            candidates = []
            for pull in pulls:
                number, head = pull['number'], pull['head']['sha']
                if type(number) is not int or number <= 0 or not re.fullmatch('[0-9a-f]{40}', head):
                    raise ValueError('invalid pull request metadata')
                text = (pull.get('title', '') + ' ' + ' '.join(label.get('name', '') for label in pull.get('labels', []))).lower()
                areas = sorted(area for area, words in AREAS.items() if any(word in text for word in words))
                if areas: candidates.append({'number': number, 'head': head, 'areas': areas,
                                              'url': f'https://github.com/{repo}/pull/{number}'})
            # Do not commit arbitrary titles/bodies from a remote project into
            # privileged automation. Links/IDs/enum categories are sufficient.
            result.update(observed_sha=sha, license=(metadata.get('license') or {}).get('spdx_id') or 'unknown',
                          pull_candidates=sorted(candidates, key=lambda p: p['number']), status='observed')
        except (OSError, ValueError, KeyError, TypeError, urllib.error.HTTPError):
            prior = old.get((repo, ref), {})
            result.update(observed_sha=prior.get('observed_sha', source['reviewed_sha']),
                          license=prior.get('license', 'unknown'), pull_candidates=prior.get('pull_candidates', []),
                          status='unavailable-no-integration')
        observations.append(result)
    return {'schema': 1, 'automatic_code_integration': False, 'observations': observations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path('docs/upstreams.json'))
    parser.add_argument('--state', type=Path, default=Path('docs/upstream-observations.json'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.state.read_text()) if args.state.exists() else {}
    result = collect(json.loads(args.config.read_text()), previous)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('Public upstream observations recorded. No source code was imported or executed.')


if __name__ == '__main__': main()
