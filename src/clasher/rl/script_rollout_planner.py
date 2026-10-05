"""Scripted rollout search, copied from the oracle qualification harness.

The source harness remains frozen. This opt-in planner omits critic tensors and
repeated public projection for P16 script decisions, and avoids observation
work when the public mask cannot afford any hand card. ``fast_script=False``
retains the original path for differential validation. ``backend="native"``
opts into the experimental P16 Rust rollout core; the default remains Python.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .public_scripted_opponent import PublicScriptedOpponent
from .reward_model import reward_potential_p0
from .selfplay_env import SelfPlayBattleEnv


class ScriptRolloutPlanner:
    """NOT the repo's planner: a one-step lookahead with scripted continuation
    (the classic "rollout algorithm" = one policy-improvement step over a base
    policy). For each root candidate of the planning seat: fork the true state,
    play the candidate (the other seat plays the script's move), then let BOTH
    seats follow the public script (``style``) every ``rollout_interval`` ticks for
    ``horizon`` ticks and score the result with the reward potential (+ elixir as
    material). The fork copies the engine RNG and the script is deterministic, so
    one rollout per candidate is exact under the model; no bandit is needed.
    Candidates: script's own choice, no-op, the script's next-best plays, and a
    uniform sample of legal placements (engine-legal AND public mask).
    Privileged: forks the true state and reads the opponent's hand/elixir through
    the script's own-seat observation of the forked state."""

    def __init__(
        self,
        env: SelfPlayBattleEnv,
        bot: Any,
        *,
        samples: int = 16,
        script_top: int = 4,
        horizon: int = 160,
        rollout_interval: int = 10,
        profile: str = "defense-v2",
        elixir_weight: float = 1.0,
        seed: int | None = None,
        opponent_model: Any = None,
        fast_script: bool = True,
        backend: str = "python",
    ) -> None:
        if backend not in {"python", "native"}:
            raise ValueError("backend must be python or native")
        self.backend = backend
        self._native_root = None
        self.fast_script = fast_script
        self.observation_skips = 0
        self.env = env
        self.space = env.action_space
        self.bot = bot
        # None: the opponent is modelled by ``bot`` too. Otherwise an object with
        # StrategyBot's interface select_action(env, player_id) (out-of-family model).
        self.opponent_model = opponent_model
        self.samples = int(samples)
        self.script_top = int(script_top)
        self.horizon = int(horizon)
        self.rollout_interval = int(rollout_interval)
        self.profile = profile
        self.elixir_weight = float(elixir_weight)
        self.rng = np.random.default_rng(seed)
        self.rollouts = 0
        self.rollout_ticks = 0
        self.script_calls = 0
        self.overrides = (
            0  # decisions where the chosen action differs from the script's
        )
        if backend == "native":
            self._init_native_backend()

    def _init_native_backend(self) -> None:
        """Import the optional P16 extension and immutable rules once per planner."""
        import json
        import math

        from clasher.balance import tournament_tower_stat
        from .card_semantics import building_target_pressure_score
        from .public_scripted_opponent import SUPPORTED_CARDS
        from .strategy_bots import BalancedStrategyConfig, StrategyBot

        if not self._can_use_fast_script() or not self.space.canonical_perspective:
            raise ValueError("native backend requires the P16 public-v4 fast script")
        if (
            self.profile != "defense-v2"
            or self.horizon < 0
            or self.rollout_interval <= 0
        ):
            raise ValueError(
                "native backend requires defense-v2 and valid rollout timing"
            )
        if self.opponent_model is not None and not (
            type(self.opponent_model) is StrategyBot
            and self.opponent_model.name == "balanced"
            and self.opponent_model.balanced_config == BalancedStrategyConfig()
        ):
            raise ValueError("native backend supports the default balanced StrategyBot")
        # engine-rs is an experimental optional extension, outside the Python package.
        import clasher_core
        from differential import config, snapshot

        builder = self.bot.builder
        if builder._uses_typed_tokens:
            raise ValueError(
                "native backend requires the qualified untyped P16 vocabulary"
            )
        cards, bodies = {}, {}
        for token, (name, stats) in self.bot.cards.items():
            cost = float(stats.mana_cost)
            count = float(stats.summon_count or 1)
            cards[name] = dict(
                token=token,
                radius=float(stats.collision_radius or 0.5),
                blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
                cost=cost,
                count=count,
                hp=float(stats.scaled_hitpoints or 0),
                damage=float(stats.scaled_damage or 0),
                range=float(stats.range or 0),
                shield=bool(
                    stats._raw_entry.get("summonCharacterData", {}).get(
                        "shieldHitpoints", 0
                    )
                ),
                building=str(stats.card_type).lower() == "building",
                spell=name in self.bot.spells,
                margin=int(stats.deploy_w_tile_margin or 0),
                only_buildings=bool(stats.targets_only_buildings),
                efficiency=(
                    math.sqrt(max(0.0, float(stats.hitpoints or 0)) / 700.0)
                    + float(stats.damage or 0) / 170.0
                    + 0.2 * max(1.0, count)
                )
                / max(1.0, cost),
                tower_pressure=math.log1p(building_target_pressure_score(stats))
                / math.log1p(400.0),
            )
        for token, stats in self.bot.bodies.items():
            name = next(
                name
                for name, card in self.bot.cards.values()
                if card.name == stats.name
            )
            bodies[stats.name] = dict(
                cards[name],
                token=token,
                blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
            )
        for token, name in self.bot.crowns.items():
            bodies[name] = dict(
                token=token,
                radius=1.0,
                blocker_radius=float(builder.card_stat_features[token, 12]) * 3,
                cost=0.0,
                count=1.0,
                hp=float(
                    tournament_tower_stat(
                        "PrincessTower" if name == "Tower" else "KingTower", "hitpoints"
                    )
                ),
                damage=0.0,
                range=0.0,
                shield=False,
                building=True,
                spell=False,
                margin=0,
                only_buildings=False,
            )
        self._native_scripts = clasher_core.NativeScripts(
            json.dumps(dict(cards=cards, bodies=bodies))
        )
        self._native_config = config(tuple(sorted(SUPPORTED_CARDS)))
        self._native_snapshot = snapshot
        self._native_class = clasher_core.BattleState
        self._native_tower_hp = {
            slot: bodies["KingTower" if slot == "king" else "Tower"]["hp"]
            for slot in ("left", "right", "king")
        }

    def _import_native_root(self, battle):
        if any(
            p.max_elixir != 10 for p in battle.players
        ) or battle._starting_tower_hps != {
            0: self._native_tower_hp,
            1: self._native_tower_hp,
        }:
            raise ValueError(
                "native backend requires standard tournament towers and elixir"
            )
        if any(
            name not in self._native_config["cards"] or p.card_level(name) != 11
            for p in battle.players
            for name in p.deck
        ):
            raise ValueError("native backend supports only level-11 P16 decks")
        root = self._native_class(self._native_snapshot(battle, self._native_config))
        root.set_public_movement_speeds(
            [
                (
                    e.id,
                    float(
                        e.original_speed if e.original_speed is not None else e.speed
                    ),
                )
                for e in battle.entities.values()
                if type(e).__name__ == "Troop"
            ]
        )
        return root

    def _packet(self, battle, player_id: int):
        from clasher.rl.public_observation import project_council_public_observation

        if self._can_use_fast_script():
            self.script_calls += 1
            observation = self.env.structured_obs_builder.build_actor(battle, player_id)
            return project_council_public_observation(observation)
        real = self.env.battle
        self.env.battle = battle
        try:
            observation = self.env.get_structured_observation(player_id)
        finally:
            self.env.battle = real
        self.script_calls += 1
        return project_council_public_observation(observation)

    def _can_use_fast_script(self) -> bool:
        return (
            self.fast_script
            and type(self.bot) is PublicScriptedOpponent
            and self.bot.card_scope == "p16"
            and self.env.public_contract_version == 4
            and self.bot.builder is self.env.structured_obs_builder
        )

    def _must_wait(self, battle, seat: int) -> bool:
        """Match the public mask's float32 elixir test before building tensors."""
        if not self._can_use_fast_script():
            return False
        own = battle.players[seat]
        # Keep float32 rounding and the mask's tolerance, including fractional elixir.
        elixir = (
            float(np.float32(np.clip(own.elixir / max(1.0, own.max_elixir), 0, 1))) * 10
        )
        if not np.isfinite(elixir):
            return False
        for name in own.hand[:4]:
            if name is None:
                continue
            token = self.bot.builder.token_id(name)
            card = self.bot.cards.get(token)
            if card is None or float(card[1].mana_cost) <= elixir + 1e-6:
                return False
        return True

    def _model_action(self, battle, seat: int, planning_seat: int) -> int:
        if seat == planning_seat or self.opponent_model is None:
            if self._must_wait(battle, seat):
                self.script_calls += 1
                self.observation_skips += 1
                return self.space.no_op_action
            return int(self.bot.select_action(self._packet(battle, seat)))
        real = self.env.battle
        self.env.battle = battle
        try:
            self.script_calls += 1
            return int(self.opponent_model.select_action(self.env, seat))
        finally:
            self.env.battle = real

    def _phi(self, battle, player_id: int) -> float:
        if battle.game_over:
            if battle.winner is None:
                return 0.0
            return 2.0 if battle.winner == player_id else -2.0
        phi = reward_potential_p0(battle, self.profile)
        phi += (
            self.elixir_weight
            * 0.08
            * (battle.players[0].elixir - battle.players[1].elixir)
            / 16.0
        )
        return float(phi if player_id == 0 else -phi)

    def _rollout(self, battle, player_id: int, action: int, other_action: int) -> float:
        if self.backend == "native":
            root = self._native_root
            if root is None:
                root = self._import_native_root(battle)
            value, ticks, calls, skips, _, _ = self._native_scripts.rollout(
                root,
                player_id,
                int(action),
                int(other_action),
                self.bot.style,
                "" if self.opponent_model is None else "sb-balanced",
                self.horizon,
                self.rollout_interval,
                self.elixir_weight,
            )
            self.rollouts += 1
            self.rollout_ticks += ticks
            self.script_calls += calls
            self.observation_skips += skips
            return value
        sim = battle.clone()
        self.space.apply_action(sim, player_id, int(action))
        self.space.apply_action(sim, 1 - player_id, int(other_action))
        ticks = 0
        while ticks < self.horizon and not sim.game_over:
            for _ in range(self.rollout_interval):
                if sim.game_over:
                    break
                sim.step()
                ticks += 1
            if ticks < self.horizon and not sim.game_over:
                for seat in (player_id, 1 - player_id):
                    move = self._model_action(sim, seat, player_id)
                    if move != self.space.no_op_action:
                        self.space.apply_action(sim, seat, int(move))
        self.rollouts += 1
        self.rollout_ticks += ticks
        return self._phi(sim, player_id)

    def select_action(self, battle, player_id: int, legal: np.ndarray) -> int:
        no_op = self.space.no_op_action
        legal_set = set(int(a) for a in legal.tolist())
        own_packet = self._packet(battle, player_id)
        ranked = self.bot._ranked_actions(own_packet, all_plays=True)
        script_choice = int(self.bot.decide(own_packet).action_id)
        other_action = self._model_action(battle, 1 - player_id, player_id)
        candidates: list[int] = []
        for action in [script_choice, no_op] + [
            int(item.action_id) for item in ranked[: self.script_top]
        ]:
            if (action == no_op or action in legal_set) and action not in candidates:
                candidates.append(action)
        pool = legal[legal != no_op]
        if pool.size:
            picks = self.rng.choice(
                pool, size=min(self.samples, pool.size), replace=False
            )
            for action in picks.tolist():
                if action not in candidates:
                    candidates.append(int(action))
        best_action = candidates[0]
        best_value = -1e9
        if self.backend == "native":
            self._native_root = self._import_native_root(battle)
        try:
            for action in candidates:
                value = self._rollout(battle, player_id, action, other_action)
                if value > best_value + 1e-9:
                    best_value = value
                    best_action = action
        finally:
            self._native_root = None
        self.overrides += int(best_action != script_choice)
        return int(best_action)
