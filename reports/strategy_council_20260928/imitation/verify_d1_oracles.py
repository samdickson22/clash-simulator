"""Instrument unchanged oracle drivers; all new receipts stay in imitation/."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import runpy
import sys
import time

import numpy as np
from derived_d1 import DerivedD1, PublicEvent

HERE = Path(__file__).resolve().parent
COUNCIL = HERE.parent
ROOT = COUNCIL.parents[1]
OUT = HERE / 'data/receipts/oracles'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


COUNTS = dict(elixir_checks=0, known_facts=0, known_fact_conflicts=0, collector=0, ability=0)


def checking_class(original, p16=False):
    class Checked(original):
        def __init__(self, prior, costs):
            super().__init__(prior, costs)
            self.d1 = DerivedD1(costs)

        def update(self, tick, events):
            super().update(tick, events)
            public = [PublicEvent(t, 'card', n) for t, n in events] if p16 else [
                PublicEvent(e.tick, e.kind, e.name, e.amount) for e in events]
            for event in public[len(self.d1.events):]:
                if event.kind in ('collector', 'ability'):
                    COUNTS[event.kind] += 1
            self.d1.update(tick, public)
            expected = self.elixir_units / 10000 if p16 else self.elixir
            assert self.d1.elixir == expected, ('elixir', tick, self.d1.elixir, expected)
            assert self.d1.refill == self.refill, ('refill', tick)
            assert len(self.d1.queue) == self.queue_len
            known = self.d1.derived()
            for name in filter(None, known['hand_known']):
                assert np.all(np.any(self.states[:, :4] == self.ids[name], axis=1)), ('hand', tick, name)
                COUNTS['known_facts'] += 1
            for i, name in enumerate(known['cycle_positions']):
                if name is not None:
                    assert np.all(self.states[:, 4+i] == self.ids[name]), ('queue', tick, i, name)
                    COUNTS['known_facts'] += 1
            COUNTS['elixir_checks'] += 1
    return Checked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('suite', choices=['full', 'collector', 'confirmation', 'srp', 'unit', 'finish'])
    ap.add_argument('--worker', type=int, default=0)
    ap.add_argument('--workers', type=int, default=1)
    args = ap.parse_args()
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.suite == 'finish':
        receipts = [json.loads((OUT / f'{name}.json').read_text()) for name in
                    ['unit-0', 'full-0', 'collector-0'] + [f'confirmation-{i}' for i in range(4)] + [f'srp-{i}' for i in range(3)]]
        assert all(r['passed'] for r in receipts)
        assert sum(r['games'] for r in receipts if r['suite']=='confirmation') == 256
        assert sum(r['counts']['elixir_checks'] for r in receipts if r['suite']=='confirmation') == 209575
        assert sum(r['counts']['elixir_checks'] for r in receipts if r['suite']=='srp') == 23058
        result = dict(passed=True, tasks=['T1'], receipts=receipts,
                      counts={k:sum(r['counts'][k] for r in receipts) for k in COUNTS},
                      source_sha256={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in
                                     ('derived_d1.py','own_cycle.py','test_derived_d1.py','verify_d1_oracles.py')})
        write(HERE/'data/receipts/T1-PASS.json', result)
        print(json.dumps(result)); return
    games = 0
    if args.suite == 'unit':
        import unittest
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(HERE), 'test_derived_d1.py'))
        assert result.wasSuccessful()
    elif args.suite == 'srp':
        folder = COUNCIL/'srp-public'
        sys.path.insert(0, str(folder))
        oracle = load('derived_public_state', folder/'derived_public_state.py')
        oracle.DerivedPublicState = checking_class(oracle.DerivedPublicState, True)
        audit = load('d1_srp_audit', folder/'audit_derived.py')
        home = OUT/f'srp-worker{args.worker}'
        home.mkdir(exist_ok=True)
        link = home/'superseded-v2'
        if not link.exists(): link.symlink_to(folder/'superseded-v2', target_is_directory=True)
        (home/'results').mkdir(exist_ok=True)
        audit.HERE = home
        sys.argv = [sys.argv[0], '--worker', str(args.worker)]
        audit.main()
        games = len(json.loads((home/'results'/f'derived-audit-{args.worker}.json').read_text()))
    else:
        folder = COUNCIL/'engine-speed/stage5'
        sys.path.insert(0, str(folder))
        oracle = load('derived_public_state', folder/'derived_public_state.py')
        oracle.DerivedPublicState = checking_class(oracle.DerivedPublicState)
        if args.suite in ('full', 'collector'):
            import qualify
            qualify.write = lambda p, value: write(OUT/f'oracle-{p.name}', value)
            if args.suite == 'full':
                mod = load('test_derived', folder/'test_derived.py')
                mod.full_games(); games = 8
            else:
                runpy.run_path(str(folder/'test_collector.py')); games = 1
        else:
            from clasher.data import CardDataLoader
            loader = CardDataLoader()
            prior = json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())
            costs = {n:float(loader.get_card(n).mana_cost) for d in prior['decks'] for n in d['cards']}
            paths = sorted((folder/'confirmation').glob('pair*-seat*.json'))
            assert len(paths) == 256
            for path in paths[args.worker::args.workers]:
                record = json.loads(path.read_text())
                tracker = oracle.DerivedPublicState(prior, costs)
                pending = [oracle.PublicEvent(t,'card',name) for t,seat,a,name,ok in record['actions']
                           if seat != record['seat'] and ok and a < 2304]
                events = []; index = 0; checks = 0
                for tick in range(90, record['ticks'], 5):
                    while index < len(pending) and pending[index].tick < tick:
                        events.append(pending[index]); index += 1
                    tracker.update(tick, events); checks += 1
                assert checks == record['derived_checks'], (path, checks, record['derived_checks'])
                games += 1
                print(json.dumps(dict(game=path.name, checks=checks)), flush=True)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    receipt = dict(passed=True, suite=args.suite, worker=args.worker, games=games, counts=COUNTS,
                   wall_seconds=time.perf_counter()-start, cpu_seconds=usage.ru_utime+usage.ru_stime)
    write(OUT/f'{args.suite}-{args.worker}.json', receipt)
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
