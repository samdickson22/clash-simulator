"""Elixir-reserve term for K4L-R (token `res`; bot lead live-diag, exploration tier).

After the timed-wait bonus, every play key a < WAIT scored while NO enemy troop/building is on our half (contract-v5
entity rows of the root packet: enemy flag, troop/building kind, y < 16 tiles, towers excluded) pays
    LAMBDA * max(0, R - (elixir - cost(a))) / R,
R = the cheapest cost among our deck's ground-hitting troops/buildings (R.config: can_ground, class Troop/Building;
3 for the live e16 deck), elixir = the root's own elixir, cost from R.costs. Waits and defensive plays are unchanged.
Without the token nothing here runs and K4L-R is unchanged. Evidence: reports/bot/live-diag/RESULTS.md (sim twin
LD-K4L-R-gs-rw-res, bot/livediag/variants.py, is this term).
"""
from __future__ import annotations

WAIT = 2304
LAMBDA = 0.015


def ground_reserve(R, deck):
    costs = []
    for card in deck:
        e = R.config['cards'].get(card) or {}
        units = e.get('units') or []
        st = units[0][0].get('stats', {}) if units and units[0] else {}
        if st.get('can_ground') and units[0][0].get('class') in ('Troop', 'Building'):
            costs.append(float(e['cost']))
    return min(costs) if costs else 3.


def enemy_on_our_half(rt, packet):
    obs, names = packet.observation, rt.R.builder.token_names
    for i in [int(j) for j in obs.entity_mask.nonzero()[0]]:
        f, tok = obs.entity_features[i], int(obs.entity_ids[i])
        if f[3] > .5 and (f[4] > .5 or f[5] > .5) and f[1] * 32 < 16 and \
                not (0 <= tok < len(names) and names[tok] in ('Tower', 'KingTower')):
            return True
    return False


def install(rt, core, deck, lam=LAMBDA):
    """core.reserve = penalty(a, elixir) for this match (read by lopp.reduce_learned / lopp_fast.reduce_fast)."""
    R = rt.R
    reserve, costs, builder = ground_reserve(R, deck), R.costs, R.builder

    def penalty(a, elixir):
        if a >= WAIT or enemy_on_our_half(rt, core.info.packet):
            return 0.
        tok = int(list(core.info.packet.observation.hand_ids)[a // 576])
        card = builder.card_name_for_token_id(tok) if tok > 0 else None
        cost = float(costs[card]) if card in costs else 0.
        return lam * max(0., reserve - (elixir - cost)) / reserve
    core.reserve = penalty


def apply(core, scores, elixir):
    pen = getattr(core, 'reserve', None)
    if pen is not None:
        for a in scores:
            scores[a] -= pen(a, elixir)
