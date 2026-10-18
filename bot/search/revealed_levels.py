"""Revealed opponent levels for the level-aware planner (LV2 follow-up, arm PLr; default off).

A card's level is public the moment it is played (the level badge on the deploy; the unit's level in the client's
public unit data). RevealedLevels(truth, prior) is the opponent-level callable for bot.search.levelplan.install:
prior(card) (the LV2 dist table) for a card not yet seen, truth[card] once the opponent has played it. In the sim,
truth is the match's true opponent level vector and only cards in the public event stream are revealed; live, call
reveal(card, level) with the badge level read off the play.

bind(search) wraps the search tier's root_fn (installed by levelplan.install -> MatchLevelRoot): before each root it
reads the public enemy card plays from info.events, and when a newly revealed card's level differs from its prior it
drops the root's cached per-seat level config so the next root and its rollouts use the revealed level. At most one
rebuild per opponent card per battle; bind() prewarms the true levels' exports before play (sim: the truth vector),
so a reveal never exports the pool inside a decision. Limits (documented): Mirror copies already on the board keep the
level their root rebuild assigns (body provenance is not public in v5); install_planner's all-11 shortcut (no
level_root) is refused, since a later reveal could not be applied.
"""
from __future__ import annotations


class RevealedLevels:
    def __init__(self, truth, prior):
        self.truth, self.prior = {c: int(v) for c, v in dict(truth).items()}, prior
        self.revealed = {}
        self.log = []                 # (tick, card, level, prior) per reveal, for the row record

    def __call__(self, card):
        return int(self.revealed[card]) if card in self.revealed else int(self.prior(card))

    def reveal(self, card, level, tick=None, root=None):
        if card in self.revealed:
            return False
        before = int(self.prior(card))
        self.revealed[card] = int(level)
        self.log.append((tick, card, int(level), before))
        if root is not None and int(level) != before:
            root._cfg.clear()             # ExactLevelRoot per-seat (config, CutConfig) cache; deltas are keyed by level
            return True
        return False

    def bind(self, search, seat):
        root = getattr(search, 'level_root', None)
        if root is None:
            raise ValueError('PLr needs an installed level root (install_planner skipped all-11 planning)')
        inner = search.root_fn
        saved, self.revealed = self.revealed, dict(self.truth)     # prewarm: export every true level once, now
        try:
            root._cfg.clear()
            root.config(seat)
        finally:
            self.revealed = saved
            root._cfg.clear()
            root.config(seat)

        def root_fn(info, opponent, rng):
            for e in info.events:
                if e.kind == 'card' and e.name in self.truth and e.name not in self.revealed:
                    self.reveal(e.name, self.truth[e.name], e.tick, root)
            return inner(info, opponent, rng)
        search.root_fn = root_fn
