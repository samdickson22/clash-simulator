"""Level profiles for the level-aware search pilot (exploration; reports/bot/levels/DESIGN.md).

A profile is the TRUE game's levels (both seats, every deck card, towers) or a planner's ESTIMATE of them. Levels are
the unified card levels of the current client (a rare starts at 3, an epic at 6, a legendary at 9; a level-L card of
any rarity has the level-L stats), the same convention as RoyaleSim's reset(levels=...) and the Python engine's
PlayerState.card_levels.

Sources (2026-10-16):
- OWN: the live account (reports/live/loop/collection.json + ACCOUNT-LOG.md through 08:30Z): Archers 7, Minions 5,
  Cannon 6, Musketeer 4, MiniPekka 5, Giant 6, Valkyrie 5, Fireball 5 (+ Skeletons 5, the alternative deck);
  towers 6 (princess 2030 / king 3312 HP read in every live battle since s14).
- OPPONENT PRIOR (population, fair): the battle-log levels shown for opponents at 750-840 trophies, 28 battles
  s18-s26, 78 values, all of common cards: L4 4, L5 49, L6 25. Rares are never shown; the scenario assumes one level
  below the common draw (our own account: commons mean 6.0, rares 5.0), never below the rarity's floor. Opponent
  towers 6 (princess HP at match start: 6 in 48 of 49 battles s18-s27, 7 once).
The opponent prior is a scenario assumption for the true game, never per-match hidden state: planners get
estimate_opponent() (a fixed prior median) and the opponent's tower level, which the client shows at match start.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

OWN_LEVELS = dict(Archers=7, Minions=5, Cannon=6, Musketeer=4, MiniPekka=5, Giant=6, Valkyrie=5, Fireball=5,
                  Skeletons=5, Knight=3, Arrows=1, GoblinCage=5, Tombstone=5, GoblinHut=5, MegaMinion=3)
OWN_TOWER = 6
LIVE_DECK = ('Valkyrie', 'Archers', 'Minions', 'Cannon', 'Fireball', 'Giant', 'MiniPekka', 'Musketeer')

COMMON_PRIOR = ((4, 4), (5, 49), (6, 25))      # (level, count) of shown opponent common levels, 750-840 trophies
OPP_TOWER = 6
FLOOR = dict(common=1, rare=3, epic=6, legendary=9, champion=11)
RARE_OFFSET = dict(common=0, rare=1, epic=1, legendary=1, champion=1)   # scenario: below the common draw


def rarity(rt, card):
    """'common' | 'rare' | 'epic' | 'legendary' | 'champion' from the runtime's card loader."""
    r = rt.R.builder.loader.get_card(card).rarity
    return str(getattr(r, 'name', getattr(r, 'value', r))).lower()


def clamp(card_rarity, level):
    return max(FLOOR.get(card_rarity, 1), min(int(level), 14))


@dataclass(frozen=True)
class Profile:
    """Per seat: {card: level} (cards not listed are level 11) and the crown-tower level."""
    cards: tuple = (dict(), dict())
    towers: tuple = (11, 11)
    note: str = ''

    def level(self, seat, card):
        return int(self.cards[seat].get(card, 11))

    def trivial(self):
        return set(self.towers) == {11} and all(v == 11 for side in self.cards for v in side.values())

    def as_json(self):
        return dict(cards=[dict(sorted(c.items())) for c in self.cards], towers=list(self.towers), note=self.note)


def sample_common(rng):
    levels, weights = zip(*COMMON_PRIOR)
    return rng.choices(levels, weights=weights, k=1)[0]


def sample_opponent(rt, deck, rng: random.Random):
    """TRUE opponent levels for one match: each card independently, common draw minus the rarity offset."""
    out = {}
    for card in deck:
        r = rarity(rt, card)
        out[card] = clamp(r, sample_common(rng) - RARE_OFFSET.get(r, 1))
    return out


def prior_median():
    total, acc = sum(n for _, n in COMMON_PRIOR), 0
    for level, n in COMMON_PRIOR:
        acc += n
        if 2 * acc >= total:
            return level
    raise AssertionError


@dataclass
class OpponentEstimate:
    """The planner's fixed, fair estimate: the prior median per rarity, for every card the opponent may hold."""
    rt: object
    median: int = field(default_factory=prior_median)
    _cache: dict = field(default_factory=dict)

    def __call__(self, card):
        if card not in self._cache:
            r = rarity(self.rt, card)
            self._cache[card] = clamp(r, self.median - RARE_OFFSET.get(r, 1))
        return self._cache[card]


def true_profile(rt, decks, seat, opp_levels, *, own=OWN_LEVELS, own_tower=OWN_TOWER, opp_tower=OPP_TOWER):
    """decks: [deck seat0, deck seat1]; `seat` is ours. Every deck card must have an own level."""
    cards = [None, None]
    cards[seat] = {c: own[c] for c in decks[seat]}
    cards[1 - seat] = {c: opp_levels[c] for c in decks[1 - seat]}
    towers = [None, None]
    towers[seat], towers[1 - seat] = own_tower, opp_tower
    return Profile(tuple(cards), tuple(towers), note='true')
