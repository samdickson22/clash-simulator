"""Level-aware planning for our K4L search tier (LV2; BOT LEAD 2026-10-17). Default OFF: nothing calls this unless a
driver asks, and without it the planner keeps the core's level-11 rollouts (levels=None behaviour).

    from bot.search.levelplan import install, dist_levels
    status = install(rt, player, seat, decks, own_levels, opp_levels, towers)

- player: our seat's player, possibly wrapped (Observed/Recorder .rec.inner, Interruptible .live, LivePlayer .search);
  the K4L search tier (a MultiSearchPlayer subclass, class attribute root_fn) is found through instance attributes.
- decks: [seat0 deck, seat1 deck] (engine card names, the match's decks).
- own_levels: {card: level} for our deck (missing cards -> 11).
- opp_levels: {card: level} for the opponent's deck (oracle: the true vector; cards the belief samples outside it plan
  at its common level, else 11), OR a callable card -> level used for EVERY card the planner meets (dist: no deck
  knowledge, so a sampled hidden card's level never reveals whether it is in the true deck).
- towers: [seat0 tower level, seat1 tower level] (King = princess level).
The planner then builds every root at these levels (bot.levels.match.install_planner -> MatchLevelRoot: own cards at
own_levels, the opponent's at opp_levels, both tower levels, warm per-level export caches before the first decision)
and scores leaves with the matching tower curve (bot.levels.root.leaf_native). Returns install_planner's status
('exact', or 'l11 (...)' when it cannot apply, e.g. a p<P> worker pool).

Live interface (for the LIVE LEAD; bot/live is not changed here): call install(...) once per battle, after the live
player is built and before LivePlayer.start, with
  own_levels = our collection's level per deck card (collection file),
  opp_levels = the opponent's per-card estimate (dist_levels(table, opp_deck) or level badges once perceived),
  towers     = [ours, theirs] in seat order (ours from the collection's King level; theirs 9 or read from tower HP).
With a callable opp_levels (e.g. lambda c: dist_level(table, c)) the opponent's deck need not be known: every card is
planned at its table level, which is what live v1 can do without new perception.

dist_levels(table, deck): the empirical opponent-level table (bot/fullpool/lv2_table.py): per card the median logged
level (rounded half up) when the card has >= min_n observations, else our CURRENT level of that card (if in our deck)
+ the median offset, else our deck's median level + the median offset.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


def find_search(player):
    p = player
    for _ in range(8):
        if hasattr(type(p), 'root_fn'):
            return p
        d = vars(p)
        nxt = d.get('rec') or d.get('live') or d.get('search') or d.get('inner')
        if nxt is None:
            break
        p = getattr(nxt, 'inner', nxt) if 'rec' in d else nxt
    raise ValueError(f'no root_fn search tier under {type(player).__name__}')


class AnyCard(dict):
    """The opponent's deck levels as a dict (resolve/tag/trivial read it), whose get() answers for ANY card through
    fn: bot.levels.match.match_root looks levels up with opp.get(card, default)."""

    def __init__(self, items, fn):
        super().__init__(items)
        self.fn = fn

    def get(self, card, default=None):
        return int(self.fn(card))


def install(rt, player, seat, decks, own_levels, opp_levels, towers):
    from bot.levels.match import install_planner, resolve
    cards = [None, None]
    cards[seat] = {c: int(own_levels.get(c, 11)) for c in decks[seat]}
    fn = opp_levels if callable(opp_levels) else None
    cards[1 - seat] = {c: int(fn(c) if fn else opp_levels.get(c, 11)) for c in decks[1 - seat]}
    spec = resolve(dict(cards={0: cards[0], 1: cards[1]}, towers={0: int(towers[0]), 1: int(towers[1])}, planner='exact'),
                   [list(d) for d in decks])
    if fn is not None:
        spec['cards'][1 - seat] = AnyCard(spec['cards'][1 - seat], fn)
    return install_planner(rt, find_search(player), seat, spec)


def load_table(path):
    return json.loads(Path(path).read_text())


def _round(x):
    return int(math.floor(float(x) + .5))          # half up: a 7.5 median plans at 8


def dist_level(table, c, own=None):
    """own: our current {card: level} (the account, not the table's logged levels) for the in-deck fallback."""
    own = own if own is not None else table['own']
    e = table['cards'].get(c)
    if e is not None and e['n'] >= table['min_n']:
        return _round(e['median'])
    if c in own:
        return _round(own[c] + table['median_offset'])
    return _round(table['own_median'] + table['median_offset'])


def dist_levels(table, deck, own=None):
    return {c: dist_level(table, c, own) for c in deck}
