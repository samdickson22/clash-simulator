"""Source-derived historical seed, physical-run and deck exclusions.

Discovery records the searched files, including aliases and files with no case
identities. Validation re-derives the union from pinned bytes, not claimed lists.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from . import rl_schedule as S


def reference(path):
    return dict(path=str(Path(path).resolve()), sha256=S.file_sha(path))


def identities(value):
    seeds, runs, decks = set(), set(), set()
    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            # A seed alone can be a bootstrap or training RNG. Require a case.
            case = any(k in node for k in ('opponent_deck', 'own_deck', 'decks', 'case_sha256'))
            if case and 'seed' in node:
                S.require(type(node['seed']) is int and node['seed'] > 0, 'invalid historical engine seed')
                seeds.add(node['seed'])
            for key in ('source_run', 'physical_source_id'):
                if node.get(key):
                    S.require(isinstance(node[key], str), 'invalid historical physical run')
                    runs.add(node[key])
            for key in ('runs', 'physical_source_ids'):
                if isinstance(node.get(key), list) and all(isinstance(r, str) for r in node[key]):
                    runs.update(node[key])
            if 'opponent_deck' in node:
                from bot.fullpool.cards import engine_name
                deck = node['opponent_deck']
                S.require(isinstance(deck, list) and len(deck) == 8, 'invalid historical opponent deck')
                decks.add(tuple(sorted(engine_name(c) for c in deck)))
            for item in node.values():
                walk(item)
    walk(value)
    return seeds, runs, decks


def read(path):
    path = Path(path)
    if path.suffix == '.jsonl':
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return json.loads(path.read_text())


def pinned_identities(ref, cache):
    """Read each artifact once per validation, including its byte authentication."""
    S.require(set(ref) == {'path', 'sha256'}, 'artifact requires exact path and SHA256')
    key = (ref['path'], ref['sha256'])
    if key not in cache:
        path = Path(ref['path'])
        raw = path.read_bytes()
        S.require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'historical source SHA mismatch: '+str(path))
        value = [json.loads(line) for line in raw.splitlines() if line.strip()] if path.suffix == '.jsonl' else json.loads(raw)
        cache[key] = identities(value)
    return cache[key]


def derive(sources, *, cache=None):
    cache = {} if cache is None else cache
    seeds, runs, decks = set(), set(), set()
    for ref in sources:
        a, b, c = pinned_identities(ref, cache)
        seeds.update(a)
        runs.update(b)
        decks.update(c)
    return dict(seeds=sorted(seeds), physical_source_ids=sorted(runs), opponent_decks=[list(d) for d in sorted(decks)])


def validate(inventory):
    S.require(bool(inventory['sources']), 'historical sources required')
    cache = {}
    actual = derive(inventory['sources'], cache=cache)
    S.require(inventory['seeds'] == actual['seeds'] and bool(actual['seeds']),
              'historical seed inventory differs from pinned source union')
    if inventory.get('schema') == 'pv1-rl-exclusions-v2':
        for key in ('physical_source_ids', 'opponent_decks'):
            S.require(inventory[key] == actual[key], 'historical inventory differs from sources: '+key)
        coverage = json.loads(S.pinned(inventory['coverage']).read_text())
        S.require(coverage['sources'] == inventory['sources'] and coverage['scope']
                  and coverage['documents'] and coverage['files'], 'incomplete historical search coverage')
        for ref in coverage['documents']:
            S.pinned(ref)
        # Search evidence is a frozen inventory, not a promise that mutable
        # directories will stay unchanged. Every inspected byte remains pinned.
        declared = {ref['path']: ref for ref in inventory['sources']}
        for row in coverage['files']:
            ref = row['artifact']
            a, b, c = pinned_identities(ref, cache)
            S.require((len(a), len(b), len(c), bool(a or b or c)) ==
                      (row['seeds'], row['physical_runs'], row['decks'], row['contributes']),
                      'search coverage identity counts mismatch')
            S.require(not (a or b or c) or declared.get(ref['path']) == ref, 'omitted inspected historical source')
        for ref in coverage['documents']:
            if Path(ref['path']).suffix in ('.json', '.jsonl'):
                a, b, c = pinned_identities(ref, cache)
                S.require(not (a or b or c) or declared.get(ref['path']) == ref, 'omitted historical inventory document')
    return actual


def discover(roots, documents, coverage_path, *, skip=()):
    sources, files = {}, []
    skipped = set(skip)
    visited, aliases = set(), []
    for root in map(Path, roots):
        S.require(root.is_dir(), 'missing historical inventory root: '+str(root))
        for directory, children, names in os.walk(root, followlinks=True):
            resolved = str(Path(directory).resolve())
            if resolved in visited:
                aliases.append(dict(path=str(Path(directory).absolute()), resolves_to=resolved))
                children[:] = []
                continue
            visited.add(resolved)
            children[:] = sorted(c for c in children if c not in skipped)
            for name in sorted(names):
                path = Path(directory)/name
                if path.suffix not in ('.json', '.jsonl'):
                    continue
                ref = reference(path)
                value = read(path)  # Parse errors abort discovery; never silently skip evidence.
                seeds, runs, decks = identities(value)
                contributes = bool(seeds or runs or decks)
                files.append(dict(artifact=ref, alias_path=str(path.absolute()), seeds=len(seeds),
                                  physical_runs=len(runs), decks=len(decks), contributes=contributes))
                if contributes:
                    sources[ref['path']] = ref
                # A manifest may point outside the searched roots. Follow its
                # explicit bank path and authenticate any accompanying SHA.
                if isinstance(value, dict) and value.get('bank_path'):
                    bank = Path(value['bank_path'])
                    bank_ref = reference(bank)
                    if value.get('bank_sha256'):
                        S.require(bank_ref['sha256'] == value['bank_sha256'], 'historical bank alias SHA mismatch')
                    sources[bank_ref['path']] = bank_ref
    for path in documents:
        if Path(path).suffix in ('.json', '.jsonl'):
            a, b, c = identities(read(path))
            if a or b or c:
                ref = reference(path)
                sources[ref['path']] = ref
    refs = [sources[p] for p in sorted(sources)]
    coverage = dict(schema='pv1-rl-exclusion-search-v1', scope=[str(Path(p).resolve()) for p in roots],
                    skipped_directory_names=sorted(skipped), documents=[reference(p) for p in documents],
                    files=files, sources=refs, directory_aliases=aliases)
    with Path(coverage_path).open('xb') as output:
        output.write(S.encoded(coverage)+b'\n')
    return dict(schema='pv1-rl-exclusions-v2', sources=refs, coverage=reference(coverage_path), **derive(refs))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, action='append', required=True)
    parser.add_argument('--document', type=Path, action='append', required=True)
    parser.add_argument('--skip-directory', action='append', default=[])
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    inventory = discover(args.root, args.document, args.coverage, skip=args.skip_directory)
    validate(inventory)
    with args.out.open('xb') as output:
        output.write(S.encoded(inventory)+b'\n')
    print(json.dumps(dict(seeds=len(inventory['seeds']), physical_runs=len(inventory['physical_source_ids']),
                          decks=len(inventory['opponent_decks']), artifact=reference(args.out))))


if __name__ == '__main__':
    main()
