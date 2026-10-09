"""Prepared only: train MPS decoder parity followed by a guarded replay suite.

Run later with a final joint seal and the owner's trusted authenticator.
Never launches a renderer or sends real taps. Uses new result directories only.
"""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from clasher.live.capture import admit_replay, replay_frames, sha256
from clasher.live.loading import ROOT, COUNCIL, V4, module
from clasher.live.perception import V4Perception
from clasher.live.runtime import quantiles
from clasher.live.selection import load_authenticated_selection


def comparable(observation):
    return dict(public=asdict(observation.public), phase=observation.phase,
                events=[{k: v for k, v in e.items() if k != 'available_timestamp_ms'}
                        for e in observation.events])


def record_model_outputs(sensor):
    model = sensor.sensor.model
    encode, temporal = model.encode, model.temporal.forward
    def encoded(*args, **kwargs):
        value = encode(*args, **kwargs)
        sensor.encoded_output = value
        return value
    def fused(*args, **kwargs):
        value = temporal(*args, **kwargs)
        sensor.event_output = value
        return value
    model.encode, model.temporal.forward = encoded, fused


def main(a):
    if sys.platform != 'darwin':
        raise ValueError('Prepared Mac remeasurement only; do not substitute CPU qualification for MPS')
    import torch
    torch.set_num_threads(1)
    selection = load_authenticated_selection(a.selection, a.selection_authenticator)
    a.output.mkdir(parents=True, exist_ok=False)
    split = a.data/'registration/split.json'
    members = sorted((r for r in json.loads(split.read_text())['matches'] if r['split'] == 'train'),
                     key=lambda r: r['seed'])
    paths = []
    for member in members:
        name = f"v4-phase-a-{member['seed']}"
        path = a.data/'matches'/name
        if not path.exists():
            path = a.matches/name
        if (path/'receipt.json').exists():
            paths.append((member['seed'], path))
    if len(paths) < 2:
        raise ValueError('Two train recordings required for MPS exactness')
    config = dict(checkpoint=str(a.checkpoint), authenticated_selection=selection, device='mps',
                  decoder_diagnostic=True)
    original = V4Perception(config)
    optimized = V4Perception(dict(config, vectorized_decoder=True))
    record_model_outputs(original)
    record_model_outputs(optimized)
    from clasher.vision.l1_v4 import decode_bodies
    records = module('clasher_mac_perf_decoder_records', V4/'l1/decoder_records_v4.py')
    samples = {'scalar': [], 'vectorized': []}
    digests = {key: hashlib.sha256() for key in samples}
    frames = 0
    for seed, path in paths[:2]:
        source = admit_replay(path, split)
        for frame in replay_frames(source, threading.Event(), lambda *args, **kw: None, a.parity_frames):
            rows = {}
            for label, sensor in (('scalar', original), ('vectorized', optimized)):
                torch.mps.synchronize()
                start = time.perf_counter()
                value = sensor.step(frame)
                torch.mps.synchronize()
                samples[label].append((time.perf_counter()-start)*1000)
                # Time only the installed runtime. Compare complete pre-fusion
                # decoder records too; empty event outputs cannot mask a drift.
                if label == 'scalar':
                    bodies = decode_bodies(sensor.encoded_output, sensor.sensor.bodies, .1)
                    events = records.extract_event_records(sensor.event_output, sensor.sensor.cards, frame.timestamp_ms)
                else:
                    bodies = sensor.decoder_adapter.bodies(sensor.encoded_output, sensor.sensor.bodies, .1)
                    events = sensor.decoder_adapter.events(sensor.event_output, sensor.sensor.cards, frame.timestamp_ms)
                row = dict(comparable(value), decoder_bodies=bodies, decoder_events=events)
                rows[label] = json.dumps(row, sort_keys=True, allow_nan=False).encode()
                digests[label].update(rows[label])
            if rows['scalar'] != rows['vectorized']:
                raise ValueError(f'MPS non-clock output mismatch: {seed}/{frame.sequence}')
            frames += 1
    parity = dict(scope='mock-train-MPS-diagnostic', formal_admitted=False,
                  frames=frames, train_matches=2, nonclock_mismatches=0,
                  sha256={key: value.hexdigest() for key, value in digests.items()},
                  perception_ms={key: quantiles(value[2:]) for key, value in samples.items()},
                  checkpoint_sha256=sha256(a.checkpoint), selection_provenance=selection.provenance(),
                  selected_body_threshold=original.sensor.body_threshold, heldout_opened=False)
    (a.output/'mps-decoder-parity.json').write_text(json.dumps(parity, indent=2)+'\n')
    del original, optimized
    torch.mps.empty_cache()
    env = dict(os.environ, PYTHONPATH=f'{ROOT}/src:{ROOT}/engine-rs:{a.data}/python-deps',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', VECLIB_MAXIMUM_THREADS='1')
    taps, receipts = 0, []
    for seed, match in paths[:a.maximum_matches]:
        command = [sys.executable, '-B', '-m', 'clasher.live', '--replay', str(match), '--split', str(split),
            '--prior', str(COUNCIL/'search-noise-s4/runtime/support/human_deck_catalog.json'),
            '--perception', 'v4', '--checkpoint', str(a.checkpoint), '--selection', str(a.selection),
            '--selection-authenticator', a.selection_authenticator, '--decoder-diagnostic',
            '--device', 'mps', '--mock-input', '--public-tower-model', '--perf-scorer',
            '--vectorized-decoder', '--blocking-queues', '--output', str(a.output/str(seed))]
        with (a.output/f'{seed}.log').open('x') as stream:
            subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT, check=True)
        metrics = json.loads((a.output/str(seed)/'metrics.json').read_text())
        assert not metrics['failures'] and not metrics['log_drops']
        taps += metrics['counts'].get('frame_to_tap', 0)
        receipts.append(dict(seed=seed, metrics=metrics))
        (a.output/'suite.json').write_text(json.dumps(dict(matches=receipts, first_taps=taps), indent=2)+'\n')
        if len(receipts) >= 6 and taps >= 200:
            break
    if len(receipts) < 6 or taps < 200:
        raise ValueError('Remeasurement incomplete: require >=6 matches and >=200 first mock taps')
    # Do not change the backend calibration automatically; coordinator pins a
    # fresh total-delay value only after the corrected nonterminal smoke.


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for key in ('data', 'matches', 'checkpoint', 'selection', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--selection-authenticator', required=True)
    p.add_argument('--parity-frames', type=int, default=200)
    p.add_argument('--maximum-matches', type=int, default=20)
    main(p.parse_args())
