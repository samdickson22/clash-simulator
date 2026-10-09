"""Bounded real-validation layer/lockstep probe; never a full equality gate.

Run under lockstep_resources_v4.py on01 with a private02 cache connection.
No pixel/checkpoint/cache payloads are written. Outputs are compact receipts.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

import torch

from clasher.vision import l1_v4 as runtime
from decoder_records_v4 import extract_event_records
from shared_model_v4 import SharedModel
from shared_temporal_v4 import prefix, tail
from lockstep_replay_v4 import (LockstepReplay, CausalWork, validate_bundle, open_readers,
    sha, tensor_equal, json_bytes, nonclock, resource_guard, gpu_snapshot)


def difference(expected, actual):
    return [k for k in expected if not tensor_equal(expected[k], actual[k])]


def compare_chunks(fn, args, references, batch):
    failures = []; torch.cuda.synchronize(); start = time.perf_counter()
    try:
        for offset in range(0, len(references), batch):
            result = fn(*(arg[offset:offset+batch] for arg in args))
            for i in range(len(next(iter(result.values())))):
                keys = difference(references[offset+i], {k: v[i:i+1] for k, v in result.items()})
                if keys:
                    failures.append(dict(slot=offset+i, fields=keys))
    except torch.cuda.OutOfMemoryError:
        gc.collect(); torch.cuda.empty_cache()
        return dict(batch=batch, exact=None, error='8GiB development allocation cap',
                    seconds=time.perf_counter()-start)
    torch.cuda.synchronize()
    return dict(batch=batch, exact=not failures, mismatches=failures,
                seconds=time.perf_counter()-start)


def reference_record(model, branch, cards, bodies, ep, seq, stamp, value):
    return dict(schema='clasher.v4.decoder-frame.v1', source_seq=seq, episode_id=ep, timestamp_ms=stamp,
        bodies=runtime.decode_bodies(model.encoded, bodies, .1),
        event_peaks=extract_event_records(model.event, cards, stamp),
        causal_own_hud_cards=[c for c, _ in branch.own_plays],
        hud={k: value[k] for k in ('own_hand', 'next_card', 'own_elixir',
                                 'hud_card_probabilities', 'clock_seconds', 'phase')})


def quarantine_prefix(episodes, limit):
    # Explicit allowlisted reference only; no traversal, heldout or mutation.
    code = """import gzip,json,hashlib,sys
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher-v4-cache/pending-equality/decoder-vector-r1/epoch-03')
assert hashlib.sha256((root/'complete.json').read_bytes()).hexdigest()=='a4d885946c72557f47a0cd2fa790c82ee9100ce6804abf15cc1186020e5f0787'
episodes=json.loads(sys.argv[1]);limit=int(sys.argv[2])
for ep in episodes:
 assert ep.startswith('v4-phase-a-') and '/' not in ep
 for branch in range(1,10):
  with gzip.open(root/f'body-{branch}'/f'{ep}-decoder.jsonl.gz','rt') as f:
   for seq in range(limit):
    row=f.readline()
    assert row,'Incomplete reference prefix'
    print(json.dumps([ep,branch,seq,json.loads(row)]))
"""
    command = ' '.join(shlex.quote(x) for x in (
        '/mpac/sdicks02/envs/clasher-gpu/bin/python', '-B', '-c', code,
        json.dumps(episodes), str(limit)))
    output = subprocess.check_output(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                                      '127x02', command], text=True)
    return {(ep, branch, seq): json_bytes(row) for ep, branch, seq, row in map(json.loads, output.splitlines())}


@torch.inference_mode()
def probe(a):
    import cv2
    from clasher.data import CardDataLoader
    resource_guard(); torch.set_num_threads(1); cv2.setNumThreads(1)
    free, total = torch.cuda.mem_get_info()
    torch.cuda.set_per_process_memory_fraction(min(7.25*1024**3/total, (free-8*1024**3)/total))
    if a.output.exists():
        raise ValueError('Fresh receipt required')
    manifest, receipts, metadata = validate_bundle(a.bundle)
    eps = sorted(receipts)[:a.matches]
    readers = open_readers(a, {ep: receipts[ep] for ep in eps})
    checkpoint = a.bundle/'fit/model'/f'epoch-{a.epoch}.pt'
    state = torch.load(checkpoint, map_location='cpu', weights_only=True)
    os.environ['CLASHER_ROOT'] = str(a.bundle/'runtime')
    loader = CardDataLoader()
    spells = [c for c in state['cards'] if str(loader.get_card(c).card_type).lower() == 'spell']
    base = runtime.PerceptionV4(len(state['cards']), len(state['bodies']))
    base.load_state_dict(state['model']); base = base.cuda().eval()
    pixels = {}; pairs = {}; fetch_start = time.perf_counter()
    for ep in eps:
        # Read owner02 service only, never any01 pixel cache.
        pixels[ep] = readers[ep].get(ep, list(range(a.frames)), raw=True)
        pairs[ep] = [runtime.prepare_pixels(im) for im in pixels[ep]]
    fetch_seconds = time.perf_counter()-fetch_start
    tensors = lambda rows: torch.from_numpy(__import__('numpy').stack(rows)).permute(0, 3, 1, 2).cuda().float()/255
    arena = tensors([pairs[ep][0][0] for ep in eps]); hud = tensors([pairs[ep][0][1] for ep in eps])
    encoded = [base.encode(arena[i:i+1], hud[i:i+1]) for i in range(len(eps))]
    # Layer probes are not sequential-runtime admission: full16-token contexts
    # are constructed from current pixel features solely to probe kernel shapes.
    cache = torch.cat([e['features'][:, None].expand(-1, 16, -1, -1, -1).contiguous() for e in encoded])
    ages = torch.arange(15, -1, -1, device='cuda').float()[None].expand(len(eps), -1).contiguous()*50
    valid = torch.ones(len(eps), 16, dtype=torch.bool, device='cuda')
    births = torch.zeros(len(eps), 2, 64, 36, device='cuda')
    mixed = [prefix(base.temporal, cache[i:i+1], ages[i:i+1], valid[i:i+1]) for i in range(len(eps))]
    event = [tail(base.temporal, m, births[i:i+1], valid[i:i+1]) for i, m in enumerate(mixed)]
    mix = torch.cat(mixed)
    evidence = dict(schema='clasher.v4.lockstep-bounded-probe.v1', formal_admitted=False,
        epoch=a.epoch, matches=len(eps), frames_per_match=a.frames, branches=9,
        bundle_sha256=sha(a.bundle/'manifest.json'), checkpoint_sha256=sha(checkpoint),
        source_sha256={p.name: sha(p) for p in (Path(__file__), Path(__file__).with_name('lockstep_replay_v4.py'))},
        fetch_seconds=fetch_seconds, layer_probes={}, replay_probes=[], gpu_samples=[gpu_snapshot()],
        heldout_payloads_opened=False, full_equality_gate_passed=False, target100fps_verified=False)
    def save():
        # This is an evolving bounded-probe receipt in our new directory only.
        a.output.write_text(json.dumps(evidence, indent=2, allow_nan=False)+'\n')
    save()
    for deterministic in (False, True):
        if deterministic:
            if os.environ.get('CUBLAS_WORKSPACE_CONFIG') not in (':4096:8', ':16:8'):
                raise ValueError('Fixed cuBLAS workspace required for retry')
            torch.use_deterministic_algorithms(True); torch.backends.cudnn.benchmark = False
        trial = {}
        for batch in a.batches:
            resource_guard()
            if batch > len(eps):
                continue
            trial[str(batch)] = dict(
                encoder=compare_chunks(base.encode, (arena, hud), encoded, batch),
                prefix=compare_chunks(lambda c, t, v: dict(mixed=prefix(base.temporal, c, t, v)),
                                      (cache, ages, valid), [dict(mixed=m) for m in mixed], batch),
                tail=compare_chunks(lambda m, b, v: tail(base.temporal, m, b, v),
                                    (mix, births, valid), event, batch))
            print(json.dumps(dict(layer_probe=True, deterministic=deterministic, batch=batch,
                                 exact={k: v['exact'] for k, v in trial[str(batch)].items()})), flush=True)
            evidence['layer_probes'][str(deterministic)] = trial; save()
    # Restore the admitted execution settings for the original-path reference.
    torch.use_deterministic_algorithms(False)
    original_records = {}; original_payloads = {}; reference_start = time.perf_counter()
    class Recorded(SharedModel):
        def temporal(self, *args):
            self.event = super().temporal(*args); return self.event
    for ep in eps[:8]:
        model = Recorded(base)
        branches = [runtime.PixelPerception(model, state['cards'], state['bodies'], spells,
                    {'default': .5}, {}, device='cuda', body_threshold=i/10) for i in range(1, 10)]
        for seq, image in enumerate(pixels[ep]):
            stamp = (metadata[ep][seq]['produced_at']-metadata[ep][0]['produced_at'])*1000
            model.begin_frame()
            for i, branch in enumerate(branches):
                value = branch.step(image, ep, stamp)
                original_records[ep, i+1, seq] = json_bytes(reference_record(
                    model, branch, state['cards'], state['bodies'], ep, seq, stamp, value))
                original_payloads[ep, i+1, seq] = json_bytes(nonclock(value))
    evidence['original_reference_seconds'] = time.perf_counter()-reference_start
    quarantine = quarantine_prefix(eps[:8], a.frames) if a.epoch == 3 else {}
    evidence['original_vs_quarantine_mismatches'] = sum(
        original_records[k] != row for k, row in quarantine.items()) if quarantine else None
    del encoded, cache, ages, valid, births, mixed, event, mix, arena, hud
    gc.collect(); torch.cuda.empty_cache(); save()
    for size in a.batches:
        if size > len(eps):
            continue
        resource_guard()
        selected = eps[:size]
        # Maximum exact whole-layer batch observed under original settings.
        choices = evidence['layer_probes']['False']
        choose = lambda stage: max([1]+[int(n) for n, r in choices.items() if r[stage]['exact'] and int(n) <= size])
        eb, pb, tb = choose('encoder'), choose('prefix'), choose('tail')
        engine = LockstepReplay(base, state['cards'], state['bodies'], spells, selected, device='cuda',
            mode=a.mode, encoder_batch=eb, prefix_batch=pb, tail_batch=tb)
        torch.cuda.synchronize(); start = time.perf_counter()
        prepared = {ep: engine.encode(pairs[ep]) for ep in selected}
        mismatches = []; payload_mismatches = []; streams = {}; reference_streams = {}
        for seq in range(a.frames):
            stamps = [(metadata[ep][seq]['produced_at']-metadata[ep][0]['produced_at'])*1000 for ep in selected]
            rows = engine.step(selected, stamps, [prepared[ep][seq] for ep in selected])
            for ep, branch, record, payload in rows:
                key = ep, branch, seq; blob = json_bytes(record)
                streams.setdefault((ep, branch), hashlib.sha256()).update(blob)
                if key in original_records:
                    reference_streams.setdefault((ep, branch), hashlib.sha256()).update(original_records[key])
                    if blob != original_records[key]:
                        mismatches.append([ep, branch, seq])
                    if json_bytes(nonclock(payload)) != original_payloads[key]:
                        payload_mismatches.append([ep, branch, seq])
        torch.cuda.synchronize(); seconds = time.perf_counter()-start
        result = dict(batch_size=size, encoder_batch=eb, prefix_batch=pb, tail_batch=tb,
            frames=size*a.frames, seconds=seconds, frames_per_second_per_gpu=size*a.frames/seconds,
            measurement='bounded replay prefix includes encoder/model/trackers/extraction/JSON; cache prefetch and disk excluded',
            full_replay_frames_per_second_per_gpu=None, record_mismatches=mismatches,
            nonclock_payload_mismatches=payload_mismatches, exact_prefix=not mismatches and not payload_mismatches,
            records_sha256={f'{ep}/body-{i}': h.hexdigest() for (ep, i), h in streams.items()},
            original_records_sha256={f'{ep}/body-{i}': h.hexdigest() for (ep, i), h in reference_streams.items()},
            peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,
            peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2)
        evidence['replay_probes'].append(result); evidence['gpu_samples'].append(gpu_snapshot()); save()
        print(json.dumps(result), flush=True)
        del engine, prepared; gc.collect(); torch.cuda.empty_cache()
    evidence['largest_exact_layer_batch_original'] = {stage: max([1]+[int(n) for n, row in evidence['layer_probes']['False'].items()
        if row[stage]['exact']]) for stage in ('encoder', 'prefix', 'tail')}
    save()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'connections', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--epoch', type=int, choices=range(1, 25), default=3)
    p.add_argument('--frames', type=int, default=4); p.add_argument('--matches', type=int, default=64)
    p.add_argument('--batches', type=int, nargs='+', default=[8, 16, 32, 64])
    p.add_argument('--mode', choices=('scalar', 'graph'), default='graph')
    a = p.parse_args(); a.local_cache = None
    if not 1 <= a.frames <= 64 or a.matches not in (8, 16, 32, 64) or any(b not in (1, 2, 4, 8, 16, 32, 64) for b in a.batches):
        raise ValueError('Invalid bounded probe size')
    probe(a)
