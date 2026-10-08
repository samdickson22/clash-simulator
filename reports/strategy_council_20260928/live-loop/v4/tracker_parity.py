"""Exact frozen-v3 comparison on public S4 development or train replay traces.

Run on a fleet CPU with BLAS threads=1. Never reads evaluator truth fields into
trackers. Assertions compare IEEE float bits, full lattice, hand masses, seeded
roots and RNG states after every update; tolerances are not used.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace
import numpy as np
from clasher.live.belief import Belief, StratifiedRng
from clasher.live.contracts import Frame, Observation
from clasher.live.loading import COUNCIL, tracker_class
from clasher.live.runtime import quantiles
from clasher.live.tracker import TrackerV3


def exact(value):
    if isinstance(value, (float, np.floating)):
        return ('float64', struct.pack('!d', value).hex())
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(v) for v in value]
    return value


def check(a, b):
    assert exact(a.distribution()) == exact(b.distribution()), 'distribution bits'
    assert exact(a.hand_masses()) == exact(b.hand_masses()), 'hand mass bits'
    assert a._p.tobytes() == b._p.tobytes(), 'current lattice bits'
    assert a.p.tobytes() == b.p.tobytes(), 'committed lattice bits'
    for ah, bh in ((a.hands, b.hands), (a._hands, b._hands)):
        assert len(ah) == len(bh)
        for (x, w), (y, v) in zip(ah, bh):
            assert exact(w) == exact(v)
            assert exact(x.derived()) == exact(y.derived()), 'cycle state'


def dev(path, limit):
    data = json.loads(gzip.decompress(path.read_bytes()))
    prior = json.loads((COUNCIL/'search-noise-s4/runtime/support/human_deck_catalog.json').read_text())
    trackers, timings, count = {}, [[], []], 0
    digest = hashlib.sha256()
    for row in data['rows']:
        key = (row['seat'], row['variant'])
        if key not in trackers:
            q, p = {'T2-N90': (.9, .9), 'T2-N97': (.97, .97), 'T2-N64': (180/280, 180/270)}[key[1]]
            kwargs = dict(body_cards=data['body_cards'], recall=q, precision=p, calibration=.11040000000000028)
            trackers[key] = [(cls(prior, data['costs'], **kwargs), np.random.default_rng(6108))
                             for cls in (tracker_class(), TrackerV3)]
        pair = trackers[key]
        outputs = []
        for i, (t, rng) in enumerate(pair):
            start = time.perf_counter_ns()
            t.update_public(row['tick'], [SimpleNamespace(**e) for e in row['events']], row['bodies'])
            d = t.distribution()
            roots = [t.sample(StratifiedRng(rng, j, 4, d['concentrated'])) for j in range(4)]
            timings[i].append((time.perf_counter_ns()-start)/1e6)
            outputs.append((d, roots, rng.bit_generator.state))
        assert exact(outputs[0]) == exact(outputs[1]), (path, count, key, row['tick'])
        check(pair[0][0], pair[1][0])
        digest.update(repr(exact(outputs[0])).encode())
        count += 1
        if limit and count >= limit:
            break
    return count, timings, digest.hexdigest()


def phase(path, limit):
    from clasher.rl.live_inference_contract import parse_public_vision_frame, LIVE_VISION_SCHEMA_VERSION
    config = json.loads(path.with_name('config.json').read_text())
    assert config['source']['kind'] == 'replay' and config['source']['split'] == 'train'
    # Recheck frozen split membership independently before opening public logs.
    split = json.loads((Path(args.split)).read_text())
    assert any(r['split'] == 'train' and str(r['seed']) == config['source']['episode'].split('-')[-1]
               for r in split['matches'])
    pair = [Belief(dict(config['belief'], frozen_tracker=frozen)) for frozen in (True, False)]
    timings, count, digest = [[], []], 0, hashlib.sha256()
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            row = json.loads(line)
            if row['metric'] != 'processed':
                continue
            p = dict(row['public'])
            outer = {k: p.pop(k) for k in ('episode_id', 'frame_id', 'timestamp_ms')}
            public = parse_public_vision_frame(dict(outer, schema_version=LIVE_VISION_SCHEMA_VERSION, public=p))
            frame = Frame(public.episode_id, row['sequence'], row['produced_at'], row['produced_at'],
                          row.get('timestamp_ms', public.timestamp_ms), None)
            observation = Observation(frame, public, tuple(row['event_candidates']), row.get('phase', 'normal'), 0.)
            outputs = []
            for i, belief in enumerate(pair):
                begin = time.perf_counter_ns()
                result = belief.update(observation)
                timings[i].append((time.perf_counter_ns()-begin)/1e6)
                outputs.append((result.opponent, result.roots, result.own, belief.rng.bit_generator.state))
            assert exact(outputs[0]) == exact(outputs[1]), (path, count)
            check(pair[0].tracker, pair[1].tracker)
            digest.update(repr(exact(outputs[0])).encode())
            count += 1
            if limit and count >= limit:
                break
    return count, timings, digest.hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', nargs='*', type=Path, default=[])
    parser.add_argument('--phase', nargs='*', type=Path, default=[])
    parser.add_argument('--split', type=Path)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from clasher.live import tracker, lattice
    sources = [Path(tracker.__file__), Path(lattice.__file__), Path(lattice.__file__).with_suffix('.rs'),
               COUNCIL/'search-noise-s4/tracker_v3.py', COUNCIL/'search-noise-s4/tracker_v2.py']
    if lattice._kernel is not None:
        sources.append(lattice.LIBRARY)
    result = dict(command=sys.argv, native=lattice._kernel is not None,
                  source_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, equal=True, updates=0, traces=[], evidence='float64 bits; both full lattices; hand masses; cycles; four seeded roots; RNG state')
    all_times = [[], []]
    for kind, paths, function in [('dev', args.dev, dev), ('phase-a-train', args.phase, phase)]:
        for path in paths:
            count, times, digest = function(path, args.limit)
            result['updates'] += count
            row = dict(kind=kind, path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                       updates=count, output_digest=digest, before_ms=quantiles(times[0]), after_ms=quantiles(times[1]))
            result['traces'].append(row)
            for i in range(2):
                all_times[i].extend(times[i])
            result['before_ms'], result['after_ms'] = map(quantiles, all_times)
            args.output.write_text(json.dumps(result, indent=2)+'\n')
            print(json.dumps(row), flush=True)
