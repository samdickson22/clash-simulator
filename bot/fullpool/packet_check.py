"""Consistency checks of an Information/packet against the runtime the full-pool bot runs on (exploration).

Use it on Information objects built by the LIVE translator (full-pool mode) and on Information the sim builds from
the true engine state (fair_player.observe). Both must speak the runtime's token space: contract-v5 token ids from
R.builder (360 tokens over all 122 cards, tokens_sha256 35db1a76…), not a separate vocabulary file.

    from bot.fullpool.packet_check import check_information, reference
    issues = check_information(rt, info)            # [] when consistent
    ref = reference(rt, ['Bomber', 'GoblinCage'])   # expected tokens/costs/templates per card

Checks:
  entity rows: every valid entity token has an R.templates (token, kind) entry, so R.root can rebuild it;
  hand ids:    token_id(name, 'card_action') of own hand names, each > 1 (known);
  events:      every card event name is in R.costs (true cost) and has a card_action token > 1 (D1 accepts it);
  history:     opponent_history_ids are card tokens of names in R.costs;
  belief:      the full-pool open-world belief (bot/fullpool/belief.py) can replay the opponent's card events.
CLI (replayed Information pickles, one per file or a list per file):
    CLASHER_BOT_RUNTIME=<live16402b-r3 root> CLASHER_BOT_RUNTIME_PINS=live16402b-r3 PYTHONHASHSEED=0 \
      python -m bot.fullpool.packet_check INFO.pkl [...]
"""
from __future__ import annotations

import json
import pickle
import sys

import numpy as np


def reference(rt, cards):
    """{card: {card_token, card_action_token, cost, template_tokens}} under this runtime."""
    b, R = rt.R.builder, rt.R
    out = {}
    for c in cards:
        out[c] = dict(card_token=int(b.token_id(c)), card_action_token=int(b.token_id(c, namespace='card_action')),
                      cost=R.costs.get(c),
                      in_meta=c in (R.meta['cards'] if isinstance(R.meta, dict) else json.loads(R.meta)['cards']))
    return out


def check_information(rt, info, *, belief_spec='fullpool:11433651:freq=b53b02a1fde4'):
    R, b = rt.R, rt.R.builder
    names = list(b.token_names)
    issues = []
    obs = info.packet.observation
    keys = {t for t, _ in R.templates}
    ids = np.asarray(obs.entity_ids).reshape(-1)
    mask = np.asarray(getattr(obs, 'entity_mask', np.ones_like(ids))).reshape(-1).astype(bool)
    for t in sorted({int(t) for t, m in zip(ids, mask) if m and t > 1}):
        if t not in keys:
            issues.append(f'entity token {t} ({names[t] if t < len(names) else "?"}) has no R.templates entry')
    for n in info.own.get('hand', []):
        if n and int(b.token_id(n, namespace='card_action')) <= 1:
            issues.append(f'own hand card {n!r} has no card_action token')
    for e in info.events:
        if getattr(e, 'kind', None) == 'card':
            if e.name not in R.costs:
                issues.append(f'event card {e.name!r} not in R.costs (runtime scope)')
            if int(b.token_id(e.name, namespace='card_action')) <= 1:
                issues.append(f'event card {e.name!r} has no card_action token')
    for t in sorted({int(t) for t in np.asarray(obs.opponent_history_ids).reshape(-1) if t > 1}):
        n = names[t] if t < len(names) else None
        if b.card_name_for_token_id(t) is None:
            issues.append(f'opponent history token {t} ({n}) is not a playable card token')
    try:
        from bot.fullpool.belief import planner_belief
        from belief import Belief
        rt.belief_prior = belief_spec
        prior, cls = planner_belief(rt, Belief)
        from derived_public_state import DerivedPublicState  # noqa: F401
        bel = cls.__new__(cls)
        next(c for c in cls.__mro__ if c.__name__ == 'DerivedPublicState').__init__(bel, prior, R.costs)
        bel.update(info.tick, [e for e in info.events])
    except Exception as ex:  # reported, not raised
        issues.append(f'full-pool belief replay failed: {ex!r:.200}')
    return issues


def main(paths):
    from bot.players.runtime import Runtime
    rt = Runtime()
    total = bad = 0
    for p in paths:
        obj = pickle.loads(open(p, 'rb').read())
        for info in (obj if isinstance(obj, (list, tuple)) else [obj]):
            total += 1
            issues = check_information(rt, info)
            if issues:
                bad += 1
                print(json.dumps(dict(file=p, tick=info.tick, issues=issues[:10])))
    print(json.dumps(dict(informations=total, with_issues=bad, PASS=bad == 0)))


if __name__ == '__main__':
    main(sys.argv[1:])
