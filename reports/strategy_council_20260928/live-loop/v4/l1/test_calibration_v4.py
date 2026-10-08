"""Synthetic validation calibration checks; run on a permitted compute host."""
import itertools
import json

from calibration_v4 import fit_validation_calibration
from clasher.vision.l1_v4 import fit_isotonic, calibrated
from test_scoring_v4 import pred, truth, rejected


def main():
    checks = 0
    # Independent exhaustive contiguous-partition least-squares oracle for PAVA.
    for n in range(1, 6):
        scores = [(i+1)/(n+1) for i in range(n)]
        for labels in itertools.product((0, 1), repeat=n):
            best = float('inf')
            for cuts in itertools.product((0, 1), repeat=n-1):
                starts = [0] + [i+1 for i, cut in enumerate(cuts) if cut] + [n]
                means = [sum(labels[a:b])/(b-a) for a, b in zip(starts, starts[1:])]
                if means != sorted(means):
                    continue
                error = sum((labels[i]-mean)**2 for a, b, mean in
                            zip(starts, starts[1:], means) for i in range(a, b))
                best = min(best, error)
            knots = fit_isotonic(scores, list(labels))
            error = sum((y-calibrated(x, knots))**2 for x, y in zip(scores, labels))
            assert abs(error-best) < 1e-12
            checks += 1
    assert fit_isotonic([.5, .5, .5], [1, 0, 1]) == [[.5, 2/3]]
    checks += 1
    def fit(ps, ts, **kw):
        return fit_validation_calibration(ps, ts, **dict(
            dict(episodes=['a', 'empty'], split_by_episode={'a': 'validation', 'empty': 'validation'}), **kw))
    ps = [pred(i*1000+10, score=.5) for i in range(20)]
    ts = [truth(i*1000) for i in range(10)]
    result = fit(ps, ts)
    assert result['calibration']['Knight'] == [[.5, .5]]
    assert result['support']['Knight']['fit'] == 'per_card'
    assert result['episodes'] == ['a', 'empty'] and not result['selection_seal']
    checks += 1
    result = fit(ps[:19], ts)
    assert set(result['calibration']) == {'default'}
    assert result['support']['Knight']['fit'] == 'pooled'
    assert calibrated(.9, result['calibration']['default']) == 10/19
    checks += 1
    result = fit([pred(10, score=.7), pred(11, score=.7), pred(10, side=1, score=.7)],
                 [truth(0), truth(0, side=1)])
    assert result['matched'] == 2 and result['calibration']['default'] == [[.7, 2/3]]
    checks += 1
    for split in ('train', 'heldout', None):
        rejected(lambda: fit(ps, ts, split_by_episode={'a': split, 'empty': 'validation'}))
        checks += 1
    for score in (float('nan'), float('inf'), True, -0.1, 1.1):
        rejected(lambda: fit([pred(10, score=score)], ts))
        checks += 1
    for call in (
        lambda: fit([], ts),
        lambda: fit(ps, ts, episodes=['a', 'a']),
        lambda: fit([pred(10, episode_id='outside', score=.5)], ts),
        lambda: fit([pred(10, kind='champion_ability', score=.5)], ts),
        lambda: fit(ps, [truth(0, kind='champion_ability')]),
        lambda: fit([pred(10, card='default', score=.5)], ts),
    ):
        rejected(call)
        checks += 1
    print(json.dumps(dict(pass_=True, checks=checks, synthetic_only=True,
                         heldout_payloads_opened=False)), flush=True)


if __name__ == '__main__':
    main()
