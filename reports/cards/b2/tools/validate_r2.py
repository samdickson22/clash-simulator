"""Validate a fresh B2 r2 evidence set; never infer success from a done marker.

Usage: validate_r2.py FID TAG [--identity NATIVE MUTANT_A MUTANT_B]
--identity writes an exclusive provenance receipt before the probes start.
Otherwise validates all child exit receipts and JSON evidence, then writes TAG.pass.json.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from datetime import datetime, timezone

SHARDS = (
    'zap fireball arrows rocket lightning log barblog snowball'.split(),
    'earthquake poison freeze tornado goblin_curse vines void electro_spirit'.split(),
    'ice_spirit rage heal clone bowler magic_archer executioner mega_knight'.split(),
    'electro_dragon ice_wizard electro_wizard fire_spirits hunter valkyrie princess'.split(),
)
B2 = 'Freeze Snowball Vines Rage DarkMagic GoblinCurse Clone Graveyard Heal Mirror'.split()
BATCH_A = 'GoblinCage SpearGoblins Bomber Tombstone Barbarians BattleRam MegaMinion BarbarianHut Mortar DartBarrell Witch Pekka SkeletonWarriors SkeletonDragons'.split()
FIRST_UPDATE_ACTIONS = dict.fromkeys(
    'zap fireball arrows rocket lightning log snowball earthquake poison freeze tornado goblin_curse fireball_hut'.split(), 1)
FIRST_UPDATE_ACTIONS.update(dict.fromkeys(
    'musketeer_projectile bomber_splash knight_melee tower_shot_drill balloon_death_bomb golem_death_damage'.split(), 0))
FIRST_UPDATE_ACTIONS.update(mighty_miner_ability=1, frozen_tombstone_death=3)
LABELS = [f'full-{i}' for i in range(1, 5)] + ['mutA', 'mutB', 'fu-paths', 'clone-checks',
          'scen-b2-root', 'scen-b2-stats', 'scen-batchA']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read(fid, tag, suffix):
    return json.loads((fid / f'{tag}-{suffix}.json').read_text())


def exact_keys(rows, expected, key):
    assert len(rows) == len(expected), (len(rows), len(expected))
    assert {key(row) for row in rows} == set(expected), 'missing/duplicate/unexpected evidence rows'


def check_sweep(rows, names, mutation=None):
    exact_keys(rows, [(n, s) for n in names for s in ('blue', 'red')], lambda r: (r['case'], r['seat']))
    for summary in rows:
        runs = summary['rows']
        assert summary['runs'] == len(runs) == 40 and summary['cast_successes'] == 40, summary
        assert {r['lead'] for r in runs} == set(range(-4, 36)), 'offsets'
        for run in runs:
            assert 'error' not in run, run
            cast = run['cast']
            assert cast['python'] is True and (cast['before_export'] or cast['native'] is True), run
        bad = [r for r in runs if r.get('first') is not None]
        assert summary['mismatches'] == len(bad), 'inconsistent mismatch count'
        if mutation:
            spell, cls, require_equal_digest = mutation
            hits = [r for r in bad if any(d['field'].endswith('.hit_ids') and
                    d.get('spell_name') == spell and d.get('entity_class') == cls
                    for d in r.get('differences', [])) and
                    (not require_equal_digest or r.get('digest_equal') is True)]
            assert hits, ('mutation not detected at intended hit-set field', summary['seat'], spell)
        else:
            assert not bad, (summary['case'], summary['seat'], bad[:1])
    return {f"{r['case']}/{r['seat']}": r['query_count'] for r in rows}


def check_actions(actions, expected_count=None):
    if expected_count is None:
        assert actions, 'expected at least one action'
    else:
        assert len(actions) == expected_count, (len(actions), expected_count)
    assert all(row[-2] is True and row[-1] is True for row in actions), actions


def validate(fid, tag):
    identity = read(fid, tag, 'identity')
    for path, expected in identity['inputs'].items():
        assert sha(Path(path)) == expected, ('input changed during run', path)
    for label in LABELS:
        assert (fid / f'{tag}-{label}.exit').read_text().strip() == '0', label
    coverage = {}
    for index, names in enumerate(SHARDS, 1):
        coverage.update(check_sweep(read(fid, tag, f'full-{index}'), names))
    # Guard-critical rows must really query the source while dash travel is active.
    for name in ('lightning', 'log', 'barblog', 'poison', 'vines', 'void', 'goblin_curse'):
        for seat in ('blue', 'red'):
            assert coverage[f'{name}/{seat}'] > 0, ('guard source never exercised', name, seat)
    check_sweep(read(fid, tag, 'mutA'), ['lightning'], ('Lightning', 'RankedStrikeArea', False))
    check_sweep(read(fid, tag, 'mutB'), ['log'], ('Log', 'RollingProjectile', True))
    for label, cards, count in (('scen-b2-root', B2, 28), ('scen-b2-stats', B2, 28),
                                 ('scen-batchA', BATCH_A, 42)):
        rows = read(fid, tag, label)
        assert len(rows) == count and {r['card'] for r in rows} == set(cards), label
        assert len({(r['card'], r['scenario']) for r in rows}) == count, label
        for row in rows:
            assert row.get('native') == 'ok' and row.get('first_mismatch') is None and 'error' not in row, row
            check_actions(row['deploys'])
    rows = read(fid, tag, 'fu-paths')
    exact_keys(rows, [f'{name}/{seat}' for name in FIRST_UPDATE_ACTIONS for seat in ('blue', 'red')],
               lambda row: row['case'])
    for row in rows:
        assert row.get('native') == 'ok' and row.get('first_mismatch') is None and 'error' not in row, row
        check_actions(row['actions'], FIRST_UPDATE_ACTIONS[row['case'].split('/')[0]])
    rows = read(fid, tag, 'clone-bounds')
    exact_keys(rows, [(c, s) for c in ('back_edge', 'river_front', 'own_tower') for s in (0, 1)],
               lambda r: (r['case'], r['seat']))
    for row in rows:
        assert row.get('first') is None and 'error' not in row and row['cast'] == [True, True], row
    rows = read(fid, tag, 'clone-recovery')
    exact_keys(rows, [('water_building_recovery', s) for s in (0, 1)], lambda r: (r['case'], r['seat']))
    assert all(r.get('ok') is True and r['ticks'] == 10 and len(r['positions']) == 10 for r in rows), rows
    return dict(status='PASS', utc=now(), identity_sha256=sha(fid / f'{tag}-identity.json'),
                baseline_runs=2480, source_guard_queries=coverage,
                mutation_A='ranked-strike hit set detected in both seats',
                mutation_B='rolling hit set detected in both seats while digest agrees',
                limitations='Source queries prove admission-path contact; zero-query sources need separate event evidence.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fid', type=Path)
    parser.add_argument('tag')
    parser.add_argument('--identity', nargs=3, metavar=('NATIVE', 'MUTANT_A', 'MUTANT_B'))
    args = parser.parse_args()
    assert args.tag != 'r2' and args.tag.replace('-', '').replace('_', '').isalnum(), 'fresh safe tag required'
    if args.identity:
        # This tool is started by the runner, so its parent PID identifies the runner (within the outer CPU lease).
        paths = [Path(n) / 'clasher_core.abi3.so' for n in args.identity]
        paths += list(args.fid.glob('*.py')) + list(args.fid.glob('*.sh'))
        tree = args.fid.parent / 'root' / 'engine-rs'
        paths += list((tree / 'src').glob('*.rs')) + list((tree / 'py').rglob('*.py'))
        paths += list(tree.glob('*.py')) + [args.fid / 'pool.json']
        # es_common supplies initial/config/digest helpers via the runner's explicit PYTHONPATH.
        paths += [Path(directory) / 'es_common.py' for directory in os.environ.get('PYTHONPATH', '').split(':')
                  if directory and (Path(directory) / 'es_common.py').is_file()]
        paths += [tree / 'py' / 'gamedata.json', args.fid.parent / 'rootstats' / 'gamedata.json']
        identity = dict(utc=now(), host=socket.gethostname(), runner_pid=os.getppid(), pgid=os.getpgid(0),
                        inputs={str(p): sha(p) for p in sorted(set(paths))})
        with (args.fid / f'{args.tag}-identity.json').open('x') as out:
            json.dump(identity, out, indent=1)
    else:
        result = validate(args.fid, args.tag)
        path = args.fid / f'{args.tag}.pass.json'
        assert not path.exists(), 'PASS receipt already exists'
        temp = path.with_suffix('.tmp')
        with temp.open('x') as out:
            json.dump(result, out, indent=1)
        os.rename(temp, path)
        print(json.dumps(result), flush=True)
