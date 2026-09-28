from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import _policy_step, load_policy_checkpoint
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import BALANCED, StrategyBot
from clasher.rl.train_recurrent import maybe_silence_stdio, resolve_torch_device

GLOBAL_FEATURE_NAMES = (
    "progress",
    "remaining",
    "double_elixir",
    "triple_elixir",
    "overtime",
    "own_elixir",
    "own_crowns",
    "enemy_crowns",
    "own_left_tower_hp",
    "own_right_tower_hp",
    "own_king_tower_hp",
    "enemy_left_tower_hp",
    "enemy_right_tower_hp",
    "enemy_king_tower_hp",
    "ability_cooldown",
    "ability_duration",
    "next_card_refill_cooldown",
    "enemy_king_alive",
)

ENTITY_FEATURE_NAMES = (
    "x",
    "y",
    "own",
    "enemy",
    "troop",
    "building",
    "projectile",
    "spell_effect",
    "other",
    "hp_fraction",
    "shield_fraction",
    "airborne",
    "placement_pending",
    "deployment_progress",
    "stun",
    "slow",
    "haste",
    "special_move",
    "stealth",
    "hidden_building",
    "forced_movement",
    "attack_windup",
    "charging",
    "speed",
    "range",
    "sight_range",
    "collision_radius",
    "facing_x",
    "facing_y",
    "effect_progress",
    "damage",
    "tower_active",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare visual TV Royale observations with live simulator states"
    )
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sampling-decks-path")
    parser.add_argument("--output", required=True)
    parser.add_argument("--observations", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=1_047_801)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    return parser.parse_args()


def _quantiles(values: np.ndarray) -> dict[str, float]:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "p00": float(np.min(values)),
        "p10": float(np.quantile(values, 0.10)),
        "p50": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p100": float(np.max(values)),
        "zero_rate": float(np.mean(values == 0.0)),
        "one_rate": float(np.mean(values == 1.0)),
    }


def _js_divergence(left: np.ndarray, right: np.ndarray, *, bins: int = 32) -> float:
    left = np.asarray(left, dtype=np.float64).reshape(-1)
    right = np.asarray(right, dtype=np.float64).reshape(-1)
    lower = min(float(np.min(left)), float(np.min(right)))
    upper = max(float(np.max(left)), float(np.max(right)))
    if not math.isfinite(lower) or not math.isfinite(upper):
        raise ValueError("domain audit inputs must be finite")
    if lower == upper:
        return 0.0
    left_hist, edges = np.histogram(left, bins=bins, range=(lower, upper))
    right_hist, _ = np.histogram(right, bins=edges)
    left_prob = left_hist.astype(np.float64) + 1e-12
    right_prob = right_hist.astype(np.float64) + 1e-12
    left_prob /= left_prob.sum()
    right_prob /= right_prob.sum()
    middle = 0.5 * (left_prob + right_prob)
    return float(
        0.5 * np.sum(left_prob * np.log2(left_prob / middle))
        + 0.5 * np.sum(right_prob * np.log2(right_prob / middle))
    )


def _feature_comparison(
    visual: np.ndarray,
    live: np.ndarray,
    names: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    if visual.shape[1] != live.shape[1] or visual.shape[1] != len(names):
        raise ValueError("feature widths do not match their names")
    return {
        name: {
            "js_divergence_bits": _js_divergence(visual[:, index], live[:, index]),
            "visual": _quantiles(visual[:, index]),
            "live": _quantiles(live[:, index]),
        }
        for index, name in enumerate(names)
    }


def _masked_entity_rows(features: np.ndarray, masks: np.ndarray) -> np.ndarray:
    rows = np.asarray(features, dtype=np.float32)[np.asarray(masks, dtype=np.bool_)]
    if rows.size == 0:
        raise ValueError("observation set contains no visible entities")
    return rows


def _token_distribution(ids: np.ndarray, masks: np.ndarray, width: int) -> np.ndarray:
    selected = np.asarray(ids, dtype=np.int64)[np.asarray(masks, dtype=np.bool_)]
    return np.bincount(selected, minlength=width).astype(np.float64)


def _categorical_js(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64) + 1e-12
    right = np.asarray(right, dtype=np.float64) + 1e-12
    left /= left.sum()
    right /= right.sum()
    middle = 0.5 * (left + right)
    return float(
        0.5 * np.sum(left * np.log2(left / middle))
        + 0.5 * np.sum(right * np.log2(right / middle))
    )


def _load_visual_rows(
    path: Path, *, observations: int, seed: int
) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as payload:
        total = int(payload["entity_ids"].shape[0])
        if total == 0:
            raise ValueError("visual corpus is empty")
        count = min(total, observations)
        indices = np.random.default_rng(seed).choice(total, size=count, replace=False)
        return {
            name: np.asarray(payload[name][indices])
            for name in (
                "entity_ids",
                "entity_features",
                "entity_mask",
                "hand_ids",
                "global_features",
                "action_masks",
                "expert_actions",
            )
        }


@torch.no_grad()
def _collect_live_rows(
    *,
    checkpoint: Path,
    decks_path: Path,
    sampling_decks_path: Path | None,
    observations: int,
    seed: int,
    device: torch.device,
    decision_interval: int,
    max_ticks: int,
) -> dict[str, np.ndarray]:
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks_path,
        canonical_perspective=True,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
        seed=seed,
    )
    opponent = StrategyBot(BALANCED)
    records: dict[str, list[np.ndarray | float | int]] = {
        "entity_ids": [],
        "entity_features": [],
        "entity_mask": [],
        "hand_ids": [],
        "global_features": [],
        "action_masks": [],
        "actions": [],
        "play_probabilities": [],
    }
    game = 0
    while len(records["actions"]) < observations:
        matchup_seed = seed + game * 1009
        with maybe_silence_stdio(True):
            env.reset(seed=matchup_seed)
        player_id = game % 2
        opponent_id = 1 - player_id
        state = loaded.model.initial_state(1, device=device)
        previous_action = env.action_space.no_op_action
        previous_reward = 0.0
        episode_start = True
        done = False
        while not done and len(records["actions"]) < observations:
            assert env.battle is not None
            actor = loaded.builder.build_actor(env.battle, player_id)
            action, state, action_mask, output = _policy_step(
                loaded,
                env,
                player_id,
                state=state,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
                deterministic=True,
                device=device,
            )
            probabilities = torch.softmax(output.action_type_logits[0, 0], dim=-1)
            opponent_mask = env.get_action_mask(opponent_id)
            opponent_action = opponent.select_action(
                env, opponent_id, action_mask=opponent_mask
            )
            records["entity_ids"].append(actor.entity_ids.copy())
            records["entity_features"].append(actor.entity_features.copy())
            records["entity_mask"].append(actor.entity_mask.copy())
            records["hand_ids"].append(actor.hand_ids.copy())
            records["global_features"].append(actor.global_features.copy())
            records["action_masks"].append(action_mask.copy())
            records["actions"].append(action)
            records["play_probabilities"].append(float(1.0 - probabilities[4]))
            with maybe_silence_stdio(True):
                rewards, done, _ = env.step(
                    {player_id: action, opponent_id: opponent_action},
                    pre_action_masks={
                        player_id: action_mask,
                        opponent_id: opponent_mask,
                    },
                )
            previous_action = action
            previous_reward = float(rewards[player_id])
            episode_start = False
        game += 1
    return {name: np.asarray(values) for name, values in records.items()}


def build_report(
    visual: dict[str, np.ndarray],
    live: dict[str, np.ndarray],
    *,
    token_count: int,
    unknown_token_id: int,
    no_op_action: int,
) -> dict[str, Any]:
    visual_entity_rows = _masked_entity_rows(
        visual["entity_features"], visual["entity_mask"]
    )
    live_entity_rows = _masked_entity_rows(live["entity_features"], live["entity_mask"])
    global_features = _feature_comparison(
        np.asarray(visual["global_features"], dtype=np.float32),
        np.asarray(live["global_features"], dtype=np.float32),
        GLOBAL_FEATURE_NAMES,
    )
    entity_features = _feature_comparison(
        visual_entity_rows,
        live_entity_rows,
        ENTITY_FEATURE_NAMES,
    )
    visual_tokens = _token_distribution(
        visual["entity_ids"], visual["entity_mask"], token_count
    )
    live_tokens = _token_distribution(live["entity_ids"], live["entity_mask"], token_count)
    visual_counts = np.count_nonzero(visual["entity_mask"], axis=1)
    live_counts = np.count_nonzero(live["entity_mask"], axis=1)
    visual_legal = np.count_nonzero(visual["action_masks"], axis=1)
    live_legal = np.count_nonzero(live["action_masks"], axis=1)
    visual_expert = np.asarray(visual["expert_actions"], dtype=np.int64)
    live_actions = np.asarray(live["actions"], dtype=np.int64)
    top_global = sorted(
        (
            {"name": name, "js_divergence_bits": row["js_divergence_bits"]}
            for name, row in global_features.items()
        ),
        key=lambda row: float(row["js_divergence_bits"]),
        reverse=True,
    )
    top_entity = sorted(
        (
            {"name": name, "js_divergence_bits": row["js_divergence_bits"]}
            for name, row in entity_features.items()
        ),
        key=lambda row: float(row["js_divergence_bits"]),
        reverse=True,
    )
    visual_selected_ids = visual["entity_ids"][visual["entity_mask"]]
    live_selected_ids = live["entity_ids"][live["entity_mask"]]
    return {
        "schema_version": 1,
        "visual_observations": int(visual["entity_ids"].shape[0]),
        "live_observations": int(live["entity_ids"].shape[0]),
        "summary": {
            "entity_count": {
                "js_divergence_bits": _js_divergence(visual_counts, live_counts),
                "visual": _quantiles(visual_counts),
                "live": _quantiles(live_counts),
            },
            "legal_action_count": {
                "js_divergence_bits": _js_divergence(visual_legal, live_legal),
                "visual": _quantiles(visual_legal),
                "live": _quantiles(live_legal),
            },
            "entity_token_js_divergence_bits": _categorical_js(
                visual_tokens, live_tokens
            ),
            "unknown_entity_rate": {
                "visual": float(np.mean(visual_selected_ids == unknown_token_id)),
                "live": float(np.mean(live_selected_ids == unknown_token_id)),
            },
            "next_card_known_rate": {
                "visual": float(np.mean(visual["hand_ids"][:, 4] != 0)),
                "live": float(np.mean(live["hand_ids"][:, 4] != 0)),
            },
            "labeled_or_chosen_play_rate": {
                "visual": float(np.mean(visual_expert != no_op_action)),
                "live": float(np.mean(live_actions != no_op_action)),
            },
            "live_policy_play_probability": _quantiles(
                np.asarray(live["play_probabilities"], dtype=np.float64)
            ),
            "mean_global_js_divergence_bits": float(
                np.mean(
                    [row["js_divergence_bits"] for row in global_features.values()]
                )
            ),
            "mean_entity_js_divergence_bits": float(
                np.mean(
                    [row["js_divergence_bits"] for row in entity_features.values()]
                )
            ),
            "top_global_divergences": top_global[:8],
            "top_entity_divergences": top_entity[:12],
        },
        "global_features": global_features,
        "entity_features": entity_features,
    }


def main() -> None:
    args = parse_args()
    if args.observations <= 0:
        raise ValueError("--observations must be positive")
    device = resolve_torch_device(args.device)
    checkpoint = Path(args.checkpoint).resolve()
    decks_path = Path(args.decks_path).resolve()
    sampling_path = (
        None
        if args.sampling_decks_path is None
        else Path(args.sampling_decks_path).resolve()
    )
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    visual = _load_visual_rows(
        Path(args.corpus).resolve(), observations=args.observations, seed=args.seed
    )
    live = _collect_live_rows(
        checkpoint=checkpoint,
        decks_path=decks_path,
        sampling_decks_path=sampling_path,
        observations=args.observations,
        seed=args.seed,
        device=device,
        decision_interval=args.decision_interval,
        max_ticks=args.max_ticks,
    )
    report = build_report(
        visual,
        live,
        token_count=len(loaded.builder.token_names),
        unknown_token_id=loaded.builder.token_id(None),
        no_op_action=NUM_HAND_SLOTS * NUM_TILES,
    )
    report["inputs"] = {
        "corpus": str(Path(args.corpus).resolve()),
        "checkpoint": str(checkpoint),
        "decks_path": str(decks_path),
        "sampling_decks_path": None if sampling_path is None else str(sampling_path),
        "seed": args.seed,
        "device": str(device),
        "decision_interval": args.decision_interval,
        "max_ticks": args.max_ticks,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    print(f"report={output}")


if __name__ == "__main__":
    main()
