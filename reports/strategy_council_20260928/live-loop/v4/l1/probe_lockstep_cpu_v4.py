"""08-only CPU emulation of exact-shape lockstep; not CUDA/full-gate evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time

import torch
from clasher.vision import l1_v4 as runtime
from shared_model_v4 import SharedModel
from decoder_records_v4 import extract_event_records
from pixel_cache import PixelCache
from lockstep_replay_v4 import LockstepReplay, frame_times, nonclock, json_bytes, sha


def first_difference(a, b, path=''):
    if type(a) is not type(b):
        return dict(path=path, original_type=type(a).__name__, candidate_type=type(b).__name__)
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return dict(path=path, original_keys=list(a), candidate_keys=list(b))
        for k in a:
            if a[k] != b[k]:
                return first_difference(a[k], b[k], path+'/'+k)
    elif isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return dict(path=path, original_length=len(a), candidate_length=len(b))
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return first_difference(x, y, path+'/'+str(i))
    elif a != b:
        return dict(path=path, original=a, candidate=b)
    return None


@torch.inference_mode()
def probe(a):
    import cv2
    from clasher.data import CardDataLoader
    if socket.gethostname().split('.')[0] != '127x08' or os.getpriority(os.PRIO_PROCESS, 0) < 10:
        raise ValueError('08CPU nice>=10 only')
    torch.set_num_threads(a.threads); cv2.setNumThreads(1)
    if a.output.exists():
        raise ValueError('Fresh CPU receipt required')
    source_pins = {n: sha(Path(__file__).with_name(n)) for n in ('probe_lockstep_cpu_v4.py', 'lockstep_replay_v4.py')}
    manifest = json.loads((a.bundle/'manifest.json').read_text())
    stage = json.loads((a.bundle/'stage-complete.json').read_text())
    if sha(a.bundle/'manifest.json') != stage['manifest_sha256']:
        raise ValueError('Pinned bundle changed')
    episodes = sorted(manifest['validation_episodes'])[:a.matches]
    receipts = []; times = {}
    for ep in episodes:
        folder = a.bundle/'matches'/ep
        receipt = json.loads((folder/'receipt.json').read_text())
        if receipt['split'] != 'validation' or receipt['episode'] != ep:
            raise ValueError('Validation only')
        if sha(folder/'frames.jsonl') != receipt['files']['frames.jsonl']:
            raise ValueError('Frame metadata pin differs')
        receipts.append(dict(receipt, receipt_sha256=sha(folder/'receipt.json')))
        times[ep] = frame_times([json.loads(s) for s in (folder/'frames.jsonl').read_text().splitlines()])[:a.frames]
        if sha(a.cache/ep/'index.json') != sha(a.bundle/'fit/model/cache-indices'/ep/'index.json'):
            raise ValueError('Pinned cache index differs')
    cache = PixelCache(a.cache, receipts)  # Full SHA verification, validation only.
    pixels = {ep: cache.get(ep, list(range(a.frames)), raw=True) for ep in episodes}
    os.environ['CLASHER_ROOT'] = str(a.bundle/'runtime')
    loader = CardDataLoader(); results = []
    for epoch in a.epochs:
        checkpoint = a.bundle/'fit/model'/f'epoch-{epoch}.pt'
        if sha(checkpoint) != manifest['files_sha256'][str(checkpoint.relative_to(a.bundle))]:
            raise ValueError('Checkpoint pin differs')
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        spells = [c for c in state['cards'] if str(loader.get_card(c).card_type).lower() == 'spell']
        base = runtime.PerceptionV4(len(state['cards']), len(state['bodies'])); base.load_state_dict(state['model']); base.eval()
        expected = {}; expected_payloads = {}; tail_shapes = []
        hook = base.temporal.birth.register_forward_pre_hook(lambda module, args: tail_shapes.append(tuple(args[0].shape)))
        class Recorded(SharedModel):
            def temporal(self, *args):
                self.event = super().temporal(*args); return self.event
        start = time.perf_counter()
        for ep in episodes:
            model = Recorded(base)
            branches = [runtime.PixelPerception(model, state['cards'], state['bodies'], spells, {'default': .5}, {}, body_threshold=i/10)
                        for i in range(1, 10)]
            for seq, image in enumerate(pixels[ep]):
                model.begin_frame(); stamp = times[ep][seq]
                for branch, r in enumerate(branches, 1):
                    value = r.step(image, ep, stamp)
                    record = dict(schema='clasher.v4.decoder-frame.v1', source_seq=seq, episode_id=ep, timestamp_ms=stamp,
                        bodies=runtime.decode_bodies(model.encoded, state['bodies'], .1),
                        event_peaks=extract_event_records(model.event, state['cards'], stamp),
                        causal_own_hud_cards=[c for c, _ in r.own_plays],
                        hud={k: value[k] for k in ('own_hand', 'next_card', 'own_elixir', 'hud_card_probabilities', 'clock_seconds', 'phase')})
                    expected[ep, branch, seq] = record; expected_payloads[ep, branch, seq] = nonclock(value)
                    json_bytes(record); json_bytes(nonclock(value))
        original_seconds = time.perf_counter()-start
        original_tail_shapes = list(tail_shapes); tail_shapes.clear()
        engine = LockstepReplay(base, state['cards'], state['bodies'], spells, episodes, mode='scalar')
        start = time.perf_counter()
        prepared = {ep: engine.encode([runtime.prepare_pixels(im) for im in pixels[ep]]) for ep in episodes}
        record_mismatches = []; payload_mismatches = []; first = None
        hashes = {}; original_hashes = {}
        for seq in range(a.frames):
            rows = engine.step(episodes, [times[ep][seq] for ep in episodes], [prepared[ep][seq] for ep in episodes])
            for ep, branch, record, payload in rows:
                key = ep, branch, seq
                blob = json_bytes(record); expected_blob = json_bytes(expected[key])
                hashes.setdefault((ep, branch), hashlib.sha256()).update(blob)
                original_hashes.setdefault((ep, branch), hashlib.sha256()).update(expected_blob)
                if blob != expected_blob:
                    record_mismatches.append(list(key))
                    first = first or first_difference(expected[key], record)
                if json_bytes(nonclock(payload)) != json_bytes(expected_payloads[key]):
                    payload_mismatches.append(list(key))
                    first = first or first_difference(expected_payloads[key], nonclock(payload))
        candidate_seconds = time.perf_counter()-start; hook.remove()
        results.append(dict(epoch=epoch, frames=len(episodes)*a.frames, matches=len(episodes), branches=9,
            checkpoint_sha256=sha(checkpoint), original_seconds=original_seconds, candidate_seconds=candidate_seconds,
            cpu_frames_per_second=len(episodes)*a.frames/candidate_seconds, cpu_speedup=original_seconds/candidate_seconds,
            record_mismatches=record_mismatches, nonclock_payload_mismatches=payload_mismatches, first_difference=first,
            exact=not record_mismatches and not payload_mismatches,
            original_tail_calls=len(original_tail_shapes), candidate_tail_calls=len(tail_shapes),
            all_tail_shapes_original=all(s == (1, 2, 64, 36) for s in original_tail_shapes+tail_shapes),
            candidate_record_sha256={f'{ep}/body-{i}': h.hexdigest() for (ep, i), h in hashes.items()},
            original_record_sha256={f'{ep}/body-{i}': h.hexdigest() for (ep, i), h in original_hashes.items()}))
        output = dict(schema='clasher.v4.lockstep-cpu-real-prefix.v1', formal_admitted=False,
            full_required_scope_equal=False, gpu_throughput_measured=False, threads=a.threads, results=results,
            source_sha256=source_pins,
            measurement='CPU prefix includes pixel preparation, encoder, causal runtime, record extraction and JSON; cache fetch/disk excluded',
            heldout_payloads_opened=False)
        if any(sha(Path(__file__).with_name(n)) != digest for n, digest in source_pins.items()):
            raise ValueError('Probe sources changed during CPU experiment')
        a.output.write_text(json.dumps(output, indent=2)+'\n')
        print(json.dumps({k: v for k, v in results[-1].items() if not k.endswith('_sha256')}), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bundle', 'cache', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--epochs', type=int, nargs='+', default=[1, 3, 20])
    p.add_argument('--matches', type=int, default=8); p.add_argument('--frames', type=int, default=2)
    p.add_argument('--threads', type=int, choices=range(1, 9), default=4)
    a = p.parse_args()
    if not 1 <= a.frames <= 32 or not 1 <= a.matches <= 8 or any(e not in range(1, 25) for e in a.epochs):
        raise ValueError('Bounded CPU prefix scope required')
    probe(a)
