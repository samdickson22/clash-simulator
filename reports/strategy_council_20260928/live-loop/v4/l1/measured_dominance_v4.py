"""Amendment12 Tier1 primitives. No file admission, clock synthesis or GPU entry.

Callers must authenticate non-clock records/body seal and measured runs. A
certificate is checked by recomputing inputs through callbacks, not JSON claims.
"""
from collections import defaultdict
from fractions import Fraction
import math

GRID = tuple(i / 10 for i in range(1, 10))


def cell_id(epoch, threshold):
    if type(epoch) is not int or epoch not in range(1, 25):
        raise ValueError('Registered epoch required')
    if type(threshold) not in (int, float) or threshold not in GRID:
        raise ValueError('Registered event threshold required')
    return epoch, threshold


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite clock-independent timestamp required')
    return value


def key(row, truth=False):
    if not isinstance(row['episode_id'], str) or not row['episode_id']:
        raise ValueError('Episode required')
    if not isinstance(row['card'], str) or not row['card']:
        raise ValueError('Card required')
    if type(row['side']) is not int or row['side'] not in (0, 1):
        raise ValueError('Native side required')
    kind = row.get('kind', 'card_play')
    allowed = ('troop', 'building', 'spell', 'champion_ability') if truth else ('card_play', 'champion_ability')
    if kind not in allowed:
        raise ValueError('Explicit supported kind required')
    return row['episode_id'], row['card'], row['side'], ('champion_ability' if kind == 'champion_ability' else 'card_play')


def optimistic_counts(predictions, truth, *, episodes):
    """Maximum matching on stamp(p)<=exec(t)+500; NO lower endpoint.

    Within each key these edge sets are nested. Earliest-deadline truth paired
    with the earliest still-unmatched feasible prediction is maximum-cardinality
    (exchange argument). Neither availability nor execution estimates of
    predictions are used. Champion abilities and own side are not primary P/T.
    """
    episodes = list(episodes)
    if not episodes or len(episodes) != len(set(episodes)):
        raise ValueError('Unique complete population required')
    pg, tg = defaultdict(list), defaultdict(list)
    for p in predictions:
        if any(k in p for k in ('available_timestamp_ms', 'service_ms', 'clock')):
            raise ValueError('Bound inputs must be clock-free')
        k = key(p)
        stamp = number(p['production_timestamp_ms'])
        if k[0] not in episodes:
            raise ValueError('Prediction outside validation population')
        if k[2:] == (0, 'card_play'):
            pg[k].append(stamp)
    for t in truth:
        k = key(t, truth=True)
        deadline = number(t['execution_timestamp_ms']) + 500
        if k[0] not in episodes:
            raise ValueError('Truth outside validation population')
        if k[2:] == (0, 'card_play'):
            tg[k].append(deadline)
    matched = 0
    for k, stamps in pg.items():
        stamps = sorted(stamps); index = 0
        for deadline in sorted(tg.get(k, ())):
            if index < len(stamps) and stamps[index] <= deadline:
                index += 1
        matched += index
    return dict(truth=sum(map(len, tg.values())), predictions=sum(map(len, pg.values())), matched=matched)


def rank(row):
    e, t = cell_id(row['epoch'], row['threshold'])
    c = row['opponent']; n, p, m = (c[k] for k in ('truth', 'predictions', 'matched'))
    if any(type(v) is not int or v < 0 for v in (n, p, m)) or not n or m > min(n, p):
        raise ValueError('Valid primary counts required')
    return Fraction(2*m, n+p), Fraction(m, p) if p else Fraction(0), -e, Fraction(str(t))


def bound_cell(predictions, truth, *, episodes, epoch, threshold):
    cell_id(epoch, threshold)
    row = dict(epoch=epoch, threshold=threshold, opponent=optimistic_counts(predictions, truth, episodes=episodes))
    rank(row)
    return dict(row, evidence_kind='zero-service upper bound', measured=False)


def next_step(bounds, measured):
    """Pure deterministic Tier1 decision. 30 is a report checkpoint, not closure.

    Every actual run must be from the frozen controlled host/lifecycle. This
    helper cannot authenticate that condition; the file verifier must do so.
    """
    bounds = list(bounds); measured = list(measured)
    index = {}
    for b in bounds:
        cid = cell_id(b['epoch'], b['threshold'])
        if cid in index or b.get('measured') is not False or b.get('evidence_kind') != 'zero-service upper bound':
            raise ValueError('Distinct bound evidence required')
        rank(b); index[cid] = b
    if set(index) != {(e, t) for e in range(1, 25) for t in GRID}:
        raise ValueError('All216 bounds required')
    if len({b['opponent']['truth'] for b in bounds}) != 1:
        raise ValueError('Truth population differs')
    seen = set()
    for row in measured:
        cid = cell_id(row['epoch'], row['threshold'])
        if cid in seen or row.get('measured') is not True or row.get('evidence_kind') != 'measured completion+FIFO':
            raise ValueError('Unique measured-cell evidence required')
        seen.add(cid); b = index[cid]
        if any(row['opponent'][k] != b['opponent'][k] for k in ('truth', 'predictions')):
            raise ValueError('Clock-independent counts changed')
        if row['opponent']['matched'] > b['opponent']['matched']:
            raise ValueError('Measured result exceeds authenticated bound')
        rank(row)
    incumbent = max(measured, key=rank) if measured else None
    remaining = sorted((b for cid, b in index.items() if cid not in seen), key=rank, reverse=True)
    pending = [b for b in remaining if incumbent is None or rank(b) >= rank(incumbent)]
    eliminated = [b for b in remaining if incumbent is not None and rank(b) < rank(incumbent)]
    return dict(incumbent=incumbent, next_cell=pending[0] if pending else None,
                closed=incumbent is not None and not pending,
                eliminated=[list(cell_id(b['epoch'], b['threshold'])) for b in eliminated],
                pending=len(pending), measured_cells=len(measured),
                budget_checkpoint=len(measured) >= 30 and bool(pending),
                tier2_enabled=False, heldout_opening_authorized=False)


def verify_certificate(claimed, *, recompute_bounds, recompute_measured):
    """Callbacks must reauthenticate/recompute actual files; no claimed scores."""
    bounds, measured = list(recompute_bounds()), list(recompute_measured())
    for i, row in enumerate(measured):
        scheduled = next_step(bounds, measured[:i])['next_cell']
        if scheduled is None or cell_id(row['epoch'], row['threshold']) != cell_id(scheduled['epoch'], scheduled['threshold']):
            raise ValueError('First-measurement history differs from frozen bound order')
    expected = next_step(bounds, measured)
    if expected != claimed or not expected['closed']:
        raise ValueError('Tampered or unterminated dominance certificate')
    return expected
