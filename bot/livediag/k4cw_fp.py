"""LIVE-K4CW-r16-fp: the L16 strong opponent LIVE-K4CW-r16 with its two C56-only components replaced (live-diag).

LIVE-K4CW-r16 as fullpool_eval.players builds it (bot-deckopt2/fullpool_eval.py:154-158) already runs on the full-scope
runtime of the caller (live16402b-r3: R.config/meta/costs/templates and the scripted rollout bots R.bots widened to the
full pool, bot/cards/scope.py) with the extended v1 / R3a nets (BOT_FULLPOOL_POLICIES -> rt.POLICY / rt.STUDENT, so its
R3a proposer and poller are the -fp nets). Its rollouts use the native scripted opponent (symmetric_opponent), not a
learned rollout net, so there is no K4CW counterpart of mk1a1's k1a1.npz to swap. What stays C56:
- belief prior: bot/live/player.py:94 `PublicPlanner(R, rt.PRIOR, seed)` (the C56 human catalog, 2925 decks) and
  :292-293 LiveBelief completing rebuilds from rt.PRIOR; rt.belief_prior is never read (bot/search/players.py:131
  reads it via planner_belief, _WallMulti.start does not);
- fast tier: fullpool_eval.py:157 `fast_spec=OLD_FAST` = it5s2 (a C56 student, not extended).
-fp = the same LivePlayer(tier='search', wall_ms=None, threads=1, r3a=16, cutoff_default='it5s2') on the caller's
full-pool runtime (rt.belief_prior = fullpool_eval.BELIEF) with the belief re-initialised on planner_belief's prior
(FullPoolBelief: the full-pool sampler's public card-frequency decks, open world; fair information) and the full-pool
fast tier f1a2 (fullpool_eval.FAST, mk1a1's). Nothing in bot/live/* or the frozen runtime is modified.
"""
from __future__ import annotations

NAME = 'LIVE-K4CW-r16-fp'


def make_k4cw_fp(rt, fast_spec, name=NAME):
    from bot.live.player import LivePlayer

    class K4CWFullPool(LivePlayer):
        def start(self, ctx):
            LivePlayer.start(self, ctx)              # LiveBelief over rt.PRIOR, as K4CW-r16
            from belief import Belief
            from bot.fullpool.belief import planner_belief
            prior, cls = planner_belief(self.rt, Belief)
            assert cls.__name__ == 'FullPoolBelief', (cls, getattr(self.rt, 'belief_prior', None))
            b = self.search.p.belief
            frozen = next(c for c in type(b).__mro__ if c.__name__ == 'DerivedPublicState')
            frozen.__init__(b, prior, b.costs)        # = PublicPlanner(R, prior, seed).belief (fair_player.py:180)
            b.__class__ = cls

    return K4CWFullPool(rt, tier='search', wall_ms=None, threads=1, r3a=16, fast_spec=fast_spec,
                        cutoff_default='it5s2', name=name)
