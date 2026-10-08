"""Pure body-scoring preparation; no dataset access, selection seal or inference.

Callers supply amendment-03 cleaned snapshots and authenticate their provenance.
Known visible bodies remain in the denominator even outside the model vocabulary.
Unknown visibility/identity is masked, never negative truth. Alignment is to the
latest past snapshot within five native ticks; future snapshots cannot score.
"""
from bisect import bisect_right
import math

import numpy as np
from scipy.optimize import linear_sum_assignment


RADIUS_TILES = 3.0  # Historical evaluate_l1_perception.match_entities radius.
POLICY = dict(radius_tiles=RADIUS_TILES, maximum_past_age_ticks=5,
              unknown_mask_half_cells=3, grid_shape=[64, 36],
              assignment='maximum cardinality, then minimum tile distance',
              population='all trusted visible nondeploying bodies, both native owners',
              phantom_rate='unmatched unmasked predictions / scored predictions',
              drop_rate='unmatched truth / scored truth')


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Finite numeric field required')
    return float(value)


def body_key(row):
    if (not isinstance(row.get('identity'), str) or not row['identity']
            or type(row.get('owner')) is not int or row['owner'] not in (0, 1)):
        raise ValueError('Body identity and native owner required')
    number(row['x']); number(row['y'])
    return row['identity'], row['owner']


def cell(x, y):
    return min(35, max(0, int(number(x)*2))), min(63, max(0, int(number(y)*2)))


class BodyTruth:
    def __init__(self, cleaned_snapshots):
        self.rows = list(cleaned_snapshots)
        self.ticks = [number(row['tick']) for row in self.rows]
        if any(b <= a for a, b in zip(self.ticks, self.ticks[1:])):
            raise ValueError('Unique chronological body snapshots required')
        for row in self.rows:
            ids = set()
            for obj in row['objects']:
                if obj.get('native_id') is None or obj['native_id'] in ids:
                    raise ValueError('Unique native body IDs required per snapshot')
                ids.add(obj['native_id'])
                number(obj['x']); number(obj['y'])
                if 'body_identity_source' not in obj or 'label_join' not in obj:
                    raise ValueError('Amendment-03 cleaned objects required')

    def at(self, tick):
        tick = number(tick)
        i = bisect_right(self.ticks, tick)-1
        if i < 0 or tick-self.ticks[i] > 5:
            return [], np.zeros((64, 36), dtype=bool), False
        row = self.rows[i]
        valid = np.ones((64, 36), dtype=bool)
        truth = []
        for obj in row['objects']:
            x, y = number(obj['x'])/1000, number(obj['y'])/1000
            gx, gy = cell(x, y)
            known = (bool(obj.get('body_name'))
                     and obj['body_identity_source'] in ('unique_card_payload_hp', 'tower_anchor_hp')
                     and obj['label_join'] == 'same_tick_coherent'
                     and obj.get('metadata_tick') == row['tick']
                     and obj.get('visible_hint') == 'visible' and obj.get('deploying') is False)
            if known:
                value = dict(identity=obj['body_name'], owner=obj['owner'], x=x, y=y)
                body_key(value)
                truth.append(value)
            else:
                valid[max(0, gy-3):gy+4, max(0, gx-3):gx+4] = False
        # Preserve trusted positive centres where uncertain regions overlap.
        for value in truth:
            gx, gy = cell(value['x'], value['y'])
            valid[gy, gx] = True
        return truth, valid, True


def match_bodies(predictions, truth):
    """One-to-one matching, without letting invalid edges steal valid matches."""
    pk = [body_key(p) for p in predictions]
    tk = [body_key(t) for t in truth]
    if not predictions or not truth:
        return []
    blocked = (min(len(predictions), len(truth))+1)*(RADIUS_TILES+1)
    cost = np.full((len(predictions), len(truth)), blocked)
    for i, p in enumerate(predictions):
        for j, t in enumerate(truth):
            if pk[i] == tk[j]:
                distance = math.hypot(p['x']-t['x'], p['y']-t['y'])
                if distance <= RADIUS_TILES:
                    cost[i, j] = distance
    ii, jj = linear_sum_assignment(cost)
    return [(int(i), int(j)) for i, j in zip(ii, jj) if cost[i, j] < blocked]


def score_frame(predictions, aligned):
    predictions = list(predictions)
    ids = set()
    for p in predictions:
        body_key(p)
        if type(p.get('track_id')) is not int or p['track_id'] < 0 or p['track_id'] in ids:
            raise ValueError('Unique nonnegative runtime track IDs required')
        ids.add(p['track_id'])
    truth, valid, eligible = aligned
    pairs = match_bodies(predictions, truth)
    matched = {i for i, _ in pairs}
    # Match first: an identifiable positive in an overlapping uncertain region
    # must not be discarded. Only unmatched predictions can be ignored by masks.
    ignored = set()
    for i, p in enumerate(predictions):
        gx, gy = cell(p['x'], p['y'])
        in_arena = 0 <= p['x'] < 18 and 0 <= p['y'] < 32
        if i not in matched and (not eligible or (in_arena and not valid[gy, gx])):
            ignored.add(i)
    return dict(truth=len(truth), predictions=len(predictions)-len(ignored),
                matched=len(pairs), ignored_predictions=len(ignored),
                eligible_frames=int(eligible), unscorable_frames=int(not eligible))


def summarize(frames):
    keys = ('truth', 'predictions', 'matched', 'ignored_predictions',
            'eligible_frames', 'unscorable_frames')
    totals = dict.fromkeys(keys, 0)
    for row in frames:
        if (any(type(row.get(k)) is not int or row[k] < 0 for k in keys)
                or row['matched'] > min(row['truth'], row['predictions'])
                or row['eligible_frames']+row['unscorable_frames'] != 1
                or (row['unscorable_frames'] and any(row[k] for k in ('truth', 'predictions', 'matched')))):
            raise ValueError('Invalid per-frame body counts')
        for k in keys:
            totals[k] += row[k]
    nt, npred, matched = (totals[k] for k in ('truth', 'predictions', 'matched'))
    return dict(totals, missed=nt-matched, false_positive=npred-matched,
                recall=matched/nt if nt else None, precision=matched/npred if npred else None,
                f1=2*matched/(nt+npred) if nt+npred else None,
                phantom_rate=(npred-matched)/npred if npred else None,
                drop_rate=(nt-matched)/nt if nt else None)
