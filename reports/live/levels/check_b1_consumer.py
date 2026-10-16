"""Model-free integration checks; native acceptance is a separate owner gate.

Run with --levels FILE and --cards-source DIR. Imports the actual LevelRoot,
scaling table and B1 graph helper, without loading Resources or a native engine.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import numpy as np


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--levels', required=True, type=Path)
    parser.add_argument('--cards-source', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.cards_source / 'engine-cards/py/src'))
    levels = load('checked_live_levels', args.levels)
    graph = load('checked_b1_public_root', args.cards_source / 'engine-cards/public_root.py')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = sha(args.levels)
    assert before == 'a3289daf71ef7f1e4270e2b4f56542a31f07c00a86b645ab94c7fbadd3d032bf'
    assert sha(args.cards_source / 'engine-cards/public_root.py') == '0968768f08e930f9b72c1325c5ef33f542f5a7787d93b44d799a40cea4cae3b5'
    cases = []
    for seat in (0, 1):
        for level in (9, 11, 13):
            for reverse in (False, True):
                names = ['pad', 'unknown', 'GoblinGiant', 'SpearGoblinGiant']
                parent = dict(id=999, owner=seat, x=5., y=12., facing=[0, 1000],
                              king=False, champion=None, shield=0., mount=None,
                              stats=dict(name='GoblinGiant', max_hp=1000, damage=100,
                                         interval=1300, load=700,
                                         riders=dict(number=2, radius=900, shift=-22, max_angle=90)))
                parent['class'] = 'Troop'
                rider = copy.deepcopy(parent)
                rider['stats'].update(name='SpearGoblinGiant', max_hp=100, damage=10)
                rider.update(mount=99999, rider_rank=99)
                templates = {(2, 'Troop'): parent, (3, 'Troop'): rider}
                originals = copy.deepcopy(templates)
                rows = []
                for rank in (None, 0, 1):
                    dx, dy = (0., 0.) if rank is None else graph.rider_offset(parent, rank)
                    x, y = parent['x']+dx, parent['y']+dy
                    row = np.zeros(33)
                    row[0:3] = [x/18, y/32, 1]
                    row[4], row[9], row[28] = 1, .5, 1
                    rows.append((2 if rank is None else 3, row))
                if reverse:
                    rows.reverse()
                obs = NS(entity_ids=np.array([x[0] for x in rows]),
                         entity_features=np.array([x[1] for x in rows]),
                         entity_mask=np.ones(3, dtype=bool), global_features=np.zeros(32))
                info = NS(seat=seat, tick=5, own={}, packet=NS(observation=obs))
                legacy = NS(builder=NS(token_names=names), templates=templates, config={})
                modern = NS(**vars(legacy), repair_public_graph=graph.repair_public_graph)
                config = levels.Levels(own=level, opp=level)
                payload = lambda resource: json.loads(levels.LevelRoot(resource, config).payload(
                    info, {}, np.random.default_rng(123)))
                old, new = payload(legacy), payload(modern)
                old_riders = [e for e in old['entities'] if e['stats']['name'] == 'SpearGoblinGiant']
                assert all(e['mount'] == 99999 and e['rider_rank'] == 99 for e in old_riders)
                byid = {e['id']: e for e in new['entities']}
                riders = [e for e in new['entities'] if e['stats']['name'] == 'SpearGoblinGiant']
                assert {e['rider_rank'] for e in riders} == {0, 1}
                for e in riders:
                    p = byid[e['mount']]
                    assert p['stats']['name'] == 'GoblinGiant' and p['owner'] == e['owner'] == seat
                    assert e['hp'] == .5*int(100*levels.ratio(level))
                    assert e['stats']['damage'] == int(10*levels.ratio(level))
                for a, b in zip(old['entities'], new['entities']):
                    for key in ('mount', 'rider_rank'):
                        a.pop(key, None)
                        b.pop(key, None)
                    assert a == b  # graph repair preserves all other public/scaled fields
                assert templates == originals
                # Invalid public graphs propagate the helper's refusal; no fallback root.
                obs.entity_mask = obs.entity_ids != 2
                try:
                    payload(modern)
                except graph.PublicGraphError:
                    pass
                else:
                    raise AssertionError('parentless riders accepted')
                # Empty C56 board is exactly byte-equivalent through both Resources APIs.
                obs.entity_mask[:] = False
                assert payload(legacy) == payload(modern)
                cases.append(dict(seat=seat, level=level, reverse=reverse))
    assert sha(args.levels) == before
    print(json.dumps(dict(status='PASS', cases=cases, source_sha256=before,
                          actual_module=True, native_executed=False), indent=2))


if __name__ == '__main__':
    main()
