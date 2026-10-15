"""The RL training distribution of a student, shared bit for bit by the CPU actor and the GPU learner.

Deployed decode (bot/exit/student.py, s1 CachedPolicy): play iff p = P(play) >= tau, then the top-1 legal
(card, tile) under the T=1 heads. The training (explore) policy is stochastic around exactly that rule:
- gate: play with q = sigmoid((logit p - logit tau0) / kappa); its mode is the deployed gate;
- card ~ softmax(card / T), tile ~ softmax(tile_card / T) (deploy = T=1 argmax).
Only polls with at least one legal play are decisions; everything else is a forced WAIT.
"""
from __future__ import annotations

import math

import torch
from torch.nn import functional as F

WAIT = 2304
LOGIT_CLAMP = 30.


def masked_log_softmax(logits, mask):
    # identical to exit_r3.network.masked_log_softmax (FP32, empty supports -> all -1e9)
    z = logits.float().masked_fill(~mask, -1e9)
    return F.log_softmax(z, dim=-1).masked_fill(~mask, -1e9)


def forward(model, b):
    return model(b, torch.empty(0, dtype=torch.long, device=b['ids'].device))


def gate_logit(raw, tau, kappa):
    """z such that q = sigmoid(z); also returns p = P(play) (deployed gate input)."""
    g = masked_log_softmax(raw['gate'], raw['gate_mask'])
    lp_play = g[:, 1]
    lp_not = torch.logsumexp(torch.stack((g[:, 0], g[:, 2]), -1), -1)
    ell = (lp_play - lp_not).clamp(-LOGIT_CLAMP, LOGIT_CLAMP)
    return (ell - math.log(tau / (1 - tau))) / kappa, lp_play.exp()


def explore(raw, tau, kappa, temp):
    z, p = gate_logit(raw, tau, kappa)
    card = masked_log_softmax(raw['card'] / temp, raw['card_mask'])
    tile = masked_log_softmax(raw['tile'] / temp, raw['tile_mask'])
    return dict(z=z, p=p, card=card, tile=tile, card_mask=raw['card_mask'], tile_mask=raw['tile_mask'])


def log_prob(d, play, slot, tile):
    """log pi(action) for rows of a batch; play bool [B], slot/tile long [B] (ignored where not play)."""
    rows = torch.arange(len(play), device=play.device)
    s, t = slot.clamp(0, 3), tile.clamp(0, 575)
    lp_play = F.logsigmoid(d['z']) + d['card'][rows, s] + d['tile'][rows, s, t]
    return torch.where(play, lp_play, F.logsigmoid(-d['z']))


def kl(d, r):
    """Analytic KL(d || r) of the whole explore distribution, per row."""
    qd = torch.sigmoid(d['z'])
    kg = qd * (F.logsigmoid(d['z']) - F.logsigmoid(r['z'])) + (1 - qd) * (F.logsigmoid(-d['z']) - F.logsigmoid(-r['z']))
    pc = d['card'].exp()
    kc = torch.where(d['card_mask'], pc * (d['card'] - r['card']), 0.).sum(-1)
    pt = d['tile'].exp()
    kt = torch.where(d['tile_mask'], pt * (d['tile'] - r['tile']), 0.).sum(-1)       # [B, 4]
    kt = torch.where(d['card_mask'], pc * kt, 0.).sum(-1)
    return kg + qd * (kc + kt)


def entropy(d):
    qd = torch.sigmoid(d['z'])
    hg = -(qd * F.logsigmoid(d['z']) + (1 - qd) * F.logsigmoid(-d['z']))
    pc = d['card'].exp()
    hc = -torch.where(d['card_mask'], pc * d['card'], 0.).sum(-1)
    ht = -torch.where(d['tile_mask'], d['tile'].exp() * d['tile'], 0.).sum(-1)
    ht = torch.where(d['card_mask'], pc * ht, 0.).sum(-1)
    return hg + qd * (hc + ht)
