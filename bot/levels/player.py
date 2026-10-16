"""Arms of the level-aware search pilot (exploration; reports/bot/levels/DESIGN.md).

make_arm_player(rt, arm, base=..., view=...) -> a bot.players Player for OUR seat:
- 'A'  : `base` with common simulator eligibility (the standard factory outside this pilot is unchanged):
         roots, rollouts and leaf all assume level 11.
- 'B0' : diagnostic, ROOT-ONLY: bot/live/levels.py LevelRoot (scaled root bodies, card-ladder towers) installed on
         the actual K4L search object; rollouts still deploy level-11 cards.
- 'B'  : level-aware search (bot/levels/root.py + configs.py): exact level stats for root bodies and towers,
         per-seat rollout templates (qualified payload/spell keys), and tower metadata for leaf normalization
         AND scripted crown-spell lethality/Lightning ordering.
`view` is what the planner may know (fair information): own card levels, own tower level, the opponent's tower level
(shown by the client at match start). The opponent's card levels are a fixed prior estimate (profile.OpponentEstimate),
never the true per-match levels. Policy weights/features and the common simulator eligibility are identical in every arm.
"""
from __future__ import annotations

from bot.levels.profile import OpponentEstimate
from bot.levels.root import ExactLevelRoot, leaf_native

BASE = 'K4L-R-gs-rw-fc'
ARMS = ('A', 'B0', 'B')


def make_arm_player(rt, arm, *, base=BASE, view=None, parity_all11=False):
    """view: dict(own_levels={card: level}, own_tower=int, opp_tower=int).

    parity_all11 is a diagnostic-only forced path, validated by the runner against
    the all-11 true profile. It never reads the true opponent profile here.
    """
    from bot.eval.headline import make_player
    from bot.levels.scope import install
    from bot.levels.placement import install_runtime, install_player
    if arm not in ARMS:
        raise ValueError(f'arm {arm!r} not in {ARMS}')
    install(rt)     # Same ordered supported-card prior for every experimental arm.
    install_runtime(rt)  # Common eligibility, proven against this installed simulator.
    player = make_player(rt, base)
    if arm == 'A':
        return install_player(player, kind='search')
    view = dict(view)
    own, own_tower, opp_tower = dict(view['own_levels']), int(view['own_tower']), int(view['opp_tower'])
    if parity_all11:
        if arm != 'B' or (own_tower, opp_tower) != (11, 11) or any(int(v) != 11 for v in own.values()):
            raise ValueError('parity_all11 requires arm B and an all-11 planner view')
        estimate = lambda card: 11
    else:
        estimate = OpponentEstimate(rt)
    if arm == 'B0':
        from bot.live.levels import LevelRoot, Levels
        producers = ExactLevelRoot(rt, own, estimate, own_tower, opp_tower).producers()
        own_bodies = {body: own[c] for body, cards in producers.items() for c in cards if c in own}
        player.root_fn = LevelRoot(rt.R, Levels(own=11, opp=estimate.median, own_tower=own_tower, opp_tower=opp_tower,
                                                own_bodies=own_bodies)).root
        player.level_root = player.root_fn.__self__
        return install_player(player, kind='search')
    root = ExactLevelRoot(rt, own, estimate, own_tower, opp_tower,
                          lc=getattr(rt, '_level_configs', None), force=parity_all11 or bool(view.get('force')))
    player.root_fn, player.level_root = root.root, root
    native = leaf_native(rt, own_tower, opp_tower)
    start = player.start

    def start_with_leaf(ctx):
        start(ctx)
        if native is not None:
            # Crown maxima affect leaf AND scripted crown-spell lethality/Lightning ordering.
            player.p.core.native = native
    player.start = start_with_leaf
    return install_player(player, kind='search')
