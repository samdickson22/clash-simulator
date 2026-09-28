#!/usr/bin/env python3
"""Measure stochastic policy temperatures against deterministic gameplay."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import torch
from torch.distributions import Categorical

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import evaluate, load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyInputs, PolicyOutput
from clasher.rl.strategy_bots import StrategyBot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, required=True)
    parser.add_argument("--candidate-decks", type=Path, required=True)
    parser.add_argument("--opponent-decks", type=Path, required=True)
    parser.add_argument("--games", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1192401)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--temperature",
        action="append",
        type=float,
        dest="temperatures",
    )
    parser.add_argument("--hazard-gated", action="store_true")
    return parser.parse_args()


def hierarchical_tempered_distribution(
    output: PolicyOutput, *, temperature: float
) -> Categorical:
    """Temper play/wait, slot, and tile factors without flattening bias."""
    if temperature == 1.0:
        return Categorical(logits=output.joint_logits)
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    placement_mask = output.joint_logits[..., :placement_actions].reshape(
        *output.joint_logits.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    ) > -1e8
    slot_mask = placement_mask.any(dim=-1)
    special_mask = output.joint_logits[..., placement_actions:] > -1e8
    type_mask = torch.cat([slot_mask, special_mask], dim=-1)
    timing_logits = (
        output.action_type_logits
        if output.deterministic_timing_logits is None
        else output.deterministic_timing_logits
    )
    masked_timing = timing_logits.masked_fill(~type_mask, -1e9)
    play_logit = torch.logsumexp(
        masked_timing[..., :NUM_HAND_SLOTS], dim=-1, keepdim=True
    )
    mode_mask = torch.cat(
        [slot_mask.any(dim=-1, keepdim=True), special_mask], dim=-1
    )
    mode_logits = torch.cat(
        [play_logit, masked_timing[..., NUM_HAND_SLOTS:]], dim=-1
    )
    mode_log_prob = torch.log_softmax(
        (mode_logits / temperature).masked_fill(~mode_mask, -1e9), dim=-1
    ).masked_fill(~mode_mask, -1e9)
    slot_log_prob = torch.log_softmax(
        (output.action_type_logits[..., :NUM_HAND_SLOTS] / temperature).masked_fill(
            ~slot_mask, -1e9
        ),
        dim=-1,
    ).masked_fill(~slot_mask, -1e9)
    location_log_prob = torch.log_softmax(
        (output.location_logits / temperature).masked_fill(~placement_mask, -1e9),
        dim=-1,
    ).masked_fill(~placement_mask, -1e9)
    placement_log_prob = (
        mode_log_prob[..., :1].unsqueeze(-1)
        + slot_log_prob.unsqueeze(-1)
        + location_log_prob
    )
    joint_log_prob = torch.cat(
        [
            placement_log_prob.reshape(*output.joint_logits.shape[:-1], -1),
            mode_log_prob[..., 1:],
        ],
        dim=-1,
    )
    joint_mask = torch.cat(
        [
            placement_mask.reshape(*output.joint_logits.shape[:-1], -1),
            special_mask,
        ],
        dim=-1,
    )
    return Categorical(logits=joint_log_prob.masked_fill(~joint_mask, -1e9))


def hazard_gated_distribution(
    output: PolicyOutput,
    action_mask: torch.Tensor,
    force_play: torch.Tensor,
    *,
    temperature: float,
) -> Categorical:
    """Sample within the recurrent hazard gate selected by deterministic decode."""
    placement_actions = NUM_HAND_SLOTS * NUM_TILES
    placement_mask = action_mask[..., :placement_actions].reshape(
        *action_mask.shape[:-1], NUM_HAND_SLOTS, NUM_TILES
    )
    slot_mask = placement_mask.any(dim=-1)
    special_mask = action_mask[..., placement_actions:]
    timing_logits = (
        output.action_type_logits
        if output.deterministic_timing_logits is None
        else output.deterministic_timing_logits
    )
    slot_log_prob = torch.log_softmax(
        (output.action_type_logits[..., :NUM_HAND_SLOTS] / temperature).masked_fill(
            ~slot_mask, -1e9
        ),
        dim=-1,
    ).masked_fill(~slot_mask, -1e9)
    location_log_prob = torch.log_softmax(
        (output.location_logits / temperature).masked_fill(~placement_mask, -1e9),
        dim=-1,
    ).masked_fill(~placement_mask, -1e9)
    special_log_prob = torch.log_softmax(
        (timing_logits[..., NUM_HAND_SLOTS:] / temperature).masked_fill(
            ~special_mask, -1e9
        ),
        dim=-1,
    ).masked_fill(~special_mask, -1e9)
    placement_log_prob = slot_log_prob.unsqueeze(-1) + location_log_prob
    logits = torch.cat(
        [
            placement_log_prob.reshape(*action_mask.shape[:-1], -1),
            special_log_prob,
        ],
        dim=-1,
    )
    gated_mask = torch.where(
        force_play.unsqueeze(-1),
        torch.cat(
            [
                placement_mask.reshape(*action_mask.shape[:-1], -1),
                torch.zeros_like(special_mask),
            ],
            dim=-1,
        ),
        torch.cat(
            [
                torch.zeros_like(
                    placement_mask.reshape(*action_mask.shape[:-1], -1)
                ),
                special_mask,
            ],
            dim=-1,
        ),
    )
    return Categorical(logits=logits.masked_fill(~gated_mask, -1e9))


def main() -> None:
    args = parse_args()
    temperatures = args.temperatures or [1.0, 0.75, 0.5, 0.35, 0.25, 0.15, 0.1]
    if args.games <= 0:
        raise ValueError("games must be positive")
    if any(not 0.0 < value <= 1.0 for value in temperatures):
        raise ValueError("temperatures must be in (0, 1]")

    device = torch.device("cpu")
    candidate = load_policy_checkpoint(
        args.checkpoint.resolve(),
        device=device,
        decks_path=args.decks_path.resolve(),
    )
    original: Callable[[PolicyOutput], Categorical] = PolicyOutput.distribution
    original_act = ClasherPolicy.act
    rows: list[dict[str, object]] = []
    try:
        arms: list[tuple[str, float | None]] = [("deterministic", None)]
        arms.extend((f"temperature-{value:g}", value) for value in temperatures)
        for arm_index, (label, temperature) in enumerate(arms):
            if temperature is None:
                PolicyOutput.distribution = original
                ClasherPolicy.act = original_act
            else:
                def tempered_distribution(
                    output: PolicyOutput,
                    *,
                    _temperature: float = temperature,
                ) -> Categorical:
                    return hierarchical_tempered_distribution(
                        output, temperature=_temperature
                    )

                PolicyOutput.distribution = tempered_distribution
                if args.hazard_gated:

                    @torch.no_grad()
                    def gated_act(
                        model: ClasherPolicy,
                        inputs: PolicyInputs,
                        state: tuple[torch.Tensor, torch.Tensor] | None = None,
                        *,
                        deterministic: bool = False,
                        _temperature: float = temperature,
                    ) -> tuple[
                        torch.Tensor,
                        torch.Tensor,
                        torch.Tensor,
                        tuple[torch.Tensor, torch.Tensor],
                        PolicyOutput,
                    ]:
                        if deterministic or not model.config.play_hazard_enabled:
                            return original_act(
                                model, inputs, state, deterministic=deterministic
                            )
                        output = model.forward(inputs, state)
                        previous_hazard = output.next_state[0][:, -1]
                        force_play, stored_hazard = model._play_hazard_force_gate(
                            output,
                            inputs.action_mask,
                            previous_hazard,
                        )
                        distribution = hazard_gated_distribution(
                            output,
                            inputs.action_mask,
                            force_play,
                            temperature=_temperature,
                        )
                        actions = distribution.sample()
                        next_hidden = output.next_state[0].clone()
                        next_hidden[:, -1] = stored_hazard
                        next_state = (next_hidden, output.next_state[1])
                        output = replace(output, next_state=next_state)
                        return (
                            actions,
                            distribution.log_prob(actions),
                            output.values,
                            next_state,
                            output,
                        )

                    ClasherPolicy.act = gated_act
            for opponent_index, opponent_name in enumerate(("balanced", "random")):
                game_records: list[dict[str, object]] = []
                metrics = evaluate(
                    candidate=candidate,
                    decks_path=args.decks_path.resolve(),
                    games=args.games,
                    seed=args.seed + opponent_index,
                    decision_interval=8,
                    max_ticks=6000,
                    opponent_mode=("strategy" if opponent_name == "balanced" else "random"),
                    opponent=None,
                    deterministic=temperature is None,
                    quiet_engine=True,
                    device=device,
                    sampling_decks_path=args.opponent_decks.resolve(),
                    candidate_sampling_decks_path=args.candidate_decks.resolve(),
                    opponent_sampling_decks_path=args.opponent_decks.resolve(),
                    reward_profile="objective-v1",
                    opponent_bot=(
                        StrategyBot("balanced") if opponent_name == "balanced" else None
                    ),
                    game_records=game_records,
                )
                rows.append(
                    {
                        "arm": label,
                        "temperature": temperature,
                        "opponent": opponent_name,
                        "seed": args.seed + opponent_index,
                        "metrics": metrics,
                        "games": game_records,
                    }
                )
    finally:
        PolicyOutput.distribution = original
        ClasherPolicy.act = original_act

    summary: list[dict[str, object]] = []
    for label in dict.fromkeys(str(row["arm"]) for row in rows):
        selected = [row for row in rows if row["arm"] == label]
        metrics = [row["metrics"] for row in selected]
        summary.append(
            {
                "arm": label,
                "temperature": selected[0]["temperature"],
                "games": sum(int(item["games"]) for item in metrics),
                "wins": sum(int(item["wins"]) for item in metrics),
                "losses": sum(int(item["losses"]) for item in metrics),
                "draws": sum(int(item["draws"]) for item in metrics),
                "crown_diff_per_game": sum(
                    float(item["crown_diff_per_game"]) * int(item["games"])
                    for item in metrics
                )
                / sum(int(item["games"]) for item in metrics),
                "placement_rate": sum(
                    float(item["candidate_placement_rate"]) for item in metrics
                )
                / len(metrics),
            }
        )

    payload = {
        "schema": "clasher.hog26.sampling-temperature-screen.v1",
        "checkpoint": str(args.checkpoint.resolve()),
        "games_per_opponent": args.games,
        "opponents": ["balanced", "random"],
        "hazard_gated": args.hazard_gated,
        "rows": rows,
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
