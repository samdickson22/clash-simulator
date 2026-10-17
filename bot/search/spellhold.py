"""Spell-hold option value for K4L-R (token `sh<N>`, lambda = N/1000; SC1, cycle-model owner; exploration tier).

A spell in hand is worth an option value: it can answer an enemy unit later. Casting it forfeits that value, while a
wait keeps it. So every root play key a < WAIT whose card is a spell pays
    LAMBDA * cost(card),
whatever it targets. A cast on real units still wins when its rollout gain exceeds the hold value. "Spell" = a card
with no Troop/Building body in the runtime config (R.config; the same data rule as bot/cyclemodel), so there are no
per-card or target rules. Fireball (4) therefore holds twice Zap's (2) value; that is by design, not tuned.

The term composes into core.reserve (read by reserve.apply in lopp.reduce_learned / lopp_fast.reduce_fast), on top of
`res`/`lc<N>` when they're installed, and is idempotent across the two install sites (LearnedOppPlayer.start and
_FastMixin._install_fast, which re-installs `res`). Without the token nothing here runs and K4L-R is unchanged.
"""
from __future__ import annotations

WAIT = 2304


def spell_cards(R):
    from bot.cyclemodel.belief import bodyless_cards
    return bodyless_cards(R.config)


def install(rt, core, lam):
    """core.reserve <- (previous penalty, if any) + lam * cost(spell) for spell plays. Idempotent."""
    prev = getattr(core, 'reserve', None)
    if prev is not None and getattr(prev, '_spellhold', None) == lam:
        return
    R = rt.R
    spells, costs, builder = spell_cards(R), R.costs, R.builder

    def penalty(a, elixir):
        p = prev(a, elixir) if prev is not None else 0.
        if a >= WAIT:
            return p
        tok = int(list(core.info.packet.observation.hand_ids)[a // 576])
        card = builder.card_name_for_token_id(tok) if tok > 0 else None
        if card in spells and card in costs:
            p += lam * float(costs[card])
        return p
    penalty._spellhold = lam
    core.reserve = penalty
