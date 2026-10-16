"""C56 search core with explicit Python/native backends.

This core accepts a caller-supplied model root. It is privileged if given a live
battle. The fair player must construct the root using only its public sensor.
Scripts retain their existing masked-ability rule; search proposes abilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
import numpy as np
from .action_space import DiscreteTileActionSpace
from .public_action_mask import PublicActionMaskInput
from .reward_model import reward_potential_p0


def trace_digest(battle):
    import hashlib
    import struct
    from es_common import battle_digest
    return battle_digest(battle) + ':' + hashlib.sha256(
        struct.pack('<625I', *battle.rng.getstate()[1])).hexdigest()


@dataclass(frozen=True)
class C56SearchConfig:
    samples: int = 16
    script_top: int = 4
    horizon: int = 160
    interval: int = 10
    elixir_weight: float = 1.0
    # None/1 preserves the Stage 5 reference path. Live uses 0.2 seconds/2.
    deadline_seconds: float | None = None
    threads: int = 1
    # Offline teacher/simulation default; live RustPlanner passes its own flag.
    wait_screen8: bool = True

    def __post_init__(self):
        if type(self.wait_screen8) is not bool:
            raise ValueError('wait_screen8 must be an explicit boolean')
        if self.samples < 0 or self.script_top < 0 or self.horizon < 0 or self.interval <= 0:
            raise ValueError('invalid C56 search configuration')
        if (not 1 <= self.threads <= 64 or
                self.deadline_seconds is not None and
                (not math.isfinite(self.deadline_seconds) or self.deadline_seconds < 0)):
            raise ValueError('invalid C56 deadline/threads')


class C56RolloutPlanner:
    def __init__(self, builder, bots, *, backend='python', config=C56SearchConfig(),
                 seed=0, native=None, native_config=None):
        if backend not in ('python', 'native'):
            raise ValueError('backend must be python or native')
        if builder.public_contract_version != 5 or any(b.card_scope != 'c56' for b in bots.values()):
            raise ValueError('C56 search requires contract v5 and C56 scripts')
        self.builder, self.bots = builder, bots
        self.backend, self.config = backend, config
        self.native, self.native_config = native, native_config
        if backend == 'native' and (native is None or native_config is None):
            raise ValueError('native C56 metadata must be initialized before play')
        versions = {getattr(b.mask_builder, 'mask_version', 1) for b in bots.values()}
        if 2 in versions:
            if versions != {2}:
                raise ValueError('mask v2 requires every rollout script to use v2')
            if backend == 'native' and getattr(native, 'mask_version', None) != 2:
                raise ValueError('mask v2 requires native rollout metadata v2')
        self.space = DiscreteTileActionSpace(mask_version=2 if versions == {2} else 1)
        self.rng = np.random.default_rng(seed)
        self.last = None
        self.deadline_stats = None

    def candidates(self, packet, policy_proposals=()):
        bot = self.bots['balanced']
        mask = bot.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
        ranked = bot._ranked_actions(packet, all_plays=True)
        script = int(bot.decide(packet).action_id)
        pool = np.flatnonzero(mask[:2304])
        samples = self.rng.choice(pool, min(self.config.samples, len(pool)), replace=False).tolist()
        proposals = [script, 2304] + [int(r.action_id) for r in ranked[:self.config.script_top]]
        if mask[2305]:
            proposals.append(2305)
        proposals += list(policy_proposals) + samples
        candidates = list(dict.fromkeys(int(a) for a in proposals if mask[int(a)]))
        if self.config.wait_screen8:
            from .wait_screen8 import TIMED_WAITS
            self.wait_own_elixir = float(packet.observation.global_features[5]) * 10
            candidates = [a for a in candidates if a != 2305] + list(TIMED_WAITS)
        return candidates, mask

    def import_root(self, battle):
        import clasher_core
        from differential import snapshot
        if any(p.card_level(c) != 11 or c not in self.native_config['cards']
               for p in battle.players for c in p.deck):
            raise ValueError('native C56 search requires level 11 supported cards')
        root = clasher_core.BattleState(snapshot(battle, self.native_config))
        root.set_public_movement_speeds([
            (e.id, e._unslowed_movement_speed())
            for e in battle.entities.values() if type(e).__name__ == 'Troop'])
        return root

    def python_rollout(self, battle, seat, action, other, style, trace=False):
        sim = battle.clone()
        self.space.apply_action(sim, seat, action)
        self.space.apply_action(sim, 1-seat, other)
        ticks = calls = 0
        events = []
        while ticks < self.config.horizon and not sim.game_over:
            for _ in range(self.config.interval):
                if sim.game_over:
                    break
                sim.step()
                ticks += 1
            if ticks < self.config.horizon and not sim.game_over:
                for actor in (seat, 1-seat):
                    packet = self.builder.build_public(sim, actor)
                    move = int(self.bots['balanced' if actor == seat else style].select_action(packet))
                    calls += 1
                    if trace:
                        events.append((sim.tick, actor, move, trace_digest(sim)))
                    self.space.apply_action(sim, actor, move)
        if sim.game_over:
            value = 0. if sim.winner is None else 2. if sim.winner == seat else -2.
        else:
            value = reward_potential_p0(sim, 'defense-v2')
            value += self.config.elixir_weight * .08 * (sim.players[0].elixir-sim.players[1].elixir)/16.
            if seat:
                value = -value
        return value, ticks, calls, 0, events, trace_digest(sim) if trace else ''

    def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None):
        if self.config.wait_screen8:
            from .wait_screen8 import score_candidates
            return score_candidates(self, root, seat, candidates, trace=trace, deadline=deadline)
        if deadline is None and self.config.deadline_seconds is not None:
            deadline = time.perf_counter() + self.config.deadline_seconds
        if deadline is not None or self.config.threads != 1:
            return self._score_anytime(root, seat, candidates, trace=trace, deadline=deadline)
        self.deadline_stats = None
        scores = np.zeros(len(candidates))
        traces = []
        for style in ('balanced', 'pressure', 'defense'):
            if self.backend == 'native':
                other = self.native.select_action(root, 1-seat, style)
            else:
                other = int(self.bots[style].select_action(self.builder.build_public(root, 1-seat)))
            for i, action in enumerate(candidates):
                if self.backend == 'native':
                    result = self.native.rollout(root, seat, action, other, 'balanced', style,
                        self.config.horizon, self.config.interval, self.config.elixir_weight, trace, trace)
                else:
                    result = self.python_rollout(root, seat, action, other, style, trace)
                scores[i] += result[0] / 3
                if trace:
                    traces.append((style, action, result))
        best = 0
        for i in range(1, len(candidates)):
            if scores[i] > scores[best] + 1e-9:
                best = i
        self.last = dict(candidates=candidates, scores=scores.tolist(), traces=traces)
        return candidates[best]

    def _score_anytime(self, root, seat, candidates, *, trace, deadline):
        if self.backend != 'native':
            raise ValueError('deadline/threaded C56 search requires the native backend')
        if not candidates:
            raise ValueError('C56 search needs a legal fallback candidate')
        remaining = None if deadline is None else max(0., deadline-time.perf_counter())
        results = self.native.search_candidates(root, seat, candidates,
            self.config.horizon, self.config.interval, self.config.elixir_weight,
            self.config.threads, remaining, trace)
        scores = [None] * len(candidates)
        best = None
        for i, row in enumerate(results):
            if row is None:
                continue
            score = 0.
            for result in row:
                score += result[0] / 3
            scores[i] = score
            if best is None or score > scores[best] + 1e-9:
                best = i
        # Keep the exact Stage 5 diagnostic representation when all finish.
        traces = [(style, candidates[i], row[j])
                  for j, style in enumerate(('balanced', 'pressure', 'defense'))
                  for i, row in enumerate(results) if row is not None] if trace else []
        self.last = dict(candidates=candidates, scores=scores, traces=traces)
        completed = sum(row is not None for row in results)
        self.deadline_stats = dict(completed=completed, total=len(candidates),
                                   truncated=completed < len(candidates), fallback=best is None)
        return candidates[0 if best is None else best]

    def select_action(self, battle, seat, *, trace=False):
        deadline = (None if self.config.deadline_seconds is None else
                    time.perf_counter() + self.config.deadline_seconds)
        candidates, _ = self.candidates(self.builder.build_public(battle, seat))
        root = self.import_root(battle) if self.backend == 'native' else battle
        return self.score_candidates(root, seat, candidates, trace=trace, deadline=deadline)
