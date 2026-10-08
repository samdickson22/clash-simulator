"""Synthetic scorer regressions, run through an authorized fleet wrapper."""
import itertools
import json
import random

from scoring_v4 import match_events, score_events, match_bootstrap, select_epoch, select_threshold


def truth(t, **kw):
    return dict(dict(episode_id='a', card='Knight', side=0, kind='troop',
                     execution_timestamp_ms=t, event_time_interval_ms=[t-20, t+20],
                     x_tiles=3., y_tiles=4.), **kw)


def pred(t, **kw):
    return dict(dict(episode_id='a', card='Knight', side=0, available_timestamp_ms=t,
                     execution_timestamp_ms=0., x_tiles=3., y_tiles=4.), **kw)


def rejected(fn):
    try:
        fn()
    except (ValueError, KeyError):
        return
    raise AssertionError('Invalid input accepted')


def main():
    checks = 0
    # Availability and inclusive boundary, never the backdated execution estimate.
    assert match_events([pred(-1), pred(500), pred(501, execution_timestamp_ms=0)], [truth(0)]) == [(1, 0)]
    checks += 1
    assert match_events([pred(450), pred(800)], [truth(0), truth(400)]) == [(0, 0), (1, 1)]
    checks += 1
    assert match_events([pred(0)], [truth(0)]) == [(0, 0)]
    assert match_events([pred(0)], [truth(0)], timing='conservative') == []
    assert match_events([pred(480)], [truth(0)], timing='conservative') == [(0, 0)]
    assert match_events([pred(481)], [truth(0)], timing='conservative') == []
    checks += 1
    assert match_events([pred(10, card='Giant'), pred(10, side=1), pred(10, episode_id='b')], [truth(0)]) == []
    checks += 1
    s = score_events([pred(10), pred(11), pred(12, kind='champion_ability')],
                     [truth(0), truth(0, kind='champion_ability'), truth(0, card='Fireball', kind='spell')], episodes=['a', 'b'])
    assert s['opponent']['matched'] == 1 and s['opponent']['false_positive'] == 1
    assert s['champion_abilities']['matched'] == 1
    assert s['placement']['spell']['fraction'] == 0 and s['placement']['troop_building']['fraction'] == 1
    assert s['per_match']['b']['0']['truth'] == 0
    checks += 1
    s = score_events([pred(10, x_tiles=None, execution_timestamp_ms=None)], [truth(0)], episodes=['a'])
    assert s['placement']['troop_building']['fraction'] == 0 and s['execution_error']['absolute_p95_ms'] is None
    checks += 1
    # Exhaustive independent maximum-cardinality/minimum-cost oracle for small graphs.
    rng = random.Random(6110)
    for _ in range(120):
        ps = [pred(rng.randrange(0, 1600)) for _ in range(rng.randrange(1, 5))]
        ts = [truth(rng.randrange(0, 1100)) for _ in range(rng.randrange(1, 5))]
        best = (0, 0.)
        for k in range(1, min(len(ps), len(ts))+1):
            for pi in itertools.combinations(range(len(ps)), k):
                for tj in itertools.permutations(range(len(ts)), k):
                    delays = [ps[i]['available_timestamp_ms']-ts[j]['execution_timestamp_ms'] for i, j in zip(pi, tj)]
                    if all(0 <= d <= 500 for d in delays):
                        best = max(best, (k, -sum(delays)))
        pairs = match_events(ps, ts)
        assert (len(pairs), -sum(ps[i]['available_timestamp_ms']-ts[j]['execution_timestamp_ms'] for i, j in pairs)) == best
    checks += 120
    s = score_events([pred(10), pred(10, side=1)], [truth(0), truth(0, side=1)], episodes=['a'])
    b = match_bootstrap({'t6': s, 't7': s})
    assert b['resamples'] == 10000 and b['seed'] == 6110
    assert b['arms']['t6']['opponent_recall']['interval95'] == [1., 1.]
    assert b['paired_differences'][0]['metrics']['all_sides_precision']['interval95'] == [0., 0.]
    checks += 1
    empty = score_events([], [], episodes=['a'])
    assert match_bootstrap({'empty': empty})['arms']['empty']['opponent_recall'] == dict(valid_resamples=0, interval95=None)
    rejected(lambda: match_bootstrap({'a': s, 'b': score_events([], [], episodes=['b'])}))
    checks += 1
    count = dict(truth=10, predictions=10, matched=5)
    sweep = [dict(threshold=i/10, opponent=count) for i in range(1, 10)]
    assert select_threshold(sweep)['threshold'] == .9
    sweep[2]['opponent'] = dict(truth=10, predictions=6, matched=4)  # Same F1, higher precision.
    assert select_threshold(sweep)['threshold'] == .3
    rows = [dict(epoch=i, opponent=count) for i in range(1, 25)]
    assert select_epoch(rows)['epoch'] == 1
    rows[11]['opponent'] = dict(truth=10, predictions=6, matched=4)
    assert select_epoch(rows)['epoch'] == 12
    checks += 1
    rejected(lambda: select_epoch(rows[:23]))
    rejected(lambda: select_threshold(sweep[:8]))
    rejected(lambda: score_events([pred(float('nan'))], [truth(0)], episodes=['a']))
    rejected(lambda: score_events([], [truth(0, kind='unknown')], episodes=['a']))
    rejected(lambda: score_events([], [truth(0)], episodes=['b']))
    rejected(lambda: match_events([pred(0)], [truth(0, event_time_interval_ms=[1, 2])], timing='conservative'))
    checks += 6
    print(json.dumps(dict(pass_=True, checks=checks, synthetic_only=True, heldout_payloads_opened=False)), flush=True)


if __name__ == '__main__':
    main()
