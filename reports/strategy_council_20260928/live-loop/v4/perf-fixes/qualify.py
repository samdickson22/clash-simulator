"""CPU-only recorded-input causality, byte equality, score parity and timings.

Run on 127x08 through fleet_run.sh, CUDA_VISIBLE_DEVICES=, one Torch/Rayon thread.
No real battle, hidden state, media, deck truth, eval or heldout reads.
"""
import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from types import FunctionType, SimpleNamespace

import numpy as np
import torch
import clasher_core
from clasher.live.decision import RustPlanner, DecisionInfo
from clasher.live.loading import ROOT, module
from clasher.live.perf_resources import cached_resources
from clasher.live.public_root import public_resources
from clasher.live.runtime import quantiles
from clasher.live.tower_model import tower_packet_builder
from clasher.rl.live_inference_contract import parse_public_vision_frame, LIVE_VISION_SCHEMA_VERSION


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public(row):
    value = copy.deepcopy(row['public'])
    outer = {key: value.pop(key) for key in ('episode_id', 'frame_id', 'timestamp_ms')}
    return parse_public_vision_frame(dict(outer, schema_version=LIVE_VISION_SCHEMA_VERSION, public=value))


def info_for(planner, packets, row):
    packet, diagnostic = packets.build(public(row), row['tick'])
    return DecisionInfo(row['tick'], 1, planner.model_hypothesis(packet),
                        {key: row['own'][key] for key in ('hand', 'cycle', 'refill', 'elixir')}), diagnostic


def main(a):
    torch.set_num_threads(1)
    if os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise ValueError('CPU-only qualification requires CUDA_VISIBLE_DEVICES=')
    if a.output.exists():
        raise ValueError('Fresh receipt required')
    data = json.loads(gzip.decompress(a.inputs.read_bytes()))
    assert data['split'] == 'train' and not data['unmatched']
    planner = RustPlanner({'seed': 6108})
    resources = planner.resources
    result = dict(schema='clasher.live-perf.qualification.v1', host=platform.node(),
                  cpu=platform.machine(), python=sys.version, torch=torch.__version__,
                  native_path=clasher_core.__file__, native_sha256=sha(clasher_core.__file__),
                  input_sha256=sha(a.inputs), split='train', heldout_opened=False,
                  flags_default_off=True, source_hashes=data['source_hashes'])
    packet_class = type(planner.packets)
    old_packets, new_packets = packet_class(resources.builder), tower_packet_builder(packet_class)(resources.builder)
    causal = []
    try:
        for row in data['inputs']:
            entry = dict(match=row['match'], sequence=row['sequence'],
                         recorded_flat_minus_two=all(v == -2. for v in row['recorded']['scores']))
            for label, packets in (('original', old_packets), ('tower_model', new_packets)):
                info, diagnostic = info_for(planner, packets, row)
                root = resources.root(info, row['roots'][0], np.random.default_rng(6108))
                before = json.loads(root.snapshot())
                kings = [e['owner'] for e in before['entities'] if e['king']]
                root.step(1)
                after = json.loads(root.snapshot())
                entry[label] = dict(kings=kings, game_over=after['game_over'], winner=after['winner'],
                                    score=resources.native.evaluate(root, 1, planner.cores[0].config.elixir_weight))
                if label == 'tower_model':
                    entry['tower_diagnostic'] = diagnostic
            causal.append(entry)
        result['causality'] = causal
        result['causal_summary'] = dict(inputs=len(causal),
            recorded_flat_minus_two=sum(r['recorded_flat_minus_two'] for r in causal),
            original_one_tick_terminal=sum(r['original']['game_over'] for r in causal),
            repaired_one_tick_terminal=sum(r['tower_model']['game_over'] for r in causal),
            flat_with_missing_own_king=sum(r['recorded_flat_minus_two'] and 1 not in r['original']['kings'] for r in causal))
        print('CAUSALITY '+json.dumps(result['causal_summary']), flush=True)

        # Capture the sealed constructor's input string without changing its
        # global module or doing a duplicate resource warmup.
        source = type(resources)
        namespace = dict(source.root.__globals__, clasher_core=SimpleNamespace(BattleState=lambda value: value))
        captured_root = FunctionType(source.root.__code__, namespace, source.root.__name__, source.root.__defaults__)
        class Captured(source):
            root = captured_root
            def __init__(self):
                self.__dict__.update(resources.__dict__)
        baseline, cached = Captured(), cached_resources(Captured)()
        assert baseline.config is cached.config
        timing = {'original': [], 'cached': []}
        digests = {key: hashlib.sha256() for key in timing}
        before_rng, after_rng = np.random.default_rng(6209), np.random.default_rng(6209)
        payloads = 0
        for i in range(max(1000, a.roots)):
            row = data['inputs'][i % len(data['inputs'])]
            info, _ = info_for(planner, new_packets, row)
            hypothesis = row['roots'][i % 4]
            values = {}
            # Alternate order to reduce drift bias.
            for key in (('original', 'cached') if i % 2 else ('cached', 'original')):
                obj, rng = (baseline, before_rng) if key == 'original' else (cached, after_rng)
                started = time.perf_counter()
                values[key] = obj.root(info, hypothesis, rng)
                timing[key].append((time.perf_counter()-started)*1000)
                digests[key].update(values[key].encode())
            assert values['original'].encode() == values['cached'].encode(), i
            payloads += 1
            if i < 32:
                assert clasher_core.BattleState(values['original']).digest() == clasher_core.BattleState(values['cached']).digest()
        assert before_rng.bit_generator.state == after_rng.bit_generator.state
        result['payload_exactness'] = dict(roots=payloads, mismatches=0, native_digest_pairs=32,
            rng_equal=True, config_bytes=len(cached.config_json.encode()),
            sha256={key: digest.hexdigest() for key, digest in digests.items()},
            serialize_ms={key: quantiles(value) for key, value in timing.items()})
        print('PAYLOADS '+json.dumps(result['payload_exactness']), flush=True)

        # Real parsed roots and real full-list S6 candidate scores on repaired
        # recorded inputs; compare both runtime variants with direct frozen S6.
        class Borrowed(source):
            def __init__(self):
                self.__dict__.update(resources.__dict__)
        repaired_resources = public_resources(Borrowed)()
        fast_resources = public_resources(cached_resources(Borrowed))()
        score_receipts = []
        timings = {'original': [], 'optimized': []}
        selected = data['inputs']
        # Evenly sample the input sequence, deterministic train-only selection.
        selected = selected[::max(1, len(selected)//a.decisions)][:a.decisions]
        for row in selected:
            planner.cores[0].rng = np.random.default_rng(6108)
            info, _ = info_for(planner, tower_packet_builder(packet_class)(resources.builder), row)
            candidates, _ = planner.cores[0].candidates(info.packet)
            if len(candidates) < 2:
                continue
            all_values = {}
            print('SCORING '+json.dumps(dict(match=row['match'], sequence=row['sequence'])), flush=True)
            for label, obj in (('original', repaired_resources), ('optimized', fast_resources)):
                rng = np.random.default_rng(6108)
                planner.hoist_opponent_moves = label == 'optimized'
                planner.delay_ticks = row['recorded_delay_ticks']
                for core in planner.cores:
                    core.command_delay = planner.delay_ticks
                started = time.perf_counter()
                roots = [obj.root(info, hypothesis, rng) for hypothesis in row['roots']]
                values = [planner.score(core, root, info, candidates, time.monotonic()+120.)
                          for core, root in zip(planner.cores, roots)]
                timings[label].append((time.perf_counter()-started)*1000)
                all_values[label] = values
            assert all_values['original'] == all_values['optimized'], row['sequence']
            # Independent direct S6 equality on identical physical roots.
            core = planner.cores[0]
            core.info, core.costs = info, resources.costs
            same_root = repaired_resources.root(info, row['roots'][0], np.random.default_rng(6108))
            digest = same_root.digest()
            core.score_candidates(same_root, 1, candidates)
            assert same_root.digest() == digest
            assert core.last['scores'] == all_values['optimized'][0]
            score_receipts.append(dict(match=row['match'], sequence=row['sequence'], candidates=len(candidates),
                delay_ticks=planner.delay_ticks, original=all_values['original'], optimized=all_values['optimized']))
        result['score_exactness'] = dict(decisions=len(score_receipts),
            candidate_root_scores=sum(r['candidates']*4 for r in score_receipts),
            mismatches=0, direct_s6_equal=True, receipts=score_receipts)
        result['decision_ms'] = {key: quantiles(value) for key, value in timings.items()}
        result['decision_ms']['paired_savings'] = quantiles([x-y for x, y in zip(timings['original'], timings['optimized'])])
        result['decision_timing_scope'] = 'serial full-budget four-root nonterminal CPU; no deadline, no Mac claim'
        result['code_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in sorted((ROOT/'src/clasher/live').glob('*.py'))}
        a.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
        print('DECISIONS '+json.dumps(result['decision_ms']), flush=True)
    finally:
        planner.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, default=Path(__file__).with_name('mac-search-inputs.json.gz'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--roots', type=int, default=1000)
    p.add_argument('--decisions', type=int, default=16)
    main(p.parse_args())
