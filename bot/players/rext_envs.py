"""RoyaleGym environment for training an EXTERNAL opponent with RoyaleLearn (rext-rlppo).

Torch-free and free of any clasher import: RoyaleLearn's rollout workers import this module by
its dotted path (`bot.players.rext_envs.build_env`) inside the separate learnvenv
(/mpac/sdicks02/repos/clasher-bot-rsim/learnvenv on 127x08), never our main venv.

What it builds is RoyaleGym's quickstart environment with our match conditions:
- decks: the five X4S human decks (Runtime().x4s_decks(), RoyaleSim names), seat decks drawn
  independently and uniformly each battle (all 25 pairings), each shuffled by the engine;
- card and tower level 11 (King 4824, Princess 3052), as our harness's Battle(level=11);
- rules client_arms('15.535.29') (rust_engine.client_overrides), as HEADLINE-v1;
- a symmetric 27-tick command delay inside the engine (RoyaleSim set_command_delay_ticks(27, 27));
  our match loop instead queues commands harness-side (CommandQueue(27, 1)), see rext_policy.py;
- RoyaleGym defaults otherwise: SpatialObsBuilder (fair observation, no Reveal),
  TileActionParser (no-op + 4 slots x 18 x 32), decision every 500 ms (10 ticks), and the
  quickstart reward (win/loss 1.0, crowns 0.2, tower HP 0.1).
"""
from __future__ import annotations

# Runtime().x4s_decks() (bot/players/runtime.py:100), mapped with royalesim_adapter.royalesim_card.
X4S_DECKS = (
    ('Cannon', 'Fireball', 'HogRider', 'IceGolemite', 'IceSpirits', 'Log', 'Musketeer', 'Skeletons'),   # bridge
    ('Archer', 'ElectroSpirit', 'Fireball', 'Knight', 'Log', 'Skeletons', 'Tesla', 'Xbow'),             # siege
    ('Arrows', 'FireSpirits', 'Giant', 'HogRider', 'Knight', 'Minions', 'Valkyrie', 'Wizard'),          # beatdown
    ('BlowdartGoblin', 'Cannon', 'GoblinBarrel', 'IceSpirits', 'Princess', 'SkeletonArmy', 'Valkyrie',
     'Wallbreakers'),                                                                                   # bait
    ('DarkPrince', 'ElectroSpirit', 'Log', 'Miner', 'Rocket', 'RoyalDelivery', 'Skeletons', 'Tesla'),   # chip
)
LEVEL = 11
CLIENT = '15.535.29'
COMMAND_DELAY = 27
DECISION_MS = 500

try:
    from royalegym.state_mutator import StateMutator as _Base
except ImportError:          # imported from our main venv (rext_policy reads the constants only)
    _Base = object


def _patch_snapshot_index():
    """Workaround for royalelearn 0.5.18: an evaluation worker reads the snapshot index once
    when it starts, so a gate against a snapshot admitted after that fails with
    KeyError("no snapshot 'snap:vN'") and kills the run (rlppo-r3, 2026-10-14 ~05:30Z). On a
    miss, re-read the index from disk and look again. Every rollout/eval worker imports this
    module (it is the run's env_fn), so the patch reaches the processes that need it."""
    try:
        from royalelearn.ladder.snapshots import DiskSnapshotStore
    except ImportError:
        return
    if getattr(DiskSnapshotStore, '_rext_patched', False):
        return
    original = DiskSnapshotStore._folder

    def _folder(self, snapshot_id):
        try:
            return original(self, snapshot_id)
        except KeyError:
            self._read_index()
            return original(self, snapshot_id)

    DiskSnapshotStore._folder = _folder
    DiskSnapshotStore._rext_patched = True


_patch_snapshot_index()


class X4SStateMutator(_Base):
    """Each battle: seat decks drawn independently from the five X4S decks, level 11 everywhere."""

    def __init__(self, level: int = LEVEL) -> None:
        self.level = int(level)

    def config(self):
        return {'level': self.level}

    def build(self, rng, cards):
        from royalegym import MatchSetup, deck_ids
        blue, red = (X4S_DECKS[int(rng.integers(len(X4S_DECKS)))] for _ in range(2))
        return MatchSetup(decks=[deck_ids(list(blue), cards), deck_ids(list(red), cards)],
                          levels=[[self.level]*8, [self.level]*8], tower_levels=[self.level]*2)


def make_engine(delay: int = COMMAND_DELAY):
    from royalegym import RustEngine
    from royalegym.rust_engine import client_overrides
    return RustEngine(calibration_overrides=client_overrides(CLIENT), command_delay_ticks=(delay, delay))


def build_env():
    from royalegym import (ClashParallelEnv, CombinedReward, CrownReward, GameOverCondition,
                           SpatialObsBuilder, TileActionParser, TowerHPReward, WinLossReward)
    return ClashParallelEnv(
        make_engine(),
        state_mutator=X4SStateMutator(),
        obs_builder=SpatialObsBuilder(),
        action_parser=TileActionParser(),
        reward_fn=CombinedReward([(WinLossReward(), 1.0), (CrownReward(), 0.2), (TowerHPReward(), 0.1)]),
        termination_cond=GameOverCondition(),
        truncation_cond=None,
        decision_ms=DECISION_MS,
    )
