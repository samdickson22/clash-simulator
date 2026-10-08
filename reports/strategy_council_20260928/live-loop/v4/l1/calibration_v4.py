"""Validation calibration primitive; no file I/O, replay, or selection seal.

The caller supplies the selected model's final thresholded card-play stream,
including temporal suppression, and the complete validation episode population.
Split provenance must ultimately come from the guarded replay driver, not from
prediction rows. This helper validates that declaration; it cannot authenticate it.
"""
from collections import defaultdict
import math

from clasher.vision.l1_v4 import fit_isotonic
from scoring_v4 import match_events


def fit_validation_calibration(predictions, truth, *, episodes, split_by_episode):
    """Fit pooled and eligible per-card existence probabilities on both seats.

    Positive labels are one-to-one availability-time matches within 500 ms.
    Duplicate/unmatched predictions are negative. Per-card fits require at least
    20 predictions; other cards (including unseen cards) use the pooled default.
    Champion abilities must be supplied to their separate reporting path.
    An empty prediction stream is uncalibratable and fails closed.
    """
    episodes = list(episodes)
    if (not episodes or any(not isinstance(e, str) or not e for e in episodes)
            or len(set(episodes)) != len(episodes)):
        raise ValueError('Complete unique validation episode population required')
    if any(split_by_episode.get(e) != 'validation' for e in episodes):
        raise ValueError('Calibration admits validation episodes only')
    population = set(episodes)
    if any(r['episode_id'] not in population for r in [*predictions, *truth]):
        raise ValueError('Row outside admitted validation population')
    if not predictions:
        raise ValueError('No validation predictions: calibration remains blocked')
    if (any(p.get('kind', 'card_play') != 'card_play' for p in predictions)
            or any(t['kind'] not in ('troop', 'building', 'spell') for t in truth)):
        raise ValueError('Card-play calibration requires abilities separated')
    scores = []
    for p in predictions:
        score = p['score']
        if (isinstance(score, bool) or not isinstance(score, (int, float))
                or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError('Finite raw score in [0,1] required')
        if p['card'] == 'default':
            raise ValueError('Card collides with pooled calibration key')
        scores.append(float(score))
    matched = {i for i, _ in match_events(predictions, truth)}
    labels = [int(i in matched) for i in range(len(predictions))]
    knots = {'default': fit_isotonic(scores, labels)}
    by_card = defaultdict(list)
    for i, p in enumerate(predictions):
        by_card[p['card']].append(i)
    support = {}
    for card, indices in sorted(by_card.items()):
        eligible = len(indices) >= 20
        if eligible:
            knots[card] = fit_isotonic([scores[i] for i in indices],
                                     [labels[i] for i in indices])
        support[card] = dict(predictions=len(indices), matched=sum(labels[i] for i in indices),
                             fit='per_card' if eligible else 'pooled')
    return dict(schema='clasher.v4.validation-calibration.v1', calibration=knots,
                support=support, predictions=len(predictions), matched=len(matched),
                episodes=sorted(episodes), scope='both_native_seats_card_plays',
                timing='availability_500ms_one_to_one', selection_seal=False)
