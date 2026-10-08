"""Audit split-runtime replay receipts and paired perception-budget projections."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
from clasher.live.runtime import quantiles


def aggregate(root):
    samples, counts, matches, errors = defaultdict(list), Counter(), [], []
    duration = 0.
    provenance = []
    for path in sorted(root.glob('*/metrics.json')):
        metrics = json.loads(path.read_text())
        config = json.loads(path.with_name('config.json').read_text())
        assert config['source']['split'] == 'train' and config['actuator']['kind'] == 'mock'
        prov = json.loads(path.with_name('provenance.json').read_text())
        provenance.append(prov)
        with gzip.open(path.with_name('latency.jsonl.gz'), 'rt') as stream:
            rows = [json.loads(line) for line in stream]
        frame_costs = defaultdict(float)
        for row in rows:
            if row['metric'] in ('backbone_hud', 'temporal_fusion'):
                frame_costs[row['sequence']] += row['ms']
        capture = [r for r in rows if r['metric'] == 'captured']
        duration += capture[-1]['produced_at']-capture[0]['produced_at']
        active, taps = set(), set()
        for row in rows:
            metric = row['metric']
            counts[metric] += 1
            if 'ms' in row:
                samples[metric].append(row['ms'])
            if metric == 'search':
                counts['search_overruns'] += bool(row['deadline_overrun'])
                if row.get('diagnostic', {}).get('candidates', 0) >= 2:
                    samples['search_active'].append(row['ms'])
            if metric == 'actuator_state':
                command = row['command_id']
                if row['pending']:
                    if active and command not in active:
                        errors.append([path.parent.name, 'overlapping reservation', command])
                    active.add(command)
                else:
                    active.discard(command)
            if metric == 'taps':
                key = (row['command_id'], row['attempt'])
                if key in taps or row['command_id'] not in active:
                    errors.append([path.parent.name, 'duplicate/unreserved tap', key])
                taps.add(key)
            if metric == 'frame_to_tap':
                actual = frame_costs[row['frame_sequence']]
                assert actual > 0
                # Paired substitution; retain all observed queues, search, HUD
                # refresh and mock submission. No sum-of-quantiles estimate.
                for budget in (20, 35):
                    samples[f'projected_perception_{budget}ms'].append(row['ms']-actual+budget)
        if metrics['failures'] or metrics['log_drops'] or active:
            errors.append([path.parent.name, metrics['failures'], metrics['log_drops'], sorted(active)])
        perceived = metrics['counts']['perceived']
        if metrics['captured'] != perceived+metrics['dropped_frames']:
            errors.append([path.parent.name, 'capture drop accounting'])
        matches.append(dict(seed=path.parent.name, captured=metrics['captured'], perceived=perceived,
                            processed=metrics['processed'], first_taps=metrics['counts'].get('frame_to_tap', 0),
                            capture_dropped=metrics['dropped_frames'], belief_skipped=perceived-metrics['processed'],
                            trace_sha256=hashlib.sha256(path.with_name('latency.jsonl.gz').read_bytes()).hexdigest()))
    assert matches
    # Every reported final run must use exactly the same runtime implementation.
    versions = [{Path(k).name: v for k, v in p['hashes'].items() if '/src/clasher/live/' in k} for p in provenance]
    assert all(v == versions[0] for v in versions), 'Mixed runtime versions: do not pool these runs'
    timing = {k: quantiles(v) for k, v in samples.items()}
    end = timing['frame_to_tap']
    n = len(matches)
    return dict(schema='clasher.live-v4.latency-optimization.v1', host=provenance[0]['host'],
                matches=matches, source_sha256=versions[0], timing_ms=timing, counts=counts,
                processed_fps=(counts['processed']-n)/duration,
                perception_fps=(counts['perceived']-n)/duration,
                processed_fraction=counts['processed']/counts['captured'],
                perception_fraction=counts['perceived']/counts['captured'],
                audit_errors=errors, heldout_opened=False, actuator='mock', device='cpu',
                sample_gate=n >= 6 and end['count'] >= 200,
                median_budget_pass=end['p50'] <= 200, tail_budget_pass=end['p99'] <= 400,
                belief_p99_pass=timing['belief']['p99'] <= 10,
                production_qualified=False,
                projection='Per first tap: measured latency minus source-frame body/HUD+temporal duration plus 20ms (DESIGN p50 stages) or 35ms (DESIGN p95 stages). Observed queueing and other stage costs retained; these are scenarios, not Mac measurements.')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.write_text(json.dumps(aggregate(a.root), indent=2)+'\n')
