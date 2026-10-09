"""Dependency-free receipt validation; Linux tests never import Torch/native code."""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def json_numeric(value):
    # Public tracker fields can carry NumPy scalars. Preserve their numeric/
    # boolean types; never turn unrecognized scientific values into strings.
    if type(value).__module__.split('.')[0] == 'numpy' and hasattr(value, 'tolist'):
        return value.tolist()
    raise TypeError('Unsupported receipt value: ' + type(value).__name__)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False, default=json_numeric)


def write_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False, default=json_numeric) + '\n')


def quantiles(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'p50': None, 'p95': None, 'p99': None, 'max': None}
    if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError('Latency must be finite, numeric and nonnegative')
    def percentile(q):
        i = (len(values) - 1) * q
        lo, hi = math.floor(i), math.ceil(i)
        return values[lo] + (values[hi] - values[lo]) * (i - lo)
    return dict(n=len(values), p50=percentile(.5), p95=percentile(.95),
                p99=percentile(.99), max=values[-1])


def verify_pins(root, pins):
    root = Path(root).resolve()
    for name, expected in pins.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha(path) != expected:
            raise ValueError('Source/config SHA mismatch: ' + name)


def without_availability(value):
    """Only service-dependent availability is excluded; public/frame time stays."""
    if isinstance(value, dict):
        return {k: without_availability(v) for k, v in value.items()
                if k != 'available_timestamp_ms'}
    if isinstance(value, (list, tuple)):
        return [without_availability(v) for v in value]
    return value


def comparison_key(row):
    return row['packet_id'], row['mode'], row['wait_screen8'], row['threads']


def complete_reduction(candidate_ids, root_scores):
    """Independent check of the four-root reducer, including stable epsilon ties."""
    if len(root_scores) != 4 or any(len(r) != len(candidate_ids) for r in root_scores):
        raise ValueError('Exactly four complete-shaped root score lists required')
    complete = [(sum(values)/4, i) for i, values in enumerate(zip(*root_scores))
                if all(v is not None for v in values)]
    if any(not math.isfinite(v) for v, _ in complete):
        raise ValueError('Nonfinite candidate score')
    best = None
    for value, i in complete:
        if best is None or value > best[0] + 1e-9:
            best = value, i
    return (candidate_ids[best[1]] if best else 2304), [v for v, _ in complete]


def summarize_decisions(rows, minimum=1000):
    cells = {}
    paired = {}
    for row in rows:
        key = comparison_key(row)
        if key in paired:
            raise ValueError('Duplicate paired measurement: ' + str(key))
        paired[key] = row
        if row['mode'] == 'deadline':
            cells.setdefault((row['wait_screen8'], row['threads']), []).append(row)
    result = {}
    for w in (False, True):
        for threads in (1, 4):
            samples = cells.get((w, threads), [])
            genuine = [r for r in samples if r['searched'] and r['nonterminal']]
            metrics = quantiles([r['decision_ms'] for r in genuine])
            invalid = sum(not r['admission_valid'] for r in genuine)
            result[f'w{int(w)}-t{threads}'] = dict(
                full_decision_ms=metrics,
                frame_to_mock_submission_ms=quantiles([r['frame_to_mock_ms'] for r in genuine]),
                samples=len(samples), real_nonterminal_searches=len(genuine),
                overruns=sum(r['decision_ms'] > 200 for r in genuine),
                no_complete_candidate=sum(r['completed'] == 0 for r in genuine),
                partial_searches=sum(r['completed'] < r['candidates'] for r in genuine),
                candidate_completion_fraction=(sum(r['completed'] for r in genuine) /
                    sum(r['candidates'] for r in genuine) if genuine else None),
                invalid_admissions=invalid,
                decision_gate=('PASS' if len(genuine) >= minimum and invalid == 0
                    and metrics['p95'] <= 200 else 'FAIL'))
    exact = []
    cohorts = {}
    for w in (False, True):
        deadline_sets = [{r['packet_id'] for r in cells.get((w, t), []) if r['searched'] and r['nonterminal']}
                         for t in (1, 4)]
        cohorts[f'w{int(w)}'] = dict(paired=len(deadline_sets[0] & deadline_sets[1]),
            identical=deadline_sets[0] == deadline_sets[1])
        ids = {key[0] for key in paired if key[1] == 'exact' and key[2] == w}
        for packet_id in sorted(ids):
            a = paired.get((packet_id, 'exact', w, 1))
            b = paired.get((packet_id, 'exact', w, 4))
            equal = (a is not None and b is not None and a['searched'] and b['searched']
                and a['exact_full_budget'] and b['exact_full_budget']
                and a['admission_valid'] and b['admission_valid']
                and ((a['completed'] > 0 and b['completed'] > 0) if w else
                     (a['completed'] == a['candidates'] and b['completed'] == b['candidates']))
                and a['candidate_ids'] == b['candidate_ids'] and a['scores'] == b['scores']
                and a['root_scores'] == b['root_scores']
                and a['action'] == b['action'])
            exact.append(dict(packet_id=packet_id, wait_screen8=w, equal=bool(equal)))
    all_sets = [{r['packet_id'] for r in cells.get((w, t), []) if r['searched'] and r['nonterminal']}
                for w in (False, True) for t in (1, 4)]
    matrix_paired = len(set.intersection(*all_sets))
    matrix_equal = all(s == all_sets[0] for s in all_sets)
    return dict(cells=result, thread_pairs=cohorts, matrix_paired=matrix_paired,
        matrix_identical=matrix_equal, exact_pairs=exact,
        exactness_gate='PASS' if len(exact) >= 64 and all(r['equal'] for r in exact) else 'FAIL',
        package_decision_gate='PASS' if matrix_equal and matrix_paired >= minimum
            and all(v['decision_gate'] == 'PASS' for v in result.values())
            and len(exact) >= 64 and all(r['equal'] for r in exact) else 'FAIL')


def perception_gate(rows, minimum=1000, budget=40):
    result = {}
    for arm in ('scalar', 'vectorized'):
        selected = [r for r in rows if r['arm'] == arm and not r['cold']]
        measured = quantiles([r['perception_ms'] for r in selected])
        result[arm] = dict(full_perception_ms=measured,
            budget_status='PASS' if len(selected) >= minimum and measured['p95'] <= budget else 'FAIL',
            status_scope='engineering budget; descriptive under L2-V4-PREREG E1',
            cold_ms=quantiles([r['perception_ms'] for r in rows if r['arm'] == arm and r['cold']]),
            integrated_tower_crown_result_ms=quantiles([r['tower_ms'] for r in selected]))
    return result
