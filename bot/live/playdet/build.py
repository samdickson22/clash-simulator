"""One atomic deterministic gzip JSONL per match; one manifest per job shard.

Example: python -m bot.live.playdet.build --source sim --shard 0/16 --out DIR
No process pool: --threads 1 bounds torch/BLAS and is required by this generator.
"""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from . import SCHEMA
from .guard import SplitGuard, DATA, SPLIT_SHA
from .origins import origin_counts


def generation_config(source, seed, index, perfect, max_ticks, players, abilities):
    package = Path(__file__).parent
    files = ('__init__.py', 'build.py', 'guard.py', 'origins.py', 'noise.py', 'sources.py')
    h = hashlib.sha256()
    for name in files:
        h.update(name.encode())
        h.update((package / name).read_bytes())
    return dict(source=source, seed=int(seed), index=index, perfect=bool(perfect), max_ticks=max_ticks,
                players=list(players) if source == 'sim' else None,
                abilities=bool(abilities) if source == 'sim' else None,
                implementation_sha256=h.hexdigest(),
                empirical_sha256=sha256(package.parent / 'empirical-val.json'))


def dumps(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(dumps(data)+'\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def validate_file(path):
    """Reject broken joins, missing sim mains, bad FP flags, or partial streams."""
    with gzip.open(path, 'rt') as f:
        head = json.loads(f.readline())
        if head.get('schema') != SCHEMA or head.get('type') != 'header':
            raise ValueError('bad header')
        origins = {o['uid']: o for o in head['origins']}
        if len(origins) != len(head['origins']):
            raise ValueError('duplicate true uid')
        main = Counter()
        for o in origins.values():
            dep = o['deployment_index']
            if dep is not None and not 0 <= dep < len(head['truth_deployments']):
                raise ValueError('invalid deployment index')
            if o['kind'] == 'main':
                if dep is None:
                    raise ValueError('main body without deployment')
                main[dep] += 1
            if o['kind'] in ('spawn', 'death') and o['parent_uid'] not in origins:
                raise ValueError('child without exact body parent')
            if o['kind'] == 'child_unresolved' and (o['exact'] or o['parent_uid'] is not None):
                raise ValueError('invented exact T1 child origin')
        missing = [d['index'] for d in head['truth_deployments'] if not d['is_spell'] and not main[d['index']]]
        if head['source'] == 'sim' and missing:
            raise ValueError(f'sim deployments missing main bodies: {missing}')
        frames, previous, summary = 0, -1, None
        for line in f:
            row = json.loads(line)
            if row['type'] == 'summary':
                summary = row
                if f.read().strip():
                    raise ValueError('records after summary')
                break
            if row['type'] != 'frame' or row['tick'] <= previous:
                raise ValueError('nonmonotonic frames')
            previous, frames = row['tick'], frames+1
            if not (len(row['units']) == len(row['true_uid']) == len(row['false_positive'])):
                raise ValueError('detection/UID alignment')
            perfect = {u['true_uid'] for u in row['perfect_units']}
            if not perfect <= origins.keys():
                raise ValueError('perfect unit missing origin')
            for u in row['perfect_units']:
                if u.get('origin_kind') == 'ability':
                    event = head['origin_events'][u['origin_event_index']]
                    if event['uid'] != u['true_uid'] or event['tick'] > row['tick']:
                        raise ValueError('invalid ability reappearance join')
            for unit, uid, fp in zip(row['units'], row['true_uid'], row['false_positive']):
                if len(unit) != 6 or (uid is None) != fp or uid is not None and uid not in perfect:
                    raise ValueError('invalid noisy detection lineage')
            for u in row['unknown_units']:
                if u['true_uid'] not in perfect:
                    raise ValueError('unknown unit lost lineage')
        if summary is None or summary['frames'] != frames:
            raise ValueError('missing/inconsistent footer')
        if not frames:
            raise ValueError('empty match stream')
    return head, summary, missing


class FrameWriter:
    def __init__(self, stream, bodies, seed, deck, perfect):
        import numpy as np
        from .noise import NoiseChannel, sample_parameters
        self.bodies = bodies
        rng = np.random.default_rng(seed)
        self.parameters = sample_parameters(rng, perfect)
        self.channel = NoiseChannel(rng, deck, bodies, self.parameters)
        self.stream, self.frames, self.perfect_detections = stream, 0, 0

    def __call__(self, record, origins):
        row = self.channel(record, origins)
        row.update(type='frame', tick=int(record['tick']), perfect_units=record['units'])
        self.stream.write(dumps(row)+'\n')
        self.frames += 1
        self.perfect_detections += len(record['units'])


def generate_match(rt, source, match_id, seed, out, *, index=0, guard=None,
                   perfect=False, max_ticks=None, players=('v1', 'scripted-pressure'), abilities=True):
    from bot.live.births import CardBodies
    from .sources import t1_source, sim_source, sim_decks
    if source not in ('t1-train', 't1-validation', 'sim') or Path(match_id).name != match_id:
        raise ValueError('invalid source/match ID')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f'{match_id}.jsonl.gz'
    wall, cpu = time.monotonic(), time.process_time()
    if source.startswith('t1-'):
        guard = guard or SplitGuard()
        entry = guard.check(match_id, source[3:])
        deck = entry['decks'][0]
    else:
        deck = sim_decks(rt, index, seed)[0]
    # Frames spool to disk until final truth/origins are known; RAM does not
    # grow with serialized frames. T1Match itself loads its native recordings.
    with tempfile.TemporaryFile(mode='w+t', dir=out) as frames:
        emit = FrameWriter(frames, CardBodies(rt), seed, deck, perfect)
        if source.startswith('t1-'):
            metadata = t1_source(rt, guard, match_id, source[3:], emit, max_ticks)
        else:
            metadata = sim_source(rt, index, seed, emit, max_ticks or 6001, players, abilities)
        head = dict(type='header', schema=SCHEMA, match_id=match_id, source=source, seed=int(seed),
                    frame='our:seat0,bottom;18x32', split_sha256=SPLIT_SHA if source.startswith('t1-') else None,
                    noise=emit.parameters,
                    generation=generation_config(source, seed, index, perfect, max_ticks, players, abilities),
                    runtime_pins=rt.pins, **metadata)
        summary = dict(type='summary', frames=emit.frames, perfect_detections=emit.perfect_detections,
                       origin_counts=origin_counts(metadata['origins'] + metadata.get('origin_events', [])))
        fd, temp = tempfile.mkstemp(prefix='.'+match_id, suffix='.tmp', dir=out)
        try:
            with os.fdopen(fd, 'wb') as raw:
                with gzip.GzipFile(fileobj=raw, mode='wb', filename='', mtime=0, compresslevel=6) as gz:
                    gz.write((dumps(head)+'\n').encode())
                    frames.seek(0)
                    for line in frames:
                        gz.write(line.encode())
                    gz.write((dumps(summary)+'\n').encode())
                raw.flush()
                os.fsync(raw.fileno())
            _, _, missing = validate_file(temp)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    return dict(match_id=match_id, file=path.name, sha256=sha256(path), bytes=path.stat().st_size,
                frames=emit.frames, seconds=time.monotonic()-wall, cpu_seconds=time.process_time()-cpu,
                origin_counts=summary['origin_counts'], unobserved_nonspell_deployments=len(missing))


def shard_arg(value):
    try:
        i, n = map(int, value.split('/'))
        if not 0 <= i < n:
            raise ValueError()
        return i, n
    except ValueError:
        raise argparse.ArgumentTypeError('shard must be i/N with 0 <= i < N') from None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, choices=('t1-train', 't1-validation', 'sim'))
    ap.add_argument('--shard', type=shard_arg, default=(0, 1))
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--threads', type=int, choices=(1,), default=1)
    ap.add_argument('--seed', type=int, default=2718281828)
    ap.add_argument('--matches', type=int, default=2000, help='global sim count before shard selection')
    ap.add_argument('--limit', type=int, help='smoke only: first N matches in this shard')
    ap.add_argument('--max-ticks', type=int, help='smoke only: truncate the source')
    ap.add_argument('--perfect', action='store_true', help='bypass all observation noise (perfect_units always retained)')
    ap.add_argument('--players', default='v1,scripted-pressure')
    ap.add_argument('--no-abilities', action='store_true', help='keep the stock play_match card-only loop')
    args = ap.parse_args(argv)
    if args.seed < 0 or args.matches < 1 or args.limit is not None and args.limit < 1:
        ap.error('seed must be nonnegative; matches and limit must be positive')
    if args.max_ticks is not None and args.max_ticks < 1:
        ap.error('max-ticks must be positive')
    players = tuple(args.players.split(','))
    if len(players) != 2:
        ap.error('--players requires exactly two comma-separated pool names')
    # Set these before numpy/torch/runtime import. No subprocess pool or lease.
    for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    i, n = args.shard
    guard = SplitGuard() if args.source.startswith('t1-') else None
    if guard:
        entries = guard.select(args.source[3:])
        jobs = [(j, e['episode'], e['seed']) for j, e in enumerate(entries) if j % n == i]
    else:
        jobs = [(j, f'sim-{args.seed+j:016d}', args.seed+j) for j in range(args.matches) if j % n == i]
    if args.limit:
        jobs = jobs[:args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / f'manifest-{args.source}-{i}-of-{n}.json'
    config = dict(schema=SCHEMA, source=args.source, shard=[i, n], seed=args.seed,
                  matches=args.matches if not guard else len(entries), max_ticks=args.max_ticks,
                  perfect=args.perfect, players=list(players) if not guard else None,
                  abilities=not args.no_abilities if not guard else None,
                  split_sha256=SPLIT_SHA if guard else None)
    # Different topologies must not overlap the same match files. All shards
    # briefly serialize only setup, then work independently under shard locks.
    with (args.out / '.setup.lock').open('w') as setup_lock:
        fcntl.flock(setup_lock, fcntl.LOCK_EX)
        run_path = args.out / f'run-{args.source}.json'
        run_config = dict(config, shard=[None, n])
        if run_path.exists() and json.loads(run_path.read_text()) != run_config:
            raise ValueError('output run configuration differs; use a separate output directory')
        atomic_json(run_path, run_config)
    # Same-shard retries serialize; different shards write independent manifests.
    with (args.out / f'.lock-{args.source}-{i}-of-{n}').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = dict(config=config, matches={})
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            if manifest['config'] != config:
                raise ValueError('manifest configuration differs; use a separate output directory')
        rt = None
        for index, match_id, seed in jobs:
            path = args.out / f'{match_id}.jsonl.gz'
            existing = manifest['matches'].get(match_id)
            if path.exists():
                head, summary, missing = validate_file(path)
                expected = generation_config(args.source, seed, index, args.perfect, args.max_ticks, players,
                                             not args.no_abilities)
                if head.get('generation') != expected:
                    raise ValueError('existing match has different configuration')
                digest = sha256(path)
                if existing and existing['sha256'] != digest:
                    raise ValueError('finished match checksum mismatch')
                if existing is None:
                    manifest['matches'][match_id] = dict(match_id=match_id, file=path.name, sha256=digest,
                                                        bytes=path.stat().st_size, frames=summary['frames'],
                                                        origin_counts=summary['origin_counts'], recovered=True,
                                                        unobserved_nonspell_deployments=len(missing))
                    atomic_json(manifest_path, manifest)
                print(dumps(dict(match_id=match_id, skipped=True)), flush=True)
                continue
            if existing:
                raise ValueError('manifest references a missing finished file')
            if rt is None:
                from bot.players.runtime import Runtime
                rt = Runtime()
            result = generate_match(rt, args.source, match_id, seed, args.out, index=index, guard=guard,
                                    perfect=args.perfect, max_ticks=args.max_ticks, players=players,
                                    abilities=not args.no_abilities)
            manifest['matches'][match_id] = result
            atomic_json(manifest_path, manifest)
            print(dumps(result), flush=True)


if __name__ == '__main__':
    main()
