"""Features and a numpy forward for the learned rollout opponent (exploration).

Input = native public_view(seat) of a Rust BattleState (own frame: own king at the bottom) + absolute tick.
Output = (gate logit, logits over the card vocabulary, tile logits for a given card). Training lives in
bot/search/lopp_train.py (torch, same architecture); inference here is numpy only (~0.1 ms per batch row).
"""
from __future__ import annotations

import numpy as np

GX, GY = 9, 16                 # 2x2-tile cells
NG = GX * GY
CH = 6                         # own troop, own building, enemy troop, enemy building (cost x hp share),
                               # enemy building-only troops (cost x hp share), enemy body count
NGLOB = 24
DIM = CH * NG + NGLOB


def featurize(view: dict, tick: int, cost_of: dict) -> tuple[np.ndarray, list[int]]:
    """view: json.loads(native.public_view(state, seat)). Returns (x[DIM] float32, hand tokens[4])."""
    x = np.zeros(DIM, np.float32)
    sums = [0.] * 6
    for b in view['bodies']:
        if b['crown']:
            continue
        c = min(GX - 1, max(0, int(b['x'] / 2)))
        r = min(GY - 1, max(0, int(b['y'] / 2)))
        cell = r * GX + c
        w = b['cost'] * (b['hp'] / b['maximum'] if b['maximum'] > 0 else 1.)
        enemy = bool(b['enemy'])
        x[((2 if enemy else 0) + bool(b['building'])) * NG + cell] += w
        if enemy:
            if b['only_buildings']:
                x[4 * NG + cell] += w
            x[5 * NG + cell] += 1.
            sums[0] += w
            if b['y'] < 16:
                sums[1] += w          # enemy value on my half
        else:
            sums[2] += w
            if b['y'] >= 16:
                sums[3] += w          # my value on the enemy half
    g = CH * NG
    e = float(view['elixir'])
    hand = [int(t) for t in view['hand']]
    x[g + 0] = e / 10
    x[g + 1:g + 7] = view['towers']
    x[g + 7] = tick / 6000
    x[g + 8] = tick >= 2400
    x[g + 9] = tick >= 4800
    for i, t in enumerate(hand[:4]):
        cost = cost_of.get(t, 0.)
        x[g + 10 + i] = cost / 10
        x[g + 14 + i] = cost <= e + 1e-6 and t != 0
    x[g + 18:g + 22] = [s / 10 for s in sums[:4]]
    x[g + 22] = len(view['bodies']) / 30
    x[g + 23] = 1.
    return x, hand


class NumpyOpponent:
    """Forward of lopp_train.Net from an .npz export."""

    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.w = {k: z[k] for k in z.files if not k.startswith('meta_')}
        self.vocab = {int(t): i for i, t in enumerate(z['meta_vocab'])}     # card token -> index (0 = unknown)
        self.cost_of = {int(t): float(c) for t, c in zip(z['meta_vocab'], z['meta_cost'])}
        self.tau = float(z['meta_tau'])                                      # calibrated play threshold (prob)
        self.mu, self.sd = z['meta_mu'], z['meta_sd']

    def trunk(self, X, cards):
        w = self.w
        X = (X - self.mu) / self.sd
        emb = w['emb'][cards].reshape(len(cards), -1)
        h = np.maximum(0, X @ w['W1'] + emb @ w['W1c'] + w['b1'])
        h = np.maximum(0, h @ w['W2'] + w['b2'])
        return h if 'W3' not in w else np.maximum(0, h @ w['W3'] + w['b3'])

    def heads(self, h):
        w = self.w
        return h @ w['wg'] + w['bg'], h @ w['Wv'] + w['bv']

    def tiles(self, h, card_idx):
        w = self.w
        t = np.maximum(0, h @ w['Wt'] + w['tem'][card_idx] + w['bt'])
        return t @ w['Wo'] + w['bo']
