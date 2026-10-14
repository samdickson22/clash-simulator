"""K4SP<k>: K4S search whose candidate set also contains the proposer's top-k plays.

The frozen K4S seat calls core.candidates(packet, []) -- the student's proposals only reorder the coarse scan
(coarse_order), so the teacher never scores the student's own preferred tiles unless the balanced script or the
16 random samples happen to hit them. K4SP<k> passes the first k proposals (coarse_order, already computed
by SearchPlayer.act from the cached R3a poller just before candidates()) as policy_proposals, which
C56RolloutPlanner.candidates inserts after the scripted ranks and before the random samples. Scorer, budget,
admission and S-default are unchanged. Spec: 'K4SP<k>-b<budget>' (bot.eval.headline make_player).
"""
from __future__ import annotations

from bot.players.search import SearchPlayer


class ProposalSearchPlayer(SearchPlayer):
    def __init__(self, rt, *, k=4, **kw):
        super().__init__(rt, **kw)
        self.k = int(k)
        self.name = self.name.replace('K4S-', f'K4SP{self.k}-', 1)

    def start(self, ctx):
        super().start(ctx)
        core, k = self.p.core, self.k
        original = core.candidates

        def candidates(packet, policy_proposals=()):
            extra = [int(a) for a in tuple(core.coarse_order)[:k]]
            return original(packet, list(policy_proposals) + extra)
        core.candidates = candidates


def from_spec(rt, name):
    k, budget = name[len('K4SP'):].split('-b')
    return ProposalSearchPlayer(rt, k=int(k), mode='budget', budget=int(budget), default='R3a')


def student_search(rt, name):
    """'<K4S-variant>@student:<ckpt>[@thr]': a bot.search K4S variant whose proposer AND cutoff default is the
    given student instead of R3a (e.g. 'K4S-st@student:/path/D.pt'). The student's poller replaces the R3a
    poller one for one (same seed, same V1Policy/CachedPolicy wrapper, its own calibrated threshold), so the
    top-8 proposals, the coarse-scan order and the S-default fallback all come from the student."""
    from bot.search.players import make_search_player
    from bot.players.policy import POLICY_SEED_OFFSET
    from bot.exit.student import parse_spec, load_policy
    base, spec = name.split('@', 1)
    path, thr = parse_spec(spec)
    player = make_search_player(rt, base)
    player.name = name
    original = player.start

    def start(ctx):
        from policy import V1Policy
        from cached_policy import CachedPolicy
        original(ctx)
        cached = CachedPolicy(load_policy(path, thr), thr, None)
        player.cached = cached
        player.poller = V1Policy(cached, rt.R.builder, rt.R.costs, ctx.seat, list(ctx.own_order),
                                 ctx.seed + POLICY_SEED_OFFSET + ctx.seat)
    player.start = start
    return player
