"""Calibrate procedural defense episodes before allowing policy training."""

# mypy: disable-error-code="import-untyped,no-any-return"
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.paths import resolve_path
from clasher.rl.defense_scenarios import (
    DefenseScenarioSpec,
    apply_defense_scenario,
    defense_scenario_outcome,
    defense_scenario_resource_loss,
    tower_fraction,
)
from clasher.rl.eval import LoadedPolicy, _policy_step, load_policy_checkpoint
from clasher.rl.reward_model import incoming_tower_danger
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot


def _tower_fraction(env: SelfPlayBattleEnv, spec: DefenseScenarioSpec) -> float:
    assert env.battle is not None
    return tower_fraction(env.battle, spec.learner_player, spec.tower_slot)


def _controller_action(
    env: SelfPlayBattleEnv,
    learner: int,
    controller: str,
    bot: StrategyBot | None,
) -> tuple[int, np.ndarray]:
    mask = env.get_action_mask(learner)
    if controller == "noop":
        return env.action_space.no_op_action, mask
    assert bot is not None
    return bot.select_action(env, learner, action_mask=mask), mask


def _policy_controller_action(
    env: SelfPlayBattleEnv,
    learner: int,
    policy: LoadedPolicy,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
    deterministic: bool,
) -> tuple[int, tuple[torch.Tensor, torch.Tensor], np.ndarray]:
    action, next_state, mask, _ = _policy_step(
        policy,
        env,
        learner,
        state=state,
        previous_action=previous_action,
        previous_reward=previous_reward,
        episode_start=episode_start,
        deterministic=deterministic,
        device=torch.device("cpu"),
    )
    return action, next_state, mask


def run_calibration(
    *,
    scenarios: int,
    seed: int,
    decks_path: Path,
    sampling_decks_path: Path,
    horizons: tuple[int, ...],
    controllers: tuple[str, ...],
    minimum_elixir: int,
    maximum_elixir: int,
    learner_sampling_decks_path: Path | None = None,
    opponent_sampling_decks_path: Path | None = None,
    checkpoint: Path | None = None,
    deterministic_policy: bool = True,
) -> dict[str, Any]:
    if scenarios <= 0 or not horizons:
        raise ValueError("scenarios and horizons must be non-empty")
    if any(horizon <= 0 or horizon % 8 for horizon in horizons):
        raise ValueError("horizons must be positive multiples of eight ticks")
    if "policy" in controllers and checkpoint is None:
        raise ValueError("the policy controller requires checkpoint")
    policy = (
        load_policy_checkpoint(
            checkpoint,
            device=torch.device("cpu"),
            decks_path=decks_path,
        )
        if checkpoint is not None
        else None
    )
    rows: list[dict[str, Any]] = []
    for controller in controllers:
        bot = (
            StrategyBot(controller)
            if controller not in {"noop", "policy"}
            else None
        )
        for scenario_index in range(scenarios):
            scenario_seed = seed + scenario_index * 1009
            learner = scenario_index % 2
            player_sampling_paths = (
                (learner_sampling_decks_path, opponent_sampling_decks_path)
                if learner == 0
                else (opponent_sampling_decks_path, learner_sampling_decks_path)
            )
            env = SelfPlayBattleEnv(
                decks_path=decks_path,
                sampling_decks_path=sampling_decks_path,
                player0_sampling_decks_path=player_sampling_paths[0],
                player1_sampling_decks_path=player_sampling_paths[1],
                learner_player_id=learner,
                seed=scenario_seed,
                canonical_perspective=True,
                engine_fast_path="on",
                reward_profile="defense-v2",
                canonical_lane_globals=(
                    bool(policy.model.config.canonical_lane_globals)
                    if controller == "policy" and policy is not None
                    else False
                ),
            )
            env.reset(seed=scenario_seed)
            assert env.battle is not None
            spec = apply_defense_scenario(
                env.battle,
                learner,
                rng=random.Random(scenario_seed + 17),
                minimum_elixir=minimum_elixir,
                maximum_elixir=maximum_elixir,
            )
            env._reset_reward_trackers()
            maximum_horizon = max(horizons)
            recorded: set[int] = set()
            policy_state = (
                policy.model.initial_state(1, device=torch.device("cpu"))
                if controller == "policy" and policy is not None
                else None
            )
            previous_action = env.action_space.no_op_action
            previous_reward = 0.0
            episode_start = True
            torch.manual_seed(scenario_seed + 271_828)
            while env.battle.tick - spec.start_tick < maximum_horizon:
                opponent = 1 - learner
                if controller == "policy":
                    assert policy is not None and policy_state is not None
                    learner_action, policy_state, learner_mask = (
                        _policy_controller_action(
                            env,
                            learner,
                            policy,
                            state=policy_state,
                            previous_action=previous_action,
                            previous_reward=previous_reward,
                            episode_start=episode_start,
                            deterministic=deterministic_policy,
                        )
                    )
                else:
                    learner_action, learner_mask = _controller_action(
                        env, learner, controller, bot
                    )
                opponent_mask = env.get_action_mask(opponent)
                rewards, done, _ = env.step(
                    {
                        learner: learner_action,
                        opponent: env.action_space.no_op_action,
                    },
                    pre_action_masks={
                        learner: learner_mask,
                        opponent: opponent_mask,
                    },
                )
                if controller == "policy":
                    previous_action = learner_action
                    previous_reward = float(rewards[learner])
                    episode_start = False
                elapsed = env.battle.tick - spec.start_tick
                for horizon in horizons:
                    if horizon <= elapsed and horizon not in recorded:
                        current_fraction = _tower_fraction(env, spec)
                        rows.append(
                            {
                                "controller": controller,
                                "scenario": scenario_index,
                                "seed": scenario_seed,
                                "learner_player": learner,
                                "tower_slot": spec.tower_slot,
                                "threat_cards": list(spec.threat_cards),
                                "learner_deck": list(
                                    env.battle.players[learner].deck
                                ),
                                "opponent_deck": list(
                                    env.battle.players[1 - learner].deck
                                ),
                                "initial_danger": spec.initial_danger,
                                "horizon_ticks": horizon,
                                "outcome": defense_scenario_outcome(env.battle, spec),
                                "tower_loss": max(
                                    0.0,
                                    spec.initial_tower_fraction - current_fraction,
                                ),
                                "resource_loss": defense_scenario_resource_loss(
                                    env.battle,
                                    spec,
                                ),
                                "remaining_danger": incoming_tower_danger(
                                    env.battle, learner
                                ),
                            }
                        )
                        recorded.add(horizon)
                if done:
                    break
    summaries: dict[str, Any] = {}
    for controller in controllers:
        summaries[controller] = {}
        for horizon in horizons:
            selected = [
                row
                for row in rows
                if row["controller"] == controller
                and row["horizon_ticks"] == horizon
            ]
            outcomes = np.asarray([row["outcome"] for row in selected])
            tower_losses = np.asarray([row["tower_loss"] for row in selected])
            remaining = np.asarray([row["remaining_danger"] for row in selected])
            resource_losses = np.asarray(
                [row["resource_loss"] for row in selected]
            )
            summaries[controller][str(horizon)] = {
                "scenarios": len(selected),
                "failure_rate": float(np.mean(outcomes <= 0.0)),
                "mean_outcome": float(np.mean(outcomes)),
                "mean_tower_loss": float(np.mean(tower_losses)),
                "tower_damage_rate": float(np.mean(tower_losses > 0.0)),
                "mean_remaining_danger": float(np.mean(remaining)),
                "mean_resource_loss": float(np.mean(resource_losses)),
            }
    return {
        "schema_version": 2,
        "seed": seed,
        "scenarios_per_controller": scenarios,
        "horizons_ticks": list(horizons),
        "decision_interval_ticks": 8,
        "minimum_elixir": minimum_elixir,
        "maximum_elixir": maximum_elixir,
        "decks_path": str(decks_path),
        "sampling_decks_path": str(sampling_decks_path),
        "learner_sampling_decks_path": (
            str(learner_sampling_decks_path)
            if learner_sampling_decks_path is not None
            else None
        ),
        "opponent_sampling_decks_path": (
            str(opponent_sampling_decks_path)
            if opponent_sampling_decks_path is not None
            else None
        ),
        "checkpoint": str(checkpoint) if checkpoint is not None else None,
        "deterministic_policy": deterministic_policy,
        "summaries": summaries,
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1051701)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sampling-decks-path", required=True)
    parser.add_argument("--learner-sampling-decks-path")
    parser.add_argument("--opponent-sampling-decks-path")
    parser.add_argument("--horizon-ticks", type=int, action="append", default=[])
    parser.add_argument("--controller", action="append", default=[])
    parser.add_argument("--minimum-elixir", type=int, default=8)
    parser.add_argument("--maximum-elixir", type=int, default=12)
    parser.add_argument("--checkpoint")
    parser.add_argument(
        "--stochastic-policy",
        action="store_true",
        help="Sample policy actions instead of taking the deterministic mode.",
    )
    parser.add_argument("--json-out", required=True)
    args = parser.parse_args()
    controllers = tuple(args.controller or ("noop", "reactive-defense"))
    allowed = {"noop", "reactive-defense", "balanced", "policy"}
    if not set(controllers) <= allowed:
        raise ValueError(f"controllers must be drawn from {sorted(allowed)}")
    payload = run_calibration(
        scenarios=args.scenarios,
        seed=args.seed,
        decks_path=resolve_path(args.decks_path, must_exist=True),
        sampling_decks_path=resolve_path(
            args.sampling_decks_path, must_exist=True
        ),
        horizons=tuple(sorted(set(args.horizon_ticks or (160, 240, 320)))),
        controllers=controllers,
        minimum_elixir=args.minimum_elixir,
        maximum_elixir=args.maximum_elixir,
        learner_sampling_decks_path=(
            resolve_path(args.learner_sampling_decks_path, must_exist=True)
            if args.learner_sampling_decks_path
            else None
        ),
        opponent_sampling_decks_path=(
            resolve_path(args.opponent_sampling_decks_path, must_exist=True)
            if args.opponent_sampling_decks_path
            else None
        ),
        checkpoint=(
            resolve_path(args.checkpoint, must_exist=True)
            if args.checkpoint
            else None
        ),
        deterministic_policy=not args.stochastic_policy,
    )
    output = resolve_path(args.json_out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload["summaries"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
