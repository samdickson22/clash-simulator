"""Resumable frozen C56 reconstruction plus independent D1 sidecars/audits."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
DATA = HERE.parent/'c56/data'
RUNTIME = DATA/'runtime-engine-v3b'
ORIGINAL = Path(os.environ.get('CLASHER_C56_RECON', str(DATA/'recon/engine-v3')))
os.environ['CLASHER_ROOT'] = str(RUNTIME)
sys.path[:0] = [str(RUNTIME/'src'), str(DATA/'scripts')]
import numpy as np
import c56_v3_bootstrap as cb
import extract_v3 as ex
from v3_common import write_parts
from clasher.rl import human_replay_v5 as v5
from clasher.rl.contract_v5 import ContractV5ObservationBuilder, CachedContractV5ActionMask
from clasher.rl.human_replay_demonstrations import parse_il_replay_record
from sidecar_observer import SidecarObserver, intent_targets

BUILDER = None


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, sort_keys=True)+'\n'); tmp.replace(path)


def initialize():
    global BUILDER
    cb.bind_runtime()
    BUILDER = ContractV5ObservationBuilder()


def pins():
    gates = json.loads((DATA/'qa/v3b/gates.json').read_text())
    runtime = cb.runtime_manifest()
    assert runtime['sha256'] == gates['runtime']['sha256']
    assert sha(Path(ex.__file__)) == gates['driver_sha256']
    assert gates['driver_sha256'].startswith('8e95786c')
    return dict(runtime=runtime, extractor_sha256=gates['driver_sha256'],
                source_sha256={n:sha(HERE/n) for n in ('derived_d1.py','own_cycle.py','sidecar_observer.py','replay_sidecars.py')})


def run_unit(args):
    key, destination = args
    out = Path(destination)
    receipt = out/'units'/f'{key}.json'
    if receipt.exists():
        value = json.loads(receipt.read_text())
        assert all(sha(out/name)==digest for name,digest in value['files'].items())
        assert not any(value['violations'])
        return value
    start = time.perf_counter(); cpu = time.process_time()
    original = ORIGINAL/f'{key}.npz'
    phase, stem = key.split('/')
    shard, number = (int(stem.split('-')[i]) for i in (1,3))
    pairs = ex.perspective_list(shard, phase)[number*48:(number+1)*48]
    records = {i:r for i,r in enumerate(cb.read_payloads(shard)) if i in {p[0] for p in pairs}}
    slugs = cb.slug_map(); masks = CachedContractV5ActionMask(BUILDER)
    with np.load(original, allow_pickle=False) as z:
        header = json.loads(str(z['header_json'].item()))
    parts = []; summaries = []; sidecars = []; audits = []; events = []
    coverage = np.zeros((21,7), np.int64)
    for index, side in pairs:
        seat = ('team','opponent').index(side)
        episode = shard*100000 + index*2 + seat
        match = parse_il_replay_record(records[index], slugs)
        with SidecarObserver(BUILDER) as observer:
            game = v5.reconstruct_perspective_v5(match, seat, BUILDER, mask_builder=masks,
                episode_id=episode, config=v5.ReconstructionConfigV5(tower_clamp=True), row_observer=observer)
        compact = v5.compact_demonstration_v5(game)
        # The frozen extractor appends its unsupervised terminal context after
        # the loop, without invoking row_observer. Its final battle is still
        # available, so capture that exact final state without changing code.
        if game.summary['terminal_context_row']:
            observer(observer.battle, seat, 2304)
        d1, audit = observer.arrays()
        assert len(d1['opp_elixir']) == len(compact['expert_actions'])
        d1.update(intent_targets(compact, d1, game.summary['cut_tick']))
        d1['episode_ids'] = compact['episode_ids']
        d1['submitted_ticks'] = compact['submitted_ticks']
        audit.update(episode_ids=compact['episode_ids'], submitted_ticks=compact['submitted_ticks'])
        parts.append(compact); summaries.append(game.summary); sidecars.append(d1); audits.append(audit)
        events.append(dict(episode_id=episode, events=observer.public_events))
        bins = np.minimum(compact['submitted_ticks']//300,20)
        known = (d1['opp_hand_known'] != 0).sum(1)
        for b in np.unique(bins):
            take = bins == b
            coverage[b,0] += take.sum()
            coverage[b,1] += (d1['opp_next_card'][take] != 0).sum()
            coverage[b,2:] += np.bincount(known[take], minlength=5)
    replay = out/'replay'/f'{key}.npz'; replay.parent.mkdir(parents=True, exist_ok=True)
    # Call the frozen driver's exact compact writer. Reuse is deliberately absent:
    # it would skip the observer and the legacy run_unit would delete v2 archives.
    fresh_header = write_parts(replay, parts, summaries, header, header.get('extra',{}))
    assert fresh_header == header, ('header', key)
    arrays_equal = 0
    with np.load(original, allow_pickle=False) as old, np.load(replay, allow_pickle=False) as new:
        assert set(old.files) == set(new.files)
        for name in old.files:
            if name == 'header_json': continue
            a,b = old[name],new[name]
            assert a.dtype == b.dtype and a.shape == b.shape and a.tobytes(order='C') == b.tobytes(order='C'), (key,name)
            arrays_equal += 1
    files = {str(replay.relative_to(out)):sha(replay)}
    merged_audit = None
    for kind, rows in [('sidecar',sidecars),('audit',audits)]:
        merged = {n:np.concatenate([r[n] for r in rows]) for n in rows[0]}
        path = out/kind/f'{key}.npz'; path.parent.mkdir(parents=True, exist_ok=True)
        v5.save_npz_deterministic(path, merged)
        files[str(path.relative_to(out))] = sha(path)
        if kind == 'audit': merged_audit = merged
    event_path = out/'events'/f'{key}.json.gz'; event_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(event_path,'wt') as f: json.dump(events,f)
    files[str(event_path.relative_to(out))] = sha(event_path)
    violations = merged_audit['violation'].sum(axis=0).tolist()
    value = dict(unit=key,perspectives=len(pairs),rows=header['rows'],arrays_equal=arrays_equal,
        summary_equal=True, violations=violations,coverage=coverage.tolist(), files=files,
        original_sha256=sha(original),wall_seconds=time.perf_counter()-start,cpu_seconds=time.process_time()-cpu)
    write(receipt,value)
    assert not any(violations), (key, 'truth audit', violations)
    return value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--workers',type=int,default=1)
    ap.add_argument('--partition',type=int,default=0)
    ap.add_argument('--partitions',type=int,default=1)
    ap.add_argument('--limit',type=int)
    ap.add_argument('--unit')
    ap.add_argument('--finalize',action='store_true')
    args = ap.parse_args()
    assert socket.gethostname() in ('127x01','127x03')
    assert 1 <= args.workers <= 64
    assert not subprocess.check_output(['who'],text=True).strip() or args.workers <= 16
    assert args.out.resolve().is_relative_to(HERE/'data')
    args.out.mkdir(parents=True,exist_ok=True)
    before = pins()
    keys = sorted(str(p.relative_to(ORIGINAL)).removesuffix('.npz')
                  for p in ORIGINAL.glob('*/shard-*.npz'))
    assert len(keys) == 1767
    if args.finalize:
        values = [json.loads((args.out/'units'/f'{k}.json').read_text()) for k in keys]
        assert sum(v['perspectives'] for v in values)==82231
        assert sum(v['rows'] for v in values)==64140802
        assert not any(sum(v['violations']) for v in values)
        files = {n:d for v in values for n,d in v['files'].items()}
        assert all(sha(args.out/n)==d for n,d in files.items())
        coverage = np.asarray([v['coverage'] for v in values]).sum(0)
        write(args.out/'coverage.json',dict(bin_width_ticks=300,columns=['rows','next_known','hand0','hand1','hand2','hand3','hand4'],counts=coverage.tolist(),
            fractions=np.divide(coverage[:,1:],coverage[:,0,None],out=np.zeros((21,6)),where=coverage[:,0,None]!=0).tolist()))
        write(args.out/'manifest.json',dict(passed=True,units=1767,perspectives=82231,rows=64140802,
            pins=before,files=files,violations=[0]*5,cpu_seconds=sum(v['cpu_seconds'] for v in values)))
        return
    keys = [args.unit] if args.unit else keys[args.partition::args.partitions]
    if args.limit: keys = keys[:args.limit]
    write(args.out/f'launch-{socket.gethostname()}-{args.partition}.json',dict(pid=os.getpid(),keys=keys,workers=args.workers,pins=before))
    started = time.perf_counter()
    with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize) as pool:
        for value in pool.map(run_unit,[(k,str(args.out)) for k in keys]):
            print(json.dumps({k:value[k] for k in ('unit','perspectives','rows','violations','wall_seconds')}),flush=True)
    assert pins() == before
    write(args.out/f'complete-{socket.gethostname()}-{args.partition}.json',dict(passed=True,units=len(keys),wall_seconds=time.perf_counter()-started,pins=before))


if __name__ == '__main__': main()
