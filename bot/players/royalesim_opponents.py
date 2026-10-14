"""Scripted opponents as bot.players Players.

ScriptedPlayer(rt, style)
    Our PublicScriptedOpponent ('balanced' | 'pressure' | 'defense'), the C56 scripted bot the
    search rollouts use, acting on the v5 public packet every 10 ticks (rollout
    opponent_interval). Engine-agnostic: works in ours.play_match and royalesim_match.

RoyaleGymPlayer(kind)
    RoyaleGym 0.1.24's built-in opponents (royalegym/opponents.py + selfplay.RandomLegalOpponent),
    RoyaleSim-native: 'first-affordable', 'defend', 'push', 'patient', 'random', 'noop'.
    Upstream they read ONLY the action mask ("HOW THEY READ THE BOARD": obs['mask_planes'],
    [slot, y, x] in the acting seat's own frame). Here the mask is RoyaleSim's own
    check_deploy for the acting seat's hand slots on all 576 tile centres, i.e. own hand, own
    elixir and the public board: no hidden opponent information. Decisions every 10 ticks
    (RoyaleGym's default decision_ms=500). Their action 1+slot*576+ty*18+tx (own frame, 0 =
    no-op) is our slot*576+ty*18+tx, so they go through the same CommandQueue lag as every
    seat. RoyaleSim-only (needs the live battle for check_deploy, bound by royalesim_match).

The upstream classes are executed from RoyaleGym's own source file (sha256 recorded), not
reimplemented, without installing royalegym into the shared venv (it would upgrade
gymnasium there). ROYALEGYM_SRC overrides the source directory.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import types

import numpy as np

from .base import Decision, MatchContext, PublicView, WAIT

ROYALEGYM_CANDIDATES = (
    '/mpac/sdicks02/repos/clasher-bot-rsim/.venv/lib/python3.12/site-packages/royalegym',   # 03: royalegym 0.1.24
    '/mpac/sdicks02/tmp/bot-upstream/RoyaleGym/royalegym',                                  # 05: upstream clone
)
OPPONENTS_SHA256 = '5894e8489b935da48eef1031348fc762e3dfd66655797ecc325f144e12ca8fd2'   # royalegym 0.1.24
SEED_OFFSET = 314159


def _royalegym_dir():
    for path in ([os.environ['ROYALEGYM_SRC']] if os.environ.get('ROYALEGYM_SRC') else []) + list(ROYALEGYM_CANDIDATES):
        if (Path(path) / 'opponents.py').exists():
            return Path(path)
    raise FileNotFoundError('RoyaleGym source not found; set ROYALEGYM_SRC')


_UPSTREAM = None


def upstream():
    """(opponents module, RandomLegalOpponent, NoopOpponent, sha256 of opponents.py)."""
    global _UPSTREAM
    if _UPSTREAM is None:
        src = _royalegym_dir()
        text = (src / 'opponents.py').read_bytes()
        digest = hashlib.sha256(text).hexdigest()
        if digest != OPPONENTS_SHA256:
            raise ValueError(f'RoyaleGym opponents.py {digest[:12]} is not the 0.1.24 file')
        pkg = types.ModuleType('royalegym_upstream')
        pkg.__path__ = []
        action = types.ModuleType('royalegym_upstream.action')
        action.NOOP = 0                          # royalegym/action.py:119
        sys.modules.setdefault('royalegym_upstream', pkg)
        sys.modules.setdefault('royalegym_upstream.action', action)
        spec = importlib.util.spec_from_file_location('royalegym_upstream.opponents', src / 'opponents.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules['royalegym_upstream.opponents'] = module
        spec.loader.exec_module(module)
        selfplay = (src / 'selfplay.py').read_text()
        tree = ast.parse(selfplay)
        wanted = [n for n in tree.body if isinstance(n, ast.ClassDef)
                  and n.name in ('RandomLegalOpponent', 'NoopOpponent')]
        from typing import Any
        ns = dict(np=np, NOOP=0, Any=Any, __name__='royalegym_upstream.selfplay')
        exec(compile(ast.Module(wanted, type_ignores=[]), str(src / 'selfplay.py'), 'exec'), ns)
        _UPSTREAM = (module, ns['RandomLegalOpponent'], ns.get('NoopOpponent'), digest)
    return _UPSTREAM


def make_royalegym(kind):
    module, random_legal, noop, _ = upstream()
    return {'first-affordable': module.FirstAffordableOpponent, 'defend': module.DefendOpponent,
            'push': module.PushOpponent, 'patient': lambda: module.PatientOpponent(ready=3),
            'random': lambda: random_legal(0.7), 'noop': noop}[kind]()


class RoyaleGymPlayer:
    deadline_seconds = None

    def __init__(self, kind='patient', *, decision_ticks=10):
        self.kind, self.decision_ticks = kind, decision_ticks
        self.name = f'royalegym-{kind}'
        self.match = None

    def bind_rsim(self, match):
        self.match = match

    def start(self, ctx: MatchContext):
        if self.match is None:
            raise RuntimeError('RoyaleGymPlayer runs only inside royalesim_match (needs check_deploy)')
        self.ctx = ctx
        self.opponent = make_royalegym(self.kind)
        self.rng = np.random.default_rng(ctx.seed + SEED_OFFSET + ctx.seat)
        self.decisions = 0

    def mask(self, seat):
        """[4, 32, 18] own-frame legality from RoyaleSim check_deploy (own hand/elixir, public board)."""
        from .royalesim_adapter import action_to_command
        b = self.match.b
        planes = np.zeros((4, 32, 18), dtype=bool)
        for slot in range(4):
            for tile in range(576):
                _, _, x, y = action_to_command(slot*576 + tile, seat)
                reason = b.check_deploy(seat, slot, x, y)
                if reason == 0:
                    planes[slot, tile // 18, tile % 18] = True
                elif tile == 0 and reason in (3, 4, 13):   # EMPTY_SLOT, NOT_ENOUGH_ELIXIR, TOO_EARLY: whole slot
                    break
        return planes

    def act(self, view: PublicView) -> Decision:
        if not view.can_act or view.tick % self.decision_ticks:
            return Decision(WAIT, stats=None)
        planes = self.mask(view.seat)
        flat = np.concatenate([[True], planes.reshape(-1)])
        action = int(self.opponent.act({'mask_planes': planes}, flat, self.rng))
        self.decisions += 1
        if action <= 0 or action > 2304 or not flat[action]:
            return Decision(WAIT, stats={})
        return Decision(action - 1, stats={})

    def close(self):
        pass


class ScriptedPlayer:
    """Our C56 PublicScriptedOpponent on the public packet, every 10 ticks."""
    deadline_seconds = None

    def __init__(self, rt, style='balanced', *, interval=10):
        self.rt, self.style, self.interval = rt, style, interval
        self.name = f'scripted-{style}'

    def start(self, ctx: MatchContext):
        from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
        self.bot = PublicScriptedOpponent(self.rt.R.builder, style=self.style, card_scope='c56')

    def act(self, view: PublicView) -> Decision:
        if not view.can_act or view.tick % self.interval:
            return Decision(WAIT, stats=None)
        action = int(self.bot.select_action(view.reserved.packet))
        return Decision(action if action < WAIT else WAIT, stats={})

    def close(self):
        pass
