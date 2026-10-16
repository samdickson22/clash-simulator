"""External (RoyaleGym-ecosystem) trained policies as bot.players Players: rext-*.

RextPolicyPlayer(model_dir, greedy=False)
    A RoyaleLearn checkpoint (Learner.save folder, a run's save_dir or one checkpoint folder),
    loaded with RoyaleLearn's own loader (royalelearn.learner.Bot: build_actor + its weights,
    EvalActors.policy for the decode), playing inside OUR RoyaleSim match loop
    (royalesim_match.play_match), RoyaleSim-only like RoyaleGymPlayer.

What it sees: exactly the observation it was trained on, built by RoyaleGym's own code from the
live RoyaleSim battle of the match: a RoyaleGym RustEngine whose battle object is the match's
(`royalesim.Battle`, the same compiled class RoyaleGym wraps), SpatialObsBuilder (fair default,
no Reveal) and TileActionParser's action mask (RoyaleSim check_deploy for the seat's own hand
slots). The builder's MatchMemory counts the enemy's elixir and cycle from plays it sees.
Information audit (see reports/bot/external-opponents/NOTES.md):
  - enemy units that are underground (tunnelling Miner) or invisible are REMOVED from the state
    before it is built (our fair-information rule; v5 hidden_from_enemy; RoyaleGym's builder
    reads no status flags and would show them);
  - MatchMemory notices an enemy play as that enemy hand slot changing between two observed
    states. In our loop RoyaleSim's own delay is 0, so the slot changes exactly when the play
    executes and the card appears on the board: the same public event, nothing earlier;
  - it reads the enemy elixir bar at the first observation (6.0, public) and afterwards only
    to set a match-long `exact` flag (False if its count ever disagrees); with eight distinct
    cards and no ability presses (X4S decks) the count is exact, so the flag carries nothing.
  - the enemy deck list in the state is the env's convention (RustEngine._setup_cards); the
    fair builder never reads it (only Reveal.enemy_deck would).
Command lag: the policy decides every 10 ticks (its decision_ms 500) when its channel is free;
its tile action becomes our action id and goes through our CommandQueue(27, 1) like every seat.
It was trained with RoyaleSim's own symmetric 27-tick command delay (rext_envs.py), so it plays
with the delay it learned, though our queue holds one command at a time where the engine's held
several. Its memory is built with command_delay (0, 0), the delay of the engine it reads.

Imports royalegym/royalelearn from a no-deps vendor dir (REXT_VENDOR, default below) appended to
sys.path, so our venv is not modified (installing royalegym there would upgrade gymnasium).
"""
from __future__ import annotations

import functools
import hashlib
import os
from pathlib import Path
import sys

from .base import Decision, MatchContext, PublicView, WAIT

VENDOR = '/mpac/sdicks02/repos/clasher-bot-rsim/rext-vendor'           # royalegym 0.1.24, royalelearn 0.5.18, pettingzoo 1.27.0
MODELS = '/mpac/sdicks02/repos/clasher-bot-rsim/rext-models'
SEED_OFFSET = 271828
DECISION_TICKS = 10


def _vendor():
    path = os.environ.get('REXT_VENDOR', VENDOR)
    if path not in sys.path:
        sys.path.append(path)          # appended: our venv's numpy/torch/gymnasium/msgspec win


@functools.lru_cache(maxsize=None)
def load_actor(model_dir: str):
    """(actor, spec, net, sha256 of the weights file); RoyaleLearn's Bot.load without the Bot."""
    _vendor()
    import msgspec
    import torch
    from royalelearn import config as cfg
    from royalelearn.api.rollout import EnvSpec
    from royalelearn.ladder.snapshots import _decode_tensors
    from royalelearn.learn.nets import build_actor
    from royalelearn.learner import _bot_files
    record_file, weights = _bot_files(Path(model_dir))
    record = msgspec.json.decode(record_file.read_bytes())
    spec = msgspec.convert(record['env_spec'], EnvSpec)
    net = msgspec.convert(record['net'], cfg.NetConfig)
    if str(getattr(net, 'device', 'cpu')) != 'cpu':
        net = msgspec.structs.replace(net, device='cpu')
    actor = build_actor(spec, net)
    blob = weights.read_bytes()
    state = _decode_tensors(blob, 'cpu')
    if state and all(k.startswith('actor.') for k in state):
        state = {k.removeprefix('actor.'): v for k, v in state.items()}
    actor.load_state_dict(state)
    actor.eval()
    torch.set_num_threads(1)
    return actor, spec, net, hashlib.sha256(blob).hexdigest()


@functools.lru_cache(maxsize=None)
def _engine_template():
    """A RoyaleGym RustEngine under the 15.535.29 arms; its battle is swapped per match."""
    _vendor()
    from royalegym import RustEngine
    from royalegym.rust_engine import client_overrides
    return RustEngine, client_overrides


class SlotRemapBattle:
    """The match battle as RoyaleGym's RustEngine expects it: only state_json differs.

    `slot_of_k` (which protocol TowerSlot engine tower k reports as) changes nothing in the
    core but the state_json text (RoyaleSim py.rs state_json_text_with: the players'
    tower_hp / tower_max_hp order and the towers' tower_slot column). Our match battle uses
    [[0,1,2],[0,1,2]] (royalesim_vocab.rsim_battle); RoyaleGym derives [[0,1,2],[0,2,1]] from
    the arena. This rewrites the text from ours to RoyaleGym's; everything else is the battle.
    """
    OURS = [[0, 1, 2], [0, 1, 2]]

    def __init__(self, battle, slot_of_k):
        self._b = battle
        # protocol slot under ours -> under RoyaleGym's, per team
        self.perm = [{self.OURS[t][k]: slot_of_k[t][k] for k in range(3)} for t in (0, 1)]
        self.identity = all(p[i] == i for p in self.perm for i in range(3))

    def __getattr__(self, name):
        return getattr(self._b, name)

    def state_json(self):
        import json
        text = self._b.state_json()
        if self.identity:
            return text
        s = json.loads(text)
        for t, player in enumerate(s['players']):
            for key in ('tower_hp', 'tower_max_hp'):
                old = player[key]
                new = list(old)
                for slot, value in enumerate(old):
                    new[self.perm[t][slot]] = value
                player[key] = new
        for row in s['entities']:
            if row[3] == -1 and row[4] >= 0:           # crown tower: card_id -1, tower_slot column 4
                row[4] = self.perm[row[1]][row[4]]
        return json.dumps(s)


def resolve_model(name):
    """'rlppo' -> MODELS/rlppo (a Learner.save folder), or an absolute path."""
    return name if os.path.isabs(name) else os.path.join(os.environ.get('REXT_MODELS', MODELS), name)


class RextPolicyPlayer:
    deadline_seconds = None
    evaluation_clients = ('15.535.29',)  # Harnesses may explicitly opt in to balance transfer.

    def __init__(self, model='rlppo', *, greedy=False, decision_ticks=DECISION_TICKS):
        self.model_dir = resolve_model(model)
        self.greedy, self.decision_ticks = greedy, decision_ticks
        self.name = f"rext-{os.path.basename(self.model_dir.rstrip('/'))}{'-greedy' if greedy else ''}"
        self.match = None

    def bind_rsim(self, match):
        self.match = match

    def start(self, ctx: MatchContext):
        if self.match is None:
            raise RuntimeError('RextPolicyPlayer runs only inside royalesim_match (reads the RoyaleSim battle)')
        if self.match.client not in self.evaluation_clients:
            raise ValueError(f'rext policies were trained on 15.535.29 rules, not {self.match.client}')
        import numpy as np
        _vendor()
        from royalegym import SpatialObsBuilder, TileActionParser
        from royalegym.protocol import STATUS_INVISIBLE, STATUS_UNDERGROUND, status_of
        from royalelearn.ladder.actors import EvalActors
        from .royalesim_adapter import royalesim_card
        self.actor, spec, net, self.weights_sha256 = load_actor(self.model_dir)
        rust_engine, client_overrides = _engine_template()
        m = self.match
        engine = rust_engine(calibration_overrides=client_overrides('15.535.29'))
        if engine.card_level != 11:
            raise ValueError(f'engine level {engine.card_level} is not the match battle\'s 11')
        engine._battle = SlotRemapBattle(m.b, engine.slot_of_k)   # the match's own battle: same class, same arms
        engine._reset_called = True
        engine._setup_cards = [([m.ids[royalesim_card(c)] for c in m.decks[t]], [0]*8) for t in (0, 1)]
        self.engine = engine
        self.parser = TileActionParser()
        self.parser.bind(engine)
        self.builder = SpatialObsBuilder()
        self.builder.bind(engine, self.parser)
        self.builder.command_delay = (0, 0)          # RoyaleSim's own delay in our loop (lag is harness-side)
        self.hidden, self.status_of = STATUS_UNDERGROUND | STATUS_INVISIBLE, status_of
        self.seat = ctx.seat
        self.builder.reset(self.state())
        mode = 'argmax' if self.greedy else 'stochastic'
        self.play = EvalActors(spec, net, None, release_mode=mode).policy(self.actor)
        self.rng = np.random.default_rng(ctx.seed + SEED_OFFSET + ctx.seat)
        self.stats = dict(decisions=0, plays=0, noop=0, illegal=0, frame_mismatch=0, hidden_dropped=0)

    def state(self):
        """RoyaleGym BattleState of the live battle, enemy units hidden from this seat removed."""
        import msgspec
        state = self.engine.state()
        keep = [e for e in state.entities if e.team == self.seat or not ((self.status_of(e) or 0) & self.hidden)]
        if len(keep) != len(state.entities):
            self.stats['hidden_dropped'] += len(state.entities) - len(keep)
            state = msgspec.structs.replace(state, entities=keep)
        return state

    def act(self, view: PublicView) -> Decision:
        if view.tick % self.decision_ticks:
            return Decision(WAIT, stats=None)
        state = self.state()
        mask = self.parser.action_mask(state, self.seat)
        obs = self.builder.build(state, self.seat, mask)   # every decision tick: keeps its memory moving
        if not view.can_act:
            return Decision(WAIT, stats=None)
        action = int(self.play(obs, float(self.rng.random()), self.rng))
        self.stats['decisions'] += 1
        if action == 0:
            self.stats['noop'] += 1
            return Decision(WAIT, stats={})
        if not mask[action]:
            self.stats['illegal'] += 1
            return Decision(WAIT, stats={})
        ours = self.to_ours(self.parser.parse(action, state, self.seat))
        if ours is None:
            return Decision(WAIT, stats={})
        self.stats['plays'] += 1
        return Decision(ours, stats={})

    def to_ours(self, cmd):
        """RoyaleGym DeployCommand (engine frame, subtiles) -> our own-frame action id; exact or None."""
        from .royalesim_adapter import action_to_command, TILE_SUBTILES, BOARD_W, BOARD_H
        cx, cy = cmd.x // TILE_SUBTILES, cmd.y // TILE_SUBTILES
        if self.seat == 1:
            cx, cy = BOARD_W-1-cx, BOARD_H-1-cy
        ours = cmd.hand_slot*576 + cy*BOARD_W + cx
        if action_to_command(ours, self.seat) != (cmd.team, cmd.hand_slot, cmd.x, cmd.y):
            self.stats['frame_mismatch'] += 1
            return None
        return ours

    def close(self):
        self.engine = None                       # drop the battle reference
