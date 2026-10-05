"""Compare recorded Stage 0 work and report gates without changing the oracle."""
from __future__ import annotations

import json
import re
from pathlib import Path

ES = Path(__file__).resolve().parent


def read(name):
    return json.loads((ES / 'results' / name).read_text())


def instructions(label):
    log = (ES / 'logs' / f'stage0_pure_{label}.log').read_text()
    return int(re.search(r'(\d+)\s+instructions retired', log).group(1))


def engine_trace(result):
    keys = ('seed', 'ticks', 'decisions', 'deploys', 'winner', 'final_digest', 'digests')
    return [{k: row[k] for k in keys} for row in result['matches']]


def srp_trace(result):
    keys = ('tick', 'seat', 'root_digest', 'action', 'rollout_ticks', 'script_actions', 'leaves')
    return [{k: row[k] for k in keys} for row in result['calls']]


def main():
    engine_before = read('pure_stage0_before.json')
    srp_before = read('stage0_srp_before.json')
    summary = {
        'baseline': {
            'engine_ticks_per_core_s': engine_before['step_only_ticks_per_s_cpu'],
            'engine_workload_instructions': instructions('before'),
            'srp_core_s_per_call': srp_before['cpu_per_call_s'],
            'srp_calls': len(srp_before['calls']),
            'snapshot_sha256': srp_before['snapshot_sha256'],
        },
        'variants': {},
    }
    for label in ('p5', 'cython'):
        engine = read(f'pure_stage0_{label}.json')
        srp = read(f'stage0_srp_{label}.json')
        engine_equal = engine_trace(engine) == engine_trace(engine_before)
        srp_equal = (srp['snapshot_sha256'] == srp_before['snapshot_sha256']
                     and srp_trace(srp) == srp_trace(srp_before))
        instruction_gain = instructions('before') / instructions(label)
        srp_gain = srp_before['cpu_per_call_s'] / srp['cpu_per_call_s']
        identity_pass = {}
        for suite in ('p16', 'c56'):
            log = (ES / 'logs' / f'stage0_{suite}_{label}.log').read_text()
            identity_pass[suite] = '"mismatches": []' in log
        test_log = (ES / 'logs' / f'stage0_tests_{label}.log').read_text()
        tests_pass = bool(re.search(r'\d+ passed', test_log)) and not re.search(r'\d+ (failed|error)', test_log)
        summary['variants'][label] = {
            'engine_ticks_per_core_s': engine['step_only_ticks_per_s_cpu'],
            'engine_tick_speedup': engine['step_only_ticks_per_s_cpu'] / engine_before['step_only_ticks_per_s_cpu'],
            'engine_workload_instructions': instructions(label),
            'instruction_reduction_factor': instruction_gain,
            'srp_core_s_per_call': srp['cpu_per_call_s'],
            'srp_speedup': srp_gain,
            'skipped_observations': srp['skipped_observations'],
            'engine_traces_equal': engine_equal,
            'srp_full_traces_equal': srp_equal,
            'identity_pass': identity_pass,
            'regressions_pass': tests_pass,
            'stage0_gate_pass': (engine_equal and srp_equal and all(identity_pass.values())
                                 and tests_pass and instruction_gain >= 1.4 and srp_gain >= 1.5),
        }
    repeated_labels = ('before', 'before_r2', 'before_r3', 'cython', 'cython_r2', 'cython_r3')
    if all((ES / 'results' / f'stage0_srp_{label}.json').exists() for label in repeated_labels):
        repeated = {label: read(f'stage0_srp_{label}.json') for label in repeated_labels}
        traces_equal = all(
            result['snapshot_sha256'] == srp_before['snapshot_sha256']
            and srp_trace(result) == srp_trace(srp_before)
            for result in repeated.values()
        )
        times = {label: result['cpu_per_call_s'] for label, result in repeated.items()}
        before_mean = sum(times[label] for label in repeated_labels[:3]) / 3
        after_mean = sum(times[label] for label in repeated_labels[3:]) / 3
        summary['srp_repeats'] = {
            'core_s_per_call': times,
            'reference_mean': before_mean,
            'cython_fast_mean': after_mean,
            'speedup': before_mean / after_mean,
            'all_full_traces_equal': traces_equal,
            'calls_per_variant': sum(len(repeated[label]['calls']) for label in repeated_labels[:3]),
        }
        variant = summary['variants']['cython']
        variant['stage0_gate_pass'] = (
            variant['engine_traces_equal'] and variant['srp_full_traces_equal'] and traces_equal
            and all(variant['identity_pass'].values()) and variant['regressions_pass']
            and variant['instruction_reduction_factor'] >= 1.4 and before_mean / after_mean >= 1.5
        )
    out = ES / 'results' / 'stage0_summary.json'
    out.write_text(json.dumps(summary, indent=2) + '\n')
    print(out.read_text())


if __name__ == '__main__':
    main()
