"""Read-only post-run GC deployment supplement; never changes timing games."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ARMS = ('K2-200', 'K0-200', 'K4-200')


def quantiles(values):
    values = sorted(values)
    def percentile(q):
        if not values:
            return 0.0
        rank = (len(values)-1)*q
        low = int(rank)
        high = min(low+1, len(values)-1)
        return values[low] + (values[high]-values[low])*(rank-low)
    return dict(zip(('p50', 'p95', 'p99', 'max'),
                    (percentile(q) for q in (.5, .95, .99, 1.))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--games', type=Path, required=True)
    parser.add_argument('--worker-log', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    results = json.loads(args.results.read_text())
    assert results['checks']['games'] == 1800 and results['paired_seeds'] == 600
    terminal_ticks = {}
    for line in args.worker_log.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and 'game' in row and 'ticks' in row:
            assert row['terminal'] and row['game'] not in terminal_ticks
            terminal_ticks[row['game']] = row['ticks']
    assert len(terminal_ticks) == 1800
    groups = {arm: [] for arm in ARMS}
    for path in sorted(args.games.glob('*.json')):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == results['file_shas'][path.name]
        row = json.loads(path.read_text())
        groups[row['cohort']].append(row)
    out = dict(utc=subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip(),
               results_sha256=hashlib.sha256(args.results.read_bytes()).hexdigest(),
               worker_log_sha256=hashlib.sha256(args.worker_log.read_bytes()).hexdigest(),
               source='Frozen raw GC duration/generation/during_decision plus terminal ticks from worker.log',
               scope='Recorded collections from game setup through the post-extraction snapshot; file writing and inter-game gaps are excluded. Timestamps and finer phase are unavailable.',
               overlap_status='Live decision-opportunity overlap unknown: no pause start/end timestamps, poll deadlines, or opportunity/channel state were recorded. Zero during_decision is not evidence of zero delayed polls.',
               live_caveat='The sim includes GC in whole-game wall/CPU but does not advance game ticks or charge decision lateness for maintenance. Live maintenance can delay the next poll; results do not quantify that loss penalty.',
               arms={})
    for arm, rows in groups.items():
        assert len(rows) == 600
        events = [event for row in rows for event in row['search_ab']['gc_maintenance']]
        pauses = [event['seconds'] for event in events]
        minutes = sum(terminal_ticks[row['identity']] for row in rows)/1200
        during = sum(bool(event['during_decision']) for event in events)
        assert during == 0 and minutes > 0
        assert len(events) == results['arms'][arm]['gc_maintenance_count']
        distribution = quantiles([pause*1000 for pause in pauses])
        assert all(abs(distribution[key]-results['arms'][arm]['gc_maintenance_ms'][key]) < 1e-6 for key in distribution)
        out['arms'][arm] = dict(games=600, count=len(events), generation_counts=dict(Counter(str(event['generation']) for event in events)),
                               pause_ms=distribution, total_pause_seconds=sum(pauses),
                               game_minutes=minutes, count_per_game_minute=len(events)/minutes,
                               pause_ms_per_game_minute=sum(pauses)*1000/minutes,
                               count_above_ms={str(limit):sum(pause*1000 > limit for pause in pauses) for limit in (50, 250, 500)},
                               during_decision_window_count=during,
                               overlapping_live_decision_opportunity_count=None,
                               overlap_status='unknown; frozen instrumentation has no timestamps/opportunity trace')
    args.out.write_text(json.dumps(out, indent=2)+'\n')
    print(json.dumps(out, indent=2))


if __name__ == '__main__':
    main()
