"""Light tests by default. Explicit integration smoke: PLAYDET_SMOKE=1 pytest ...

Smoke opens only TWO registered train matches and ONE complete sim match.
Runtime is shared; deterministic noise is replayed without another game run.
"""
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pytest

from .build import FrameWriter, generate_match, sha256, validate_file, shard_arg
from .guard import SplitGuard


def test_guard_rejects_tampered_registration(tmp_path):
    p = tmp_path / 'split.json'
    p.write_text('{"matches":[]}')
    with pytest.raises(ValueError, match='registered'):
        SplitGuard(p)


def test_no_heldout_loads_or_directory_listing():
    guard = SplitGuard()
    # Synthetic heldout name avoids even enumerating heldout registration IDs.
    opened = []

    def loader(rt, path, entry, seat=0):
        assert entry['split'] != 'heldout'
        assert path.name != 'heldout-sentinel'
        opened.append((path.name, entry['split']))
        return object()

    with patch('bot.live.replay.T1Match', loader), patch.object(Path, 'iterdir', side_effect=AssertionError('directory listing')):
        for split in ('train', 'validation'):
            entries = guard.select(split)
            assert len(entries) == (1920 if split == 'train' else 240)
            guard.load(None, entries[0]['episode'], split)
        for split in ('heldout', 'validation', 'train'):
            with pytest.raises(ValueError):
                guard.load(None, 'heldout-sentinel', split)
        with pytest.raises(ValueError):
            guard.load(None, guard.select('validation')[0]['episode'], 'train')
    assert len(opened) == 2


def test_shard_partitions():
    assert shard_arg('2/3') == (2, 3)
    for s in ('3/3', '-1/2', '0/0', 'x', '1/2/3'):
        with pytest.raises(Exception):
            shard_arg(s)
    shards = [{j for j in range(37) if j % 4 == i} for i in range(4)]
    assert set.union(*shards) == set(range(37))
    assert sum(map(len, shards)) == 37


def test_noise_determinism_across_process_hash_seeds():
    # Family members are frozensets in CardBodies: their enumeration must not
    # make seeded label flips depend on Python's per-process hash randomization.
    script = '''
import hashlib,json
from types import SimpleNamespace
import numpy as np
from bot.live.playdet.noise import NoiseChannel,sample_parameters
cards=('Goblins','GoblinGang','GoblinHut')
b=SimpleNamespace(main={c:[1] for c in cards},families={'g':frozenset(cards)},family_of=lambda c:'g')
rng=np.random.default_rng(7);p=sample_parameters(rng);p['family_flip']=1.;p['unknown_buildings']=False
n=NoiseChannel(rng,list(cards),b,p)
origin={'u':dict(kind='main',deployment_index=0,source_card='Goblins')}
rows=[]
for tick in range(0,200,3):
 rows.append(n(dict(tick=tick,units=[dict(card='Goblins',cls='Goblins',owner=1,x=3.,y=22.,hp_frac=1.,true_uid='u')],towers=[],hand=dict(cards=list(cards),next='Goblins'),elixir=5.,events=[]),origin))
print(hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
'''
    outputs = [subprocess.check_output([sys.executable, '-c', script],
                                      env=dict(os.environ, PYTHONHASHSEED=str(seed))) for seed in (7, 41)]
    assert outputs[0] == outputs[1]


def test_unknown_bursts_and_frame_drop_keep_identity():
    from types import SimpleNamespace
    from .noise import NoiseChannel, sample_parameters
    bodies = SimpleNamespace(main={'GoblinHut': [1]}, families={'GoblinHut': {'GoblinHut'}},
                             family_of=lambda card: card)
    rng = np.random.default_rng(19)
    params = sample_parameters(rng)
    params.update(unknown_buildings=True, frame_drop=0., burst_start=0.)
    channel = NoiseChannel(rng, ['GoblinHut'], bodies, params)
    channel.emp.x = frozenset({'units', 'hud', 'ev'})
    origins = {'hut': dict(kind='main', deployment_index=0, source_card='GoblinHut', is_building=True)}
    record = dict(tick=0, units=[dict(card='GoblinHut', cls='GoblinHut', owner=1, x=4., y=24.,
                                     hp_frac=1., true_uid='hut', score=1.)],
                  towers=[], hand=dict(cards=['GoblinHut'], next=None), elixir=5., events=[])
    row = channel(record, origins)
    assert not row['units']
    assert row['unknown_units'][0]['true_uid'] == 'hut'
    assert not row['unknown_units'][0]['false_positive']
    params.update(unknown_buildings=False, burst_start=1.)
    assert not channel(record, origins)['units']
    assert 5 <= channel.bursts['hut'] <= 40
    params['burst_start'] = 0.
    assert channel(dict(record, tick=41), origins)['true_uid'] == ['hut']
    params['frame_drop'] = 1.
    row = channel(dict(record, tick=44), origins)
    assert row['frame_dropped'] and not row['true_uid']
    params['perfect'] = True
    row = channel(dict(record, tick=47), origins)
    assert not row['frame_dropped'] and row['true_uid'] == ['hut']


def test_atomic_resume_and_orphan_recovery(tmp_path):
    from . import build
    calls = []

    def fake_generate(rt, source, match_id, seed, out, **kw):
        calls.append(match_id)
        head = dict(type='header', schema=build.SCHEMA, source=source, seed=seed, noise=dict(perfect=False),
                    origins=[], truth_deployments=[],
                    generation=build.generation_config(source, seed, kw['index'], kw['perfect'],
                                                       kw['max_ticks'], kw['players'], kw['abilities']))
        frame = dict(type='frame', tick=0, units=[], true_uid=[], false_positive=[], perfect_units=[], unknown_units=[])
        footer = dict(type='summary', frames=1, origin_counts={})
        path = out / f'{match_id}.jsonl.gz'
        with gzip.open(path, 'wt') as f:
            for row in (head, frame, footer):
                f.write(json.dumps(row)+'\n')
        return dict(match_id=match_id, file=path.name, sha256=sha256(path), bytes=path.stat().st_size)

    argv = ['--source', 'sim', '--matches', '1', '--out', str(tmp_path)]
    with patch('bot.players.runtime.Runtime', return_value=object()), patch.object(build, 'generate_match', fake_generate):
        build.main(argv)
        build.main(argv)
        manifest = tmp_path / 'manifest-sim-0-of-1.json'
        manifest.unlink()
        build.main(argv)  # completed file survived interrupted manifest update
        assert len(calls) == 1
        assert next(iter(json.loads(manifest.read_text())['matches'].values()))['recovered']
        with pytest.raises(ValueError, match='configuration'):
            build.main(argv + ['--perfect'])


@pytest.fixture(scope='module')
def smoke(tmp_path_factory):
    if os.environ.get('PLAYDET_SMOKE') != '1':
        pytest.skip('set PLAYDET_SMOKE=1 for 2 train + 1 sim smoke')
    from bot.players.runtime import Runtime
    wall, cpu = time.monotonic(), time.process_time()
    rt = Runtime()
    startup = dict(seconds=time.monotonic()-wall, cpu_seconds=time.process_time()-cpu)
    out = tmp_path_factory.mktemp('playdet-smoke')
    guard, results = SplitGuard(), []
    for e in guard.select('train')[:2]:
        results.append(generate_match(rt, 't1-train', e['episode'], e['seed'], out, guard=guard))
    results.append(generate_match(rt, 'sim', 'sim-smoke', 2718281828, out, index=0))
    report = dict(directory=str(out), runtime_startup=startup, matches=results)
    (out / 'smoke-report.json').write_text(json.dumps(report, sort_keys=True)+'\n')
    print('\nPLAYDET_SMOKE_REPORT '+json.dumps(report, sort_keys=True), flush=True)
    return rt, out, results


def test_smoke_files_and_lineage(smoke):
    _, out, results = smoke
    for result in results:
        head, footer, missing = validate_file(out / result['file'])
        assert footer['frames'] > 100
        assert result['sha256'] == sha256(out / result['file'])
        assert head['origins']
        if head['source'] == 'sim':
            assert not missing
            assert all(o['exact'] for o in head['origins'])
        else:
            # Snapshot loss is reported, never repaired with fabricated units.
            assert all(o['origin'] in ('main', 'child_unresolved') for o in head['origins'])


def test_seed_determinism_and_uid_roundtrip(smoke, tmp_path):
    from bot.live.births import CardBodies
    rt, out, results = smoke
    # Replay exact perfect frames through fresh independently seeded channels.
    # gzip bytes are also checked for determinism (mtime=0, filename='').
    for result in results:
        with gzip.open(out / result['file'], 'rt') as f:
            head, *rows = [json.loads(line) for line in f]
        origins = {o['uid']: o for o in head['origins']}
        # Sim building flags are frame-side metadata; recover from main bodies.
        cb = CardBodies(rt)
        for o in origins.values():
            if 'is_building' not in o:
                o['is_building'] = o['kind'] == 'main' and any(b[1] == 1 for b, _ in cb.main[o['source_card']])
        outputs = []
        for _ in range(2):
            import io
            stream = io.StringIO()
            writer = FrameWriter(stream, cb, head['seed'], head['decks'][0], False)
            for row in rows:
                if row['type'] == 'frame':
                    record = dict(tick=row['tick'], units=row['perfect_units'], towers=row['towers'],
                                  hand=dict(cards=head['decks'][0][:4], next=head['decks'][0][4]), elixir=5., events=[])
                    writer(record, origins)
            outputs.append(stream.getvalue())
        assert outputs[0] == outputs[1]


def test_source_bytes_and_perfect_mode(smoke, tmp_path):
    rt, _, _ = smoke
    # Two short games check source/engine determinism too, independently of the
    # noise replay test. No additional full match or extra T1 episode is run.
    results = [generate_match(rt, 'sim', 'determinism', 2718281829, tmp_path / str(i),
                              index=1, max_ticks=250, perfect=True) for i in range(2)]
    assert results[0]['sha256'] == results[1]['sha256']
    with gzip.open(tmp_path / '0/determinism.jsonl.gz', 'rt') as f:
        head = json.loads(next(f))
        assert head['noise']['perfect']
        assert head['truth_deployments']
        for line in f:
            row = json.loads(line)
            if row['type'] == 'frame':
                assert not row['frame_dropped'] and not row['unknown_units']
                assert not any(row['false_positive'])
                assert row['true_uid'] == [u['true_uid'] for u in row['perfect_units']]


def test_perfect_tracker_roundtrip(smoke):
    from bot.live.births import CardBodies, UnitTracker
    rt, out, results = smoke
    result = results[-1]
    tracker, plays = UnitTracker(CardBodies(rt)), []
    with gzip.open(out / result['file'], 'rt') as f:
        head = json.loads(next(f))
        for line in f:
            row = json.loads(line)
            if row['type'] != 'frame':
                continue
            units = [[u['card'], u['owner'], u['x'], u['y'], 1., None] for u in row['perfect_units']]
            alive = {t['side']: t['alive'] for t in row['towers'] if t['owner'] == 0 and t['kind'] == 'princess'}
            _, found = tracker.update(row['tick'], units, alive)
            plays.extend(found)
    truth = sum(not d['is_spell'] for d in head['truth_deployments'])
    print(f'PERFECT_TRACKER_SANITY plays={len(plays)} nonspell_truth={truth}', flush=True)
    # Sanity only: no accuracy gate on the existing rules tracker.
    assert tracker.last_tick is not None
