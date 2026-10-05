"""Oracle-planner qualification harness (evaluation games only; no fitting, no labels).

Mirrors ``clasher.rl.eval.evaluate`` game setup (paired seats, matchup seeds,
asymmetric deck pools, public-script opponent on the council public packet,
decision interval 5, max ticks 6001) but lets a non-network "player" occupy the
candidate seat. Must run inside the frozen pilot runtime (see PROGRESS.md).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl import eval as cl_eval
from clasher.rl.deck_pool import load_deck_pool
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.oracle_sampling import sample_action_subset
from clasher.rl.reward_model import reward_potential_p0, reward_win_prob_p0
from clasher.rl.selfplay_env import SelfPlayBattleEnv, resolve_match_horizon
from clasher.rl.train_recurrent import maybe_silence_stdio

OQ_DIR = Path(__file__).resolve().parent
COUNCIL = OQ_DIR.parent
TRAIN_DECKS = COUNCIL / "m0/data/roles_v2/training.json"
DEV_DECKS = COUNCIL / "m0/data/roles_v2/development.json"
HOG_DECKS = COUNCIL / "pilot/hog26-deployment.json"
CKPT_2903_1M = (
    COUNCIL
    / "pilot/v7r2-launch/runs/s2903/seed-2903/scripted/policy_decisions_001000000.pt"
)
ROLE_DECKS = {"holdout": DEV_DECKS, "hog26": HOG_DECKS}
# Seeds of the pilot one-million diagnostic cells (council_pilot.evaluation_commands,
# evaluation_seed 9413, slots 12-23). Using them gives common matchups with the pilot.
PILOT_CELL_SEEDS = {
    ("holdout", "balanced"): 12009449,
    ("holdout", "pressure"): 13009452,
    ("holdout", "defense"): 14009455,
    ("hog26", "balanced"): 18009467,
    ("hog26", "pressure"): 19009470,
    ("hog26", "defense"): 20009473,
}
DECISION_INTERVAL = 5
MAX_TICKS = 6001


class RolloutLeafOracle(FixedDepthThompsonOracle):
    """Supercell-style leaf: after the searched plies, play on with NO further
    deploys for ``leaf_rollout_ticks`` (or to the end of the match) and score the
    resulting state with the same potential (exact outcome if the game ended).

    Optional extras (all off by default, so the plain variant changes only the leaf):
    - ``centre_gain`` > 0: bandit reward = sigmoid(gain * (phi_leaf - phi_root))
      instead of sigmoid(2.5 * phi_leaf); the stock squashing leaves candidate
      differences of ~0.01 that the Beta(1,1) prior swamps.
    - ``elixir_weight`` > 0: adds weight * 0.08 * (elixir0 - elixir1) / 16 to the
      potential (same scale as defense-v2 board value, where one elixir of troops is
      0.08/16), so an unspent elixir is not worth zero in a no-more-deploys leaf.
    The rollout stops early once only static towers remain (nothing can change).
    """

    def __init__(
        self,
        *args: Any,
        leaf_rollout_ticks: int = 200,
        centre_gain: float = 0.0,
        elixir_weight: float = 0.0,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.leaf_rollout_ticks = int(leaf_rollout_ticks)
        self.centre_gain = float(centre_gain)
        self.elixir_weight = float(elixir_weight)
        self._root_phi = 0.0
        self.leaf_ticks = 0

    def _phi(self, battle) -> float:
        phi = reward_potential_p0(battle, self.reward_profile)
        if self.elixir_weight:
            phi += (
                self.elixir_weight
                * 0.08
                * (battle.players[0].elixir - battle.players[1].elixir)
                / 16.0
            )
        return float(phi)

    def select_actions(self, battle):  # type: ignore[override]
        self._root_phi = self._phi(battle)
        return super().select_actions(battle)

    def _evaluate_state_prob_p0(self, battle) -> float:  # type: ignore[override]
        remaining = self.leaf_rollout_ticks
        while remaining > 0 and not battle.game_over:
            if remaining % 5 == 0 and battle.can_fast_forward_idle():
                break
            battle.step()
            remaining -= 1
            self.leaf_ticks += 1
        if battle.game_over:
            if battle.winner is None:
                return 0.5
            return 1.0 if battle.winner == 0 else 0.0
        phi = self._phi(battle)
        if self.centre_gain > 0.0:
            return float(1.0 / (1.0 + np.exp(-self.centre_gain * (phi - self._root_phi))))
        return float(1.0 / (1.0 + np.exp(-2.5 * phi)))


class PublicRootMixin:
    """Restrict one seat's ROOT candidates to engine-legal AND public-action-mask
    actions, so the planner only ever returns actions the public-contract learner
    could also select. Deeper plies and the other seat keep the engine mask."""

    _root_restriction: tuple | None = None

    def set_root_restriction(self, battle, player_id: int, mask: np.ndarray) -> None:
        self._root_restriction = (battle, int(player_id), mask)

    def _legal_actions(self, battle, player_id: int) -> np.ndarray:
        legal = super()._legal_actions(battle, player_id)  # type: ignore[misc]
        restriction = self._root_restriction
        if (
            restriction is not None
            and battle is restriction[0]
            and player_id == restriction[1]
        ):
            no_op = self.action_space.no_op_action  # type: ignore[attr-defined]
            keep = legal[restriction[2][legal] | (legal == no_op)]
            if keep.size == 0:
                return np.asarray([no_op], dtype=np.int64)
            return keep
        return legal


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
    ) -> None:
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
        self.overrides = 0  # decisions where the chosen action differs from the script's

    def _packet(self, battle, player_id: int):
        from clasher.rl.public_observation import project_council_public_observation

        real = self.env.battle
        self.env.battle = battle
        try:
            observation = self.env.get_structured_observation(player_id)
        finally:
            self.env.battle = real
        self.script_calls += 1
        return project_council_public_observation(observation)

    def _model_action(self, battle, seat: int, planning_seat: int) -> int:
        if seat == planning_seat or self.opponent_model is None:
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
            picks = self.rng.choice(pool, size=min(self.samples, pool.size), replace=False)
            for action in picks.tolist():
                if action not in candidates:
                    candidates.append(int(action))
        best_action = candidates[0]
        best_value = -1e9
        for action in candidates:
            value = self._rollout(battle, player_id, action, other_action)
            if value > best_value + 1e-9:
                best_value = value
                best_action = action
        self.overrides += int(best_action != script_choice)
        return int(best_action)


class Context:
    """Per-process shared objects (checkpoint builder, pools, envs)."""

    def __init__(self, checkpoint: Path = CKPT_2903_1M) -> None:
        torch.set_num_threads(1)
        self.device = torch.device("cpu")
        self.loaded = cl_eval.load_policy_checkpoint(
            Path(checkpoint), device=self.device, decks_path=TRAIN_DECKS
        )
        self.config = self.loaded.model.config
        self.max_ticks = resolve_match_horizon(
            MAX_TICKS, self.config.public_contract_version
        )
        self._envs: dict[str, dict[int, SelfPlayBattleEnv]] = {}
        self._pools: dict[str, tuple] = {}
        self._bots: dict[str, Any] = {}

    def envs(self, role: str, seed: int) -> dict[int, SelfPlayBattleEnv]:
        if role not in self._envs:
            self._envs[role] = cl_eval._make_evaluation_envs(
                candidate=self.loaded,
                decks_path=TRAIN_DECKS,
                sampling_decks_path=None,
                candidate_sampling_decks_path=ROLE_DECKS[role],
                opponent_sampling_decks_path=TRAIN_DECKS,
                decision_interval=DECISION_INTERVAL,
                max_ticks=self.max_ticks,
                seed=seed,
                mirror_match=False,
                reward_profile="objective-v1",
            )
            for env in self._envs[role].values():
                env._structured_obs_builder = self.loaded.builder
                env._public_action_mask_builder = None
                env.public_contract_version = self.config.public_contract_version
        return self._envs[role]

    def pools(self, role: str):
        if role not in self._pools:
            self._pools[role] = (
                load_deck_pool(ROLE_DECKS[role]),
                load_deck_pool(TRAIN_DECKS),
            )
        return self._pools[role]

    def strategy_bot(self, name: str):
        key = "sb:" + name
        if key not in self._bots:
            from clasher.rl.strategy_bots import StrategyBot

            self._bots[key] = StrategyBot(name)
        return self._bots[key]

    def bot(self, style: str):
        if style not in self._bots:
            from clasher.rl.public_scripted_opponent import PublicScriptedOpponent

            self._bots[style] = PublicScriptedOpponent(self.loaded.builder, style=style)
        return self._bots[style]


def make_planner(env: SelfPlayBattleEnv, player: dict, seed: int):
    kwargs = dict(
        action_space=env.action_space,
        decision_interval_ticks=int(player.get("interval", DECISION_INTERVAL)),
        plan_depth=int(player.get("depth", 10)),
        num_simulations=int(player.get("sims", 48)),
        rollout_action_samples=int(player.get("samples", 96)),
        seed=seed,
        reward_profile=player.get("profile", "objective-v1"),
        stable_root_candidates=bool(player.get("stable_root", False)),
    )
    leaf = int(player.get("leaf_rollout_ticks", 0))
    base: type = RolloutLeafOracle if leaf > 0 else FixedDepthThompsonOracle
    if player.get("mask_public"):
        base = type("Public" + base.__name__, (PublicRootMixin, base), {})
    if leaf > 0:
        return base(
            leaf_rollout_ticks=leaf,
            centre_gain=float(player.get("centre_gain", 0.0)),
            elixir_weight=float(player.get("elixir_weight", 0.0)),
            **kwargs,
        )
    return base(**kwargs)


def game_id(spec: dict) -> str:
    return (
        f"{spec['player']['name']}__{spec['role']}__{spec['opponent']}"
        f"__s{spec['seed']}__g{spec['game']:03d}"
    )


def play_game(ctx: Context, spec: dict) -> dict:
    """Play one evaluation game. ``spec`` keys: role, opponent (balanced|pressure|
    defense|policy), seed (cell base seed), game (index; seat = game % 2,
    matchup = game // 2), player {name, kind, ...}."""

    role = spec["role"]
    opponent_kind = spec["opponent"]
    player = spec["player"]
    kind = player["kind"]
    seed = int(spec["seed"])
    game = int(spec["game"])
    matchup = game // 2
    matchup_seed = seed + matchup * 1009
    candidate_player = game % 2
    other_player = 1 - candidate_player
    env = ctx.envs(role, seed)[candidate_player]
    candidate_deck, opponent_deck = cl_eval._sample_paired_ordered_decks(
        *ctx.pools(role), matchup_seed=matchup_seed
    )
    ordered = (
        (candidate_deck, opponent_deck)
        if candidate_player == 0
        else (opponent_deck, candidate_deck)
    )
    with maybe_silence_stdio(True):
        env.reset(seed=matchup_seed, ordered_decks=ordered)
    rng = np.random.default_rng(matchup_seed + 91_117)  # parity with eval (unused)
    torch.manual_seed(matchup_seed + 271_828)
    device = ctx.device
    loaded = ctx.loaded
    no_op = env.action_space.no_op_action

    planner = None
    control_rng = np.random.default_rng(matchup_seed * 2 + candidate_player + 7_919)
    if kind == "planner":
        planner = make_planner(
            env, player, seed=matchup_seed * 2 + candidate_player + 7_919
        )
    elif kind == "srp":
        planner = ScriptRolloutPlanner(
            env,
            ctx.bot(player.get("style", "balanced")),
            samples=int(player.get("samples", 16)),
            script_top=int(player.get("script_top", 4)),
            horizon=int(player.get("horizon", 160)),
            rollout_interval=int(player.get("rollout_interval", 10)),
            profile=player.get("profile", "defense-v2"),
            elixir_weight=float(player.get("elixir_weight", 1.0)),
            seed=matchup_seed * 2 + candidate_player + 7_919,
            opponent_model=(
                ctx.strategy_bot(player["opponent_model"][3:])
                if str(player.get("opponent_model", "")).startswith("sb-")
                else None
            ),
        )
    plan_every = int(player.get("plan_every", 1))  # query planner every N decisions
    candidate_state = loaded.model.initial_state(1, device=device)
    opponent_state = (
        loaded.model.initial_state(1, device=device)
        if opponent_kind == "policy"
        else None
    )
    candidate_previous_action = no_op
    opponent_previous_action = no_op
    candidate_previous_reward = 0.0
    opponent_previous_reward = 0.0
    episode_start = True
    done = False
    decisions = 0
    planner_calls = 0
    planner_seconds = 0.0
    planner_cpu_seconds = 0.0
    placements = 0
    failed_actions = 0
    not_in_public_mask = 0
    playable_decisions = 0
    trace: list[list[int]] = []
    started = time.perf_counter()
    cpu_started = time.process_time()

    while not done:
        battle = env.battle
        assert battle is not None
        if kind == "policy":
            candidate_action, candidate_state, candidate_mask, _ = cl_eval._policy_step(
                loaded,
                env,
                candidate_player,
                state=candidate_state,
                previous_action=candidate_previous_action,
                previous_reward=candidate_previous_reward,
                episode_start=episode_start,
                deterministic=False,
                device=device,
            )
        else:
            observation = env.get_structured_observation(candidate_player)
            candidate_mask = env.get_action_mask(
                candidate_player, structured_observation=observation
            )
            exact_mask = env.action_space.legal_action_mask(battle, candidate_player)
            if player.get("mask_public"):
                exact_mask = exact_mask & candidate_mask
                exact_mask[no_op] = True
            legal = np.flatnonzero(exact_mask).astype(np.int64, copy=False)
            playable = bool(np.any(legal != no_op)) and legal.size > 0
            playable_decisions += int(playable)
            if kind == "noop" or not playable:
                candidate_action = no_op
            elif kind == "random":
                subset = sample_action_subset(
                    legal,
                    sample_limit=int(player.get("samples", 96)),
                    no_op_action=no_op,
                    rng=control_rng,
                )
                candidate_action = int(control_rng.choice(subset))
            elif kind == "srp":
                if decisions % plan_every != 0:
                    candidate_action = no_op
                else:
                    t0 = time.perf_counter()
                    c0 = time.process_time()
                    with maybe_silence_stdio(True):
                        candidate_action = planner.select_action(
                            battle, candidate_player, legal
                        )
                    planner_seconds += time.perf_counter() - t0
                    planner_cpu_seconds += time.process_time() - c0
                    planner_calls += 1
            elif kind == "planner":
                if decisions % plan_every != 0:
                    candidate_action = no_op
                else:
                    t0 = time.perf_counter()
                    c0 = time.process_time()
                    if player.get("mask_public"):
                        planner.set_root_restriction(
                            battle, candidate_player, candidate_mask
                        )
                    with maybe_silence_stdio(True):
                        candidate_action = int(
                            planner.select_actions(battle)[candidate_player]
                        )
                    planner_seconds += time.perf_counter() - t0
                    planner_cpu_seconds += time.process_time() - c0
                    planner_calls += 1
            else:
                raise ValueError(f"unknown player kind {kind!r}")
            if player.get("shadow"):
                # Purity check: plan, then discard the plan. The game must then be
                # identical to the never-play control on the same spec.
                candidate_action = no_op
            if candidate_action != no_op and not candidate_mask[candidate_action]:
                not_in_public_mask += 1

        if opponent_kind.startswith("sb-"):
            # Out-of-family scripted opponent: clasher.rl.strategy_bots.StrategyBot
            # (the pilot's training opponent family), on the engine/contract mask.
            other_mask = env.get_action_mask(other_player)
            other_action = ctx.strategy_bot(opponent_kind[3:]).select_action(
                env, other_player, action_mask=other_mask
            )
        elif opponent_kind == "policy":
            other_action, opponent_state, other_mask = cl_eval._policy_action(
                loaded,
                env,
                other_player,
                state=opponent_state,
                previous_action=opponent_previous_action,
                previous_reward=opponent_previous_reward,
                episode_start=episode_start,
                deterministic=False,
                device=device,
            )
        else:
            from clasher.rl.public_observation import project_council_public_observation

            other_observation = env.get_structured_observation(other_player)
            other_mask = env.get_action_mask(
                other_player, structured_observation=other_observation
            )
            other_action = ctx.bot(opponent_kind).select_action(
                project_council_public_observation(other_observation)
            )
        if candidate_action != no_op:
            slot = int(candidate_action) // 576
            hand = battle.players[candidate_player].hand
            trace.append(
                [
                    int(battle.tick),
                    int(candidate_action),
                    str(hand[slot]) if slot < len(hand) else "?",
                    bool(candidate_mask[candidate_action]),
                ]
            )
        with maybe_silence_stdio(True):
            rewards, done, info = env.step(
                {candidate_player: candidate_action, other_player: other_action},
                pre_action_masks={
                    candidate_player: candidate_mask,
                    other_player: other_mask,
                },
            )
        if candidate_action != no_op:
            placements += 1
            failed_actions += int(not info.action_success.get(candidate_player, True))
        candidate_previous_action = candidate_action
        opponent_previous_action = other_action
        candidate_previous_reward = float(rewards[candidate_player])
        opponent_previous_reward = float(rewards[other_player])
        episode_start = False
        decisions += 1

    battle = env.battle
    assert battle is not None
    if not battle.game_over:
        raise RuntimeError("match did not complete")
    if battle.winner is None:
        outcome = "draw"
    elif battle.winner == candidate_player:
        outcome = "win"
    else:
        outcome = "loss"
    cand = battle.players[candidate_player]
    opp = battle.players[other_player]
    return {
        "schema": "oracle-qualification-game-v1",
        "id": game_id(spec),
        "spec": spec,
        "privileged_player": kind in ("planner", "srp"),
        "planner_stats": (
            {
                "rollouts": planner.rollouts,
                "rollout_ticks": planner.rollout_ticks,
                "script_calls": planner.script_calls,
                "overrides": planner.overrides,
            }
            if kind == "srp"
            else None
        ),
        "game": game,
        "matchup": matchup,
        "matchup_seed": matchup_seed,
        "candidate_player": candidate_player,
        "outcome": outcome,
        "score": {"win": 1.0, "draw": 0.5, "loss": 0.0}[outcome],
        "candidate_crowns": battle.get_crown_count(candidate_player),
        "opponent_crowns": battle.get_crown_count(other_player),
        "ticks": int(battle.tick),
        "candidate_deck": list(cand.deck),
        "opponent_deck": list(opp.deck),
        "candidate_tower_hp": [
            float(cand.left_tower_hp),
            float(cand.right_tower_hp),
            float(cand.king_tower_hp),
        ],
        "opponent_tower_hp": [
            float(opp.left_tower_hp),
            float(opp.right_tower_hp),
            float(opp.king_tower_hp),
        ],
        "decisions": decisions,
        "playable_decisions": playable_decisions,
        "planner_calls": planner_calls,
        "planner_seconds": planner_seconds,
        "planner_cpu_seconds": planner_cpu_seconds,
        "placements": placements,
        "failed_actions": failed_actions,
        "actions_outside_public_mask": not_in_public_mask,
        "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": time.process_time() - cpu_started,
        "trace": trace,
        "pid": os.getpid(),
        "runtime": os.environ.get("CLASHER_ROOT"),
    }


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(payload, sort_keys=True) + "\n")
    os.replace(tmp, path)
