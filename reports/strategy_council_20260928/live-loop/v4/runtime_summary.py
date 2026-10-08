"""Aggregate completed train replay receipts without opening labels or media."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
from clasher.live.runtime import BUDGETS, quantiles


def aggregate(root):
    samples = defaultdict(list)
    counts = Counter()
    matches = []
    duplicates = []
    tap_keys = set()
    duration = 0.
    for path in sorted(Path(root).glob('*/metrics.json')):
        result = json.loads(path.read_text())
        matches.append(dict(match=path.parent.name, captured=result['captured'], processed=result['processed'],
                            processed_fps=result['processed_fps'], failures=result['failures'],
                            first_submissions=result['counts'].get('frame_to_tap', 0),
                            log_drops=result['log_drops']))
        duration += (result['processed']-1)/result['processed_fps'] if result['processed_fps'] else 0.
        with gzip.open(path.with_name('latency.jsonl.gz'), 'rt') as stream:
            for line in stream:
                row = json.loads(line)
                counts[row['metric']] += 1
                if 'ms' in row:
                    samples[row['metric']].append(row['ms'])
                if row['metric'] == 'search':
                    if row.get('diagnostic', {}).get('candidates', 0) >= 2:
                        samples['search_active'].append(row['ms'])
                    counts['search_overruns'] += bool(row.get('deadline_overrun'))
                if row['metric'] == 'dropped':
                    counts['dropped_frames'] += row['count']
                if row['metric'] == 'processed':
                    counts['history_resets'] += row['history_resets']
                if row['metric'] == 'taps':
                    key = (path.parent.name, row['command_id'], row['attempt'])
                    if key in tap_keys:
                        duplicates.append(key)
                    tap_keys.add(key)
    timing = {name: quantiles(values) for name, values in samples.items()}
    end = timing.get('frame_to_tap', quantiles([]))
    return dict(schema='clasher.live-v4.fleet-summary.v1', host='127x04', matches=matches,
                perception='v3-body-hud-only', device='cpu', actuator='mock',
                timing_ms=timing, counts=dict(counts),
                processed_fraction=counts['processed']/max(1, counts['captured']),
                processed_fps=(counts['processed']-len(matches))/duration if duration else 0.,
                search_overrun_fraction=counts['search_overruns']/max(1, counts['search']),
                duplicate_tap_attempts=duplicates,
                stage_budget_pass={name: value['p50'] <= BUDGETS[name][0] and value['p95'] <= BUDGETS[name][1]
                                   for name, value in timing.items() if name in BUDGETS},
                frame_to_tap_p50_pass=bool(end['count'] and end['p50'] <= 200),
                frame_to_tap_p99_pass=bool(end['count'] and end['p99'] <= 400),
                processed_fraction_pass=counts['processed']/max(1, counts['captured']) >= .95,
                production_qualified=False,
                caveats=['Two train matches only; all 51 first submissions came from the first match.',
                         'Second match produced wait decisions with the limited fallback; no latency samples.',
                         'Search-active excludes wait-only/candidate-generation calls.',
                         'Mock transport sleeps 20 ms and cannot change recorded pixels.',
                         'Fleet CPU was shared (load 61.64/53.70/33.81 at suite launch, no console users).',
                         'No formal v4 weights, trained v3 event weights, Mac or ANE benchmark.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('root', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    a.output.write_text(json.dumps(aggregate(a.root), indent=2)+'\n')
