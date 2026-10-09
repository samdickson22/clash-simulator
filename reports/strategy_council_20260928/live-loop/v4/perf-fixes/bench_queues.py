"""Paired synthetic CPU runtime measurements; transport evidence, not E4."""
import argparse
import json
from pathlib import Path
from clasher.live.runtime import run, quantiles

DECK = ['Knight', 'Archers', 'Giant', 'Musketeer', 'Fireball', 'Zap', 'Cannon', 'Skeletons']


def main(a):
    a.output.mkdir(parents=True, exist_ok=False)
    prior = a.output/'prior.json'
    prior.write_text(json.dumps({'decks': [{'cards': DECK}]}))
    costs = dict(zip(DECK, [3, 3, 5, 4, 4, 2, 3, 1]))
    measurements = []
    for repeat in range(a.repeats):
        for mode in (('polling', 'blocking') if repeat % 2 == 0 else ('blocking', 'polling')):
            config = dict(source={'kind': 'synthetic', 'episode': f'synthetic-{repeat}-{mode}'},
                frames=a.frames, fps=20, perception={'kind': 'synthetic', 'deck': DECK},
                belief={'own_deck': DECK, 'prior': str(prior), 'costs': costs},
                planner={'kind': 'synthetic'}, actuator={'kind': 'mock', 'tap_seconds': .001},
                blocking_queues=mode == 'blocking', startup_timeout=60, max_seconds=60)
            result = run(config, a.output/f'{repeat}-{mode}')
            assert not result['failures'] and not result['log_drops']
            row = dict(repeat=repeat, mode=mode, timing_ms=result['timing_ms'],
                       processed=result['processed'], captured=result['captured'])
            measurements.append(row)
            print(json.dumps(row), flush=True)
    keys = ('capture_queue_age', 'perception_queue_age', 'belief_queue_age', 'frame_to_tap')
    summary = {mode: {key: quantiles([r['timing_ms'][key]['p50'] for r in measurements
                                    if r['mode'] == mode and key in r['timing_ms']])
                      for key in keys} for mode in ('polling', 'blocking')}
    (a.output/'queue-benchmark.json').write_text(json.dumps(dict(
        schema='clasher.live-perf.queue-benchmark.v1', synthetic_only=True,
        measurements=measurements, median_of_run_medians_ms=summary), indent=2)+'\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=3)
    p.add_argument('--frames', type=int, default=120)
    main(p.parse_args())
