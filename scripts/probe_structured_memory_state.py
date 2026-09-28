from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.structured_memory import StructuredBeliefCell
from clasher.rl.train_recurrent import (
    _stack_step_inputs,
    maybe_silence_stdio,
    resolve_torch_device,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _correlation(first: np.ndarray, second: np.ndarray) -> float:
    if first.size < 2 or float(first.std()) < 1e-9 or float(second.std()) < 1e-9:
        return 0.0
    return float(np.corrcoef(first, second)[0, 1])


def _metrics(predicted: list[float], actual: list[float]) -> dict[str, float]:
    prediction = np.asarray(predicted, dtype=np.float64)
    target = np.asarray(actual, dtype=np.float64)
    error = prediction - target
    return {
        "samples": float(target.size),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "correlation": _correlation(prediction, target),
        "prediction_mean": float(prediction.mean()),
        "target_mean": float(target.mean()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit model-owned structured clock and elixir state in live games"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sampling-decks-path", default=None)
    parser.add_argument("--games-per-strategy", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1062703)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--json-out", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.games_per_strategy <= 0:
        raise ValueError("games per strategy must be positive")
    torch.set_num_threads(args.torch_threads)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = resolve_torch_device(args.device)
    checkpoint_path = Path(args.checkpoint).expanduser().resolve()
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    sampling_decks_path = (
        resolve_decks_path(args.sampling_decks_path, must_exist=True)
        if args.sampling_decks_path is not None
        else None
    )
    output_path = Path(args.json_out).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    loaded = load_policy_checkpoint(
        checkpoint_path,
        device=device,
        decks_path=decks_path,
    )
    model = loaded.model
    if model.config.memory_kind != "structured":
        raise ValueError("checkpoint does not use structured memory")
    if not isinstance(model.memory, StructuredBeliefCell):
        raise TypeError("structured checkpoint did not construct StructuredBeliefCell")

    clock_predictions: list[float] = []
    clock_targets: list[float] = []
    elixir_predictions: list[float] = []
    elixir_targets: list[float] = []
    games: list[dict[str, Any]] = []
    started = time.perf_counter()
    game_index = 0

    for strategy_name in STRATEGY_NAMES:
        for repetition in range(args.games_per_strategy):
            matchup_seed = args.seed + game_index * 1009
            env = SelfPlayBattleEnv(
                decision_interval_ticks=args.decision_interval,
                max_ticks=args.max_ticks,
                decks_path=decks_path,
                sampling_decks_path=sampling_decks_path,
                seed=matchup_seed,
                canonical_perspective=True,
                canonical_lane_globals=model.config.canonical_lane_globals,
            )
            with maybe_silence_stdio(True):
                env.reset(seed=matchup_seed)
            candidate_player = repetition % 2
            opponent_player = 1 - candidate_player
            opponent = StrategyBot(strategy_name)
            state = model.initial_state(1, device=device)
            previous_action = env.action_space.no_op_action
            previous_reward = 0.0
            episode_start = True
            decision = 0
            done = False
            game_elixir_prediction: list[float] = []
            game_elixir_target: list[float] = []

            while not done:
                assert env.battle is not None
                observation = env.get_structured_observation(
                    candidate_player,
                    actor_observation_domain=model.config.actor_observation_domain,
                )
                candidate_mask = env.get_action_mask(
                    candidate_player,
                    actor_observation_domain=model.config.actor_observation_domain,
                    structured_observation=observation,
                )
                inputs = _stack_step_inputs(
                    [observation],
                    candidate_mask[None, :],
                    np.asarray([previous_action], dtype=np.int64),
                    np.asarray([previous_reward], dtype=np.float32),
                    np.asarray([episode_start], dtype=np.bool_),
                    device,
                    public_observation_confidence=(
                        model.config.public_observation_confidence
                    ),
                )
                with torch.no_grad():
                    action_tensor, _, _, state, output = model.act(
                        inputs,
                        state,
                        deterministic=True,
                    )
                action = int(action_tensor[0, 0].item())
                predicted_clock = float(
                    state[0][0, StructuredBeliefCell.CLOCK_INDEX].item()
                )
                expected_clock = min(
                    (decision + 1) / model.config.structured_clock_horizon_steps,
                    2.0,
                )
                predicted_elixir = float(output.opponent_elixir[0, 0].item())
                actual_elixir = (
                    float(env.battle.players[opponent_player].elixir) / 10.0
                )
                clock_predictions.append(predicted_clock)
                clock_targets.append(expected_clock)
                elixir_predictions.append(predicted_elixir)
                elixir_targets.append(actual_elixir)
                game_elixir_prediction.append(predicted_elixir)
                game_elixir_target.append(actual_elixir)

                opponent_mask = env.get_action_mask(opponent_player)
                opponent_action = opponent.select_action(
                    env,
                    opponent_player,
                    action_mask=opponent_mask,
                )
                with maybe_silence_stdio(True):
                    rewards, done, _ = env.step(
                        {
                            candidate_player: action,
                            opponent_player: opponent_action,
                        },
                        pre_action_masks={
                            candidate_player: candidate_mask,
                            opponent_player: opponent_mask,
                        },
                    )
                previous_action = action
                previous_reward = float(rewards[candidate_player])
                episode_start = False
                decision += 1

            games.append(
                {
                    "strategy": strategy_name,
                    "seed": matchup_seed,
                    "candidate_player": candidate_player,
                    "decisions": decision,
                    "winner": env.battle.winner if env.battle is not None else None,
                    "opponent_elixir": _metrics(
                        game_elixir_prediction,
                        game_elixir_target,
                    ),
                }
            )
            game_index += 1

    payload = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_sha256": _sha256(checkpoint_path),
        "actor_observation_domain": model.config.actor_observation_domain,
        "memory_kind": model.config.memory_kind,
        "memory_size": model.config.memory_size,
        "clock_horizon_steps": model.config.structured_clock_horizon_steps,
        "games": games,
        "clock": _metrics(clock_predictions, clock_targets),
        "opponent_elixir": _metrics(elixir_predictions, elixir_targets),
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
