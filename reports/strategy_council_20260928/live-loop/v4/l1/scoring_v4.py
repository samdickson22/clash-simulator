"""Pure scoring/selection primitives; no dataset I/O or heldout entry point.

Inputs use one common production-time clock in milliseconds. Predictions must
carry output completion time, including FIFO backlog. Truth timing conversion
and authenticated replay admission belong to the future evaluation driver.
"""
from collections import defaultdict
from fractions import Fraction
import math

import numpy as np
from scipy.optimize import linear_sum_assignment


def _number(row, key):
    value = row[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'Invalid finite number: {key}')
    return float(value)


def _key(row):
    if not isinstance(row['episode_id'], str) or not row['episode_id']:
        raise ValueError('Episode ID required')
    if (not isinstance(row['card'], str) or not row['card']
            or type(row['side']) is not int or row['side'] not in (0, 1)):
        raise ValueError('Card and native side 0/1 required')
    return row['episode_id'], row['card'], row['side']


def match_events(predictions, truth, *, timing='point'):
    """Maximum-cardinality, then minimum availability-latency assignment.

    Point mode uses explicitly mapped execution_timestamp_ms. Conservative
    sensitivity uses availability >= bracket upper and <= bracket lower + 500.
    Spatial error and backdated predictions never influence event matching.
    Returns original (prediction index, truth index) pairs, including abilities
    only when both inputs explicitly identify them as champion_ability.
    """
    if timing not in ('point', 'conservative'):
        raise ValueError('Unknown timing rule')
    pg, tg = defaultdict(list), defaultdict(list)
    for i, p in enumerate(predictions):
        kind = p.get('kind', 'card_play')
        if kind not in ('card_play', 'champion_ability'):
            raise ValueError('Unknown prediction kind')
        _number(p, 'available_timestamp_ms')
        pg[(*_key(p), kind)].append(i)
    for j, t in enumerate(truth):
        kind = t['kind']
        if kind not in ('troop', 'building', 'spell', 'champion_ability'):
            raise ValueError('Unknown truth kind; placement denominator must be explicit')
        _number(t, 'execution_timestamp_ms')
        if kind != 'champion_ability':
            _number(t, 'x_tiles')
            _number(t, 'y_tiles')
        if timing == 'conservative':
            lo, hi = t['event_time_interval_ms']
            if not all(math.isfinite(x) for x in (lo, hi)) or not lo <= t['execution_timestamp_ms'] <= hi:
                raise ValueError('Invalid execution bracket')
        tg[(*_key(t), 'champion_ability' if kind == 'champion_ability' else 'card_play')].append(j)
    pairs = []
    for key, pi in pg.items():
        ti = tg.get(key, [])
        if not ti:
            continue
        # Losing one admissible match costs more than every valid edge combined.
        blocked = (min(len(pi), len(ti)) + 1) * 501.
        costs = np.full((len(pi), len(ti)), blocked)
        for i, ip in enumerate(pi):
            available = predictions[ip]['available_timestamp_ms']
            for j, jt in enumerate(ti):
                t = truth[jt]
                lo, hi = (t['event_time_interval_ms'] if timing == 'conservative'
                          else (t['execution_timestamp_ms'], t['execution_timestamp_ms']))
                if hi <= available <= lo + 500:
                    costs[i, j] = available - lo
        ii, jj = linear_sum_assignment(costs)
        pairs.extend((pi[i], ti[j]) for i, j in zip(ii, jj) if costs[i, j] < blocked)
    return sorted(pairs)


def _counts(nt, npred, matched):
    return dict(truth=nt, predictions=npred, matched=matched,
                false_positive=npred-matched, missed=nt-matched,
                recall=matched/nt if nt else None,
                precision=matched/npred if npred else None,
                f1=2*matched/(nt+npred) if nt+npred else None)


def score_events(predictions, truth, *, episodes, timing='point'):
    """Score all admitted episodes, including empty matches for bootstrapping.

    No gates are certified here. Missing placement counts as a placement miss;
    any missing execution estimate makes the overall error p95 unavailable.
    """
    episodes = list(episodes)
    if len(set(episodes)) != len(episodes) or not episodes:
        raise ValueError('Unique complete episode population required')
    if any(r['episode_id'] not in episodes for r in [*predictions, *truth]):
        raise ValueError('Row outside supplied episode population')
    pairs = match_events(predictions, truth, timing=timing)
    play_p = {i for i, p in enumerate(predictions) if p.get('kind', 'card_play') == 'card_play'}
    play_t = {j for j, t in enumerate(truth) if t['kind'] != 'champion_ability'}
    play_pairs = [(i, j) for i, j in pairs if j in play_t]

    def subset_counts(ps, ts):
        return _counts(len(ts), len(ps), sum(i in ps and j in ts for i, j in pairs))

    per_match = {}
    for ep in episodes:
        per_match[ep] = {}
        for side in (0, 1):
            ps = {i for i in play_p if predictions[i]['episode_id'] == ep and predictions[i]['side'] == side}
            ts = {j for j in play_t if truth[j]['episode_id'] == ep and truth[j]['side'] == side}
            per_match[ep][str(side)] = subset_counts(ps, ts)
    per_card = []
    for card, side in sorted({(r['card'], r['side']) for r in [*predictions, *truth]}):
        ps = {i for i in play_p if (predictions[i]['card'], predictions[i]['side']) == (card, side)}
        ts = {j for j in play_t if (truth[j]['card'], truth[j]['side']) == (card, side)}
        if ps or ts:
            per_card.append(dict(card=card, side=side, eligible=len(ts) >= 10, **subset_counts(ps, ts)))
    placement = {}
    for name, kinds, radius in (('troop_building', ('troop', 'building'), 1.), ('spell', ('spell',), 1.5)):
        total = sum(truth[j]['kind'] in kinds for j in play_t)
        hits = 0
        for i, j in play_pairs:
            if truth[j]['kind'] not in kinds:
                continue
            p, t = predictions[i], truth[j]
            if p.get('x_tiles') is None or p.get('y_tiles') is None:
                continue
            error = math.hypot(_number(p, 'x_tiles')-_number(t, 'x_tiles'),
                               _number(p, 'y_tiles')-_number(t, 'y_tiles'))
            hits += error <= radius
        placement[name] = dict(truth=total, hits=hits, radius_tiles=radius,
                               fraction=hits/total if total else None)
    errors = [abs(_number(predictions[i], 'execution_timestamp_ms')-_number(truth[j], 'execution_timestamp_ms'))
              for i, j in play_pairs if predictions[i].get('execution_timestamp_ms') is not None]
    opponent_p = {i for i in play_p if predictions[i]['side'] == 0}
    opponent_t = {j for j in play_t if truth[j]['side'] == 0}
    return dict(timing=timing, all_sides=subset_counts(play_p, play_t),
                opponent=subset_counts(opponent_p, opponent_t), per_match=per_match,
                per_card_side=per_card, placement=placement,
                execution_error=dict(matched=len(play_pairs), estimates=len(errors),
                    absolute_p95_ms=float(np.quantile(errors, .95)) if errors and len(errors) == len(play_pairs) else None),
                champion_abilities=subset_counts(set(range(len(predictions)))-play_p, set(range(len(truth)))-play_t),
                pairs=[dict(prediction=i, truth=j) for i, j in pairs])


def match_bootstrap(arms, *, resamples=10000, seed=6110):
    """Paired match-cluster intervals; both seats stay in each selected cluster.

    `arms` maps names to score_events results. The identical sampled indices
    are used in every arm and paired differences are second minus first.
    Undefined denominator draws are counted; an interval is null unless every
    draw is defined. This prevents empty-population draws from certifying gates.
    """
    if not arms or resamples < 1:
        raise ValueError('Arms and positive resample count required')
    names = list(arms)
    episodes = sorted(arms[names[0]]['per_match'])
    if not episodes or any(sorted(v['per_match']) != episodes for v in arms.values()):
        raise ValueError('Paired arms need identical complete match populations')
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(episodes), size=(resamples, len(episodes)))
    metrics = {}
    for name, result in arms.items():
        values = {}
        for label, sides in (('opponent', ('0',)), ('all_sides', ('0', '1'))):
            rows = np.array([[sum(result['per_match'][ep][s][k] for s in sides)
                              for k in ('truth', 'predictions', 'matched')] for ep in episodes], dtype=np.int64)
            total = rows[draws].sum(axis=1)
            for metric, column in (('recall', 0), ('precision', 1)):
                valid = total[:, column] > 0
                v = np.full(resamples, np.nan)
                v[valid] = total[valid, 2]/total[valid, column]
                values[label+'_'+metric] = v
        metrics[name] = values

    def interval(v):
        valid = int(np.isfinite(v).sum())
        return dict(valid_resamples=valid, interval95=np.quantile(v, [.025, .975]).tolist() if valid == resamples else None)

    return dict(seed=seed, resamples=resamples, matches=len(episodes),
        arms={n: {k: interval(v) for k, v in m.items()} for n, m in metrics.items()},
        paired_differences=[dict(first=a, second=b, metrics={k: interval(metrics[b][k]-metrics[a][k]) for k in metrics[a]})
                            for ai, a in enumerate(names) for b in names[ai+1:]])


def _rank(row):
    c = row['opponent']
    n, p, m = c['truth'], c['predictions'], c['matched']
    if any(type(x) is not int or x < 0 for x in (n, p, m)) or m > min(n, p):
        raise ValueError('Invalid validation counts')
    if not n:
        raise ValueError('Validation truth required for selection')
    return Fraction(2*m, n+p), Fraction(m, p) if p else Fraction(0)


def select_threshold(sweep):
    """Registered nine-point grid, F1 then precision then higher threshold."""
    if len(sweep) != 9 or sorted(r['threshold'] for r in sweep) != [i/10 for i in range(1, 10)]:
        raise ValueError('Complete registered threshold grid required')
    if len({r['opponent']['truth'] for r in sweep}) != 1:
        raise ValueError('Threshold population changed')
    return max(sweep, key=lambda r: (*_rank(r), r['threshold']))


def select_epoch(rows):
    """All 24 formal epochs, opponent F1 then precision then earlier epoch."""
    if len(rows) != 24 or sorted(r['epoch'] for r in rows) != list(range(1, 25)):
        raise ValueError('All 24 formal validation epochs required')
    if len({r['opponent']['truth'] for r in rows}) != 1:
        raise ValueError('Epoch validation population changed')
    return max(rows, key=lambda r: (*_rank(r), -r['epoch']))
