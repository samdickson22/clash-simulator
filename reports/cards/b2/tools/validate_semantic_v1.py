"""Validate semantic-v1 evidence separately from the preserved strict FAIL.

Usage: validate_semantic_v1.py FID TAG [--identity NATIVE MUTANT_A MUTANT_B]
Only TAG.semantic-pass.json is emitted, never a full-state or engine PASS.
"""
import argparse
import json
import os
from pathlib import Path
import socket

from snapshot_contract_v1 import VERSION, CACHE_INAPPLICABLE
from validate_r2 import (SHARDS, B2, BATCH_A, FIRST_UPDATE_ACTIONS, sha, now, read,
                         exact_keys, check_actions)

LABELS = [f'semantic-{i}' for i in range(1, 5)] + [
    'mutA', 'mutB', 'descendants', 'fu-paths', 'clone-checks',
    'scen-b2-root', 'scen-b2-stats', 'scen-batchA']
NATIVES = {
    'out4': '7738f9d2c4c2b9f900fda60b69b70976faed186975662838b3b2af1f82a2e7ff',
    'mutA': 'ff74a2fc8cfb7e78c60d0c1eb9e0880aebab8fb010939b2fa9d0eb6cfe01ee33',
    'mutB': '2964dec34f8a0a29c9352e249e7e87e77adfce7bcdc908bdbb1443fb8b4265f3'}


def check_ledger(records):
    assert records, 'missing applicability evidence'
    for row in records:
        assert {'field', 'entity_class', 'python', 'native', 'reason', 'disposition', 'ticks'} <= row.keys(), row
        assert row['ticks'] and all(isinstance(t, int) and t >= 0 for t in row['ticks']), row
        assert row['reason'], row
        if row['field'].endswith('.public_speed_base'):
            if row['entity_class'] == 'Troop':
                assert row['disposition'] == 'effective-value-compared', row
            else:
                assert row['entity_class'] in CACHE_INAPPLICABLE, row
                assert row['reason'] == CACHE_INAPPLICABLE[row['entity_class']], row
                assert row['disposition'] == 'inapplicable', row


def check_sweep(rows, names, mutation=None):
    exact_keys(rows, [(n, s) for n in names for s in ('blue', 'red')], lambda r: (r['case'], r['seat']))
    for summary in rows:
        assert summary['contract'] == VERSION
        runs = summary['rows']
        assert summary['runs'] == len(runs) == summary['cast_successes'] == 40, summary['case']
        assert {r['lead'] for r in runs} == set(range(-4, 36)), 'offsets'
        bad = []
        queries = 0
        for run in runs:
            assert 'error' not in run and run['contract'] == VERSION, run
            cast = run['cast']
            assert cast['python'] is True and (cast['before_export'] or cast['native'] is True), run
            assert run['fresh_troop_templates'], 'missing actual fresh-template proof'
            assert 1 <= run['compared_ticks'] <= 45, run
            check_ledger(run['applicability'])
            for rec in run['applicability']:
                assert all(t < run['compared_ticks'] for t in rec['ticks']), rec
            assert (run['raw_first'] is None) == (not run['raw_differences']), run
            if run['first'] is not None:
                bad.append(run)
            else:
                assert run['compared_ticks'] == 45 and not run['differences'], run
            queries += len(run['gate_queries'])
        assert summary['query_count'] == queries
        assert summary['queried_runs'] == sum(bool(r['gate_queries']) for r in runs)
        assert summary['raw_discrepancy_runs'] == sum(r['raw_first'] is not None for r in runs)
        assert summary['mismatches'] == len(bad)
        if mutation:
            spell, cls, equal_digest = mutation
            hits = [(run, d) for run in bad for d in run['differences']
                    if d['field'].endswith('.hit_ids') and d.get('spell_name') == spell
                    and d.get('entity_class') == cls
                    and isinstance(d.get('python'), list) and isinstance(d.get('native'), list)
                    and 7 not in d['python'] and 7 in d['native']
                    and any(q.get('allowed') is False and
                            str(q.get('source', '')).replace('_', '').lower() == spell.lower()
                            for q in run['gate_queries'])
                    and (not equal_digest or d.get('digest_equal') is True)]
            # This checks the intended difference's digest, not some earlier metadata discrepancy.
            assert hits, ('intended mutant hit-set difference not observed', summary['seat'], spell)
        else:
            assert not bad, (summary['case'], summary['seat'], bad[:1])
    return {f"{r['case']}/{r['seat']}": r['query_count'] for r in rows}


def check_descendants(rows):
    exact_keys(rows, [(n, s) for n in ('barblog', 'royal_delivery') for s in (0, 1)],
               lambda r: (r['case'], r['seat']))
    for row in rows:
        assert row['contract'] == VERSION and row.get('ok') is True and 'error' not in row, row
        assert row['first'] is None and not row['differences'], row
        assert row['source_class'] == {'barblog': 'RollingProjectile', 'royal_delivery': 'SpawnProjectile'}[row['case']]
        assert row['sentinel'] == 137.0 and row['child_ids'] and row['continuation'] == 20, row
        assert row['poisoned_child_detected'] is True and row['fresh_troop_templates'], row
        assert row['speed_checks'] and {r['child'] for r in row['speed_checks']} == set(row['child_ids']), row
        assert len({r['tick'] for r in row['speed_checks']}) == 20, row
        assert all(r['native_cache'] != 137.0 for r in row['speed_checks']), row
        check_ledger(row['applicability'])


def check_original_parity(fid, tag):
    """Unchanged digest/action/Clone fixtures, run once because strict phase1 aborted before them."""
    for label, cards, count in (('scen-b2-root', B2, 28), ('scen-b2-stats', B2, 28),
                                 ('scen-batchA', BATCH_A, 42)):
        rows = read(fid, tag, label)
        assert len(rows) == count and {r['card'] for r in rows} == set(cards), label
        assert len({(r['card'], r['scenario']) for r in rows}) == count, label
        for row in rows:
            assert row.get('native') == 'ok' and row.get('first_mismatch') is None and 'error' not in row, row
            check_actions(row['deploys'])
    rows = read(fid, tag, 'fu-paths')
    exact_keys(rows, [f'{n}/{s}' for n in FIRST_UPDATE_ACTIONS for s in ('blue', 'red')], lambda r: r['case'])
    for row in rows:
        assert row.get('native') == 'ok' and row.get('first_mismatch') is None and 'error' not in row, row
        check_actions(row['actions'], FIRST_UPDATE_ACTIONS[row['case'].split('/')[0]])
    rows = read(fid, tag, 'clone-bounds')
    exact_keys(rows, [(c, s) for c in ('back_edge', 'river_front', 'own_tower') for s in (0, 1)],
               lambda r: (r['case'], r['seat']))
    assert all(r.get('first') is None and 'error' not in r and r['cast'] == [True, True] for r in rows), rows
    rows = read(fid, tag, 'clone-recovery')
    exact_keys(rows, [('water_building_recovery', s) for s in (0, 1)], lambda r: (r['case'], r['seat']))
    assert all(r.get('ok') is True and r['ticks'] == 10 and len(r['positions']) == 10 for r in rows), rows


def validate(fid, tag):
    identity = read(fid, tag, 'identity')
    assert identity['contract'] == VERSION
    for path, expected in identity['inputs'].items():
        assert sha(Path(path)) == expected, ('input/evidence changed during run', path)
    assert identity['strict_status'] == 'FAIL preserved'
    for label in LABELS:
        assert (fid / f'{tag}-{label}.exit').read_text().strip() == '0', label
    coverage = {}
    for index, names in enumerate(SHARDS, 1):
        coverage.update(check_sweep(read(fid, tag, f'semantic-{index}'), names))
    for name in ('lightning', 'log', 'barblog', 'poison', 'vines', 'void', 'goblin_curse'):
        for seat in ('blue', 'red'):
            assert coverage[f'{name}/{seat}'] > 0, ('critical guard never queried', name, seat)
    check_sweep(read(fid, tag, 'mutA'), ['lightning'], ('Lightning', 'RankedStrikeArea', False))
    check_sweep(read(fid, tag, 'mutB'), ['log'], ('Log', 'RollingProjectile', True))
    check_descendants(read(fid, tag, 'descendants'))
    check_original_parity(fid, tag)
    return dict(contract=VERSION, status='SEMANTIC_PASS', utc=now(),
                identity_sha256=sha(fid / f'{tag}-identity.json'), baseline_runs=2480,
                strict_status='FAIL preserved', source_guard_queries=coverage,
                zero_query_sources=[key for key, value in coverage.items() if not value],
                limitations='Semantic contract only; zero-query sources lack event coverage. C56/final engine approval pending.')


def identity(fid, native_dirs):
    job = fid.parent
    original = json.loads((job / 'original-receipts.json').read_text())
    assert original['strict_status'] == 'FAIL preserved'
    paths = list(fid.glob('*.py')) + list(fid.glob('*.sh')) + [fid / 'pool.json']
    paths += list((job / 'tree/src').glob('*.rs')) + list((job / 'tree/py').rglob('*.py'))
    paths += list((job / 'tree').glob('*.py'))
    paths += [job / 'tree/py/gamedata.json', job / 'stats/gamedata.json',
              job / 'source-and-tools.json', job / 'original-receipts.json', job / 'SEMANTIC-SNAPSHOT-V1.md']
    for directory, (name, expected) in zip(native_dirs, NATIVES.items()):
        path = Path(directory) / 'clasher_core.abi3.so'
        assert sha(path) == expected, ('native identity', name)
        paths.append(path)
    paths += [Path(d) / 'es_common.py' for d in os.environ['PYTHONPATH'].split(':')
              if d and (Path(d) / 'es_common.py').is_file()]
    inputs = {str(p): sha(p) for p in sorted(set(paths))}
    for path, expected in original['inputs'].items():
        assert sha(Path(path)) == expected, ('original input/FAIL evidence changed', path)
        inputs[path] = expected
    return dict(contract=VERSION, utc=now(), host=socket.gethostname(), runner_pid=os.getppid(),
                pgid=os.getpgid(0), strict_status='FAIL preserved', inputs=inputs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fid', type=Path); parser.add_argument('tag')
    parser.add_argument('--identity', nargs=3)
    args = parser.parse_args()
    assert args.tag.startswith('semv1-') and args.tag.replace('-', '').isalnum(), 'fresh versioned tag required'
    if args.identity:
        with (args.fid / f'{args.tag}-identity.json').open('x') as out:
            json.dump(identity(args.fid, args.identity), out, indent=1)
    else:
        result = validate(args.fid, args.tag)
        final = args.fid / f'{args.tag}.semantic-pass.json'
        assert not final.exists()
        temp = final.with_suffix('.tmp')
        with temp.open('x') as out:
            json.dump(result, out, indent=1)
        os.rename(temp, final)
        print(json.dumps(result), flush=True)
