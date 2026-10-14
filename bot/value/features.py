"""Public-state features for the leaf value V(state, seat) (exploration).

Input per state: the native `public_view(state, s)` of both seats (seat-relative, point-mirrored
frame: own king at (9, 3)), phi's `evaluation_parts(state)` (seat-0 frame) and the tick. Every
feature is computed from one seat's perspective; the model is antisymmetric by construction
(z = g(F(me)) - g(F(them))), so P(me) + P(them) = 1.

Only public information plus the planner's sampled hidden opponent hand/elixir enter (the
search root and its rollout leaves); outcomes appear only as training targets.
"""
from __future__ import annotations

import numpy as np

REGULATION, DOUBLE, OVERTIME = 3600, 2400, 2400  # ticks (20/s): 3 min, double elixir from 2:00, 2 min OT
HALF = 16.0

# Card tokens of the C56 hand vocabulary are learned per model (see fit.py: vocab); unknown -> ignored.
BASE_NAMES = (
    ['crowns', 'princess_pressure', 'king_pressure', 'tiebreak', 'early', 'board', 'danger'] +
    ['elixir_me', 'elixir_them'] +
    ['tw_me_l', 'tw_me_r', 'tw_me_k', 'tw_them_l', 'tw_them_r', 'tw_them_k', 'alive_me', 'alive_them'] +
    ['t_reg', 't_double', 't_ot', 'in_ot'] +
    [f'val_{o}_{lane}_{zone}' for o in ('me', 'them') for lane in ('l', 'r') for zone in ('home', 'away')] +
    [f'{k}_{o}' for k in ('bld', 'wincon', 'count') for o in ('me', 'them')]
)


def phi_from(parts_me, elixir_me, elixir_them, elixir_weight=1.0):
    """leaf.rs phi for a non-terminal state, from seat-relative parts (bit-compatible formula)."""
    p = parts_me
    objective = .55*p[0] + .25*p[1] + .10*p[2] + .10*p[3] - .20*p[4]
    potential = min(1.5, max(-1.5, objective + .08*p[5] + .12*p[6]))
    return potential + elixir_weight*.08*(elixir_me - elixir_them)/16.


def perspective(pv_me, pv_them, parts0, seat, tick):
    """Base feature vector (BASE_NAMES order) for `seat` = the owner of pv_me."""
    sign = 1. if seat == 0 else -1.
    out = [sign*x for x in parts0]
    out += [pv_me['elixir'], pv_them['elixir']]
    tw = list(pv_me['towers'])
    out += tw + [float(tw[0] > 0) + float(tw[1] > 0), float(tw[3] > 0) + float(tw[4] > 0)]
    reg = min(tick, REGULATION)
    out += [reg/REGULATION, max(0., reg - DOUBLE)/(REGULATION-DOUBLE), max(0., tick - REGULATION)/OVERTIME,
            float(tick >= REGULATION)]
    val = np.zeros(8); bld = [0., 0.]; win = [0., 0.]; cnt = [0., 0.]
    for b in pv_me['bodies']:
        if b['crown']:
            continue
        o = 1 if b['enemy'] else 0
        v = b['cost']*max(0., min(1., b['hp']/max(b['maximum'], 1.)))
        lane = 0 if b['x'] < 9. else 1
        zone = 0 if b['y'] < HALF else 1
        val[o*4 + lane*2 + zone] += v
        if b['building']:
            bld[o] += v
        elif b['only_buildings']:
            win[o] += v
        cnt[o] += 1
    out += list(val) + bld + win + cnt
    return out


def hand_tokens(pv):
    return list(pv['hand'])


def encode(row_pv, parts0, seat, tick, vocab):
    """(x_me, x_them): base features + multi-hot own hand over `vocab` (token -> index)."""
    xs = []
    for s in (seat, 1-seat):
        base = perspective(row_pv[s], row_pv[1-s], parts0, s, tick)
        hand = np.zeros(len(vocab))
        for t in row_pv[s]['hand']:
            j = vocab.get(t)
            if j is not None:
                hand[j] = 1.
        xs.append(np.concatenate([np.asarray(base, dtype=np.float64), hand]))
    return xs[0], xs[1]
