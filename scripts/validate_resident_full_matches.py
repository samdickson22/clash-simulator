"""Validate complete resident Gym episodes and within-profile determinism."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import torch

from clasher.battle import STANDARD_MATCH_TICKS, BattleState
from clasher.rl.deck_pool import load_deck_pool
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.policy_validation import PROJECTED_GYM_TRANSITION_PROFILE
from clasher.torch_sim.resident_selfplay import (
    ResidentGymTransitionInputs,
    TensorResidentSelfPlay,
)
from clasher.torch_sim.runtime_state import (
    RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    RESIDENT_EXECUTION_PROFILE_GYM_FAST,
    RESIDENT_EXECUTION_PROFILES,
)


@dataclass(frozen=True)
class EpisodeSummary:
    seed: int
    policy: str
    decisions: int
    requested_native_ticks: int
    native_ticks: int
    fallback_rows: int
    final_tick: int
    final_time: float
    done: bool
    winner: int
    reached_regulation_end: bool
    entered_overtime: bool
    reached_tiebreak: bool
    terminal_reason: str
    digest: str


def _battle(seed: int, decks: list[list[str]]) -> BattleState:
    rng = random.Random(seed)
    battle = BattleState(fast_path=False, rng=rng)
    for player in battle.players:
        deck = list(rng.choice(decks))
        rng.shuffle(deck)
        player.hand = cast(list[str | None], deck[:4])
        player.deck = list(deck)
        player.cycle_queue = deque(deck[4:])
        player.elixir = 5.0
    return battle


def _actions(mask: torch.Tensor, policy: str) -> torch.Tensor:
    batch, seats, action_count = mask.shape
    if policy == "noop":
        return torch.full(
            (batch, seats),
            NO_OP_ACTION,
            dtype=torch.int64,
            device=mask.device,
        )
    indices = torch.arange(action_count, dtype=torch.int64, device=mask.device)
    candidates = torch.where(
        mask & (indices != NO_OP_ACTION),
        indices,
        torch.full_like(indices, action_count),
    )
    selected = candidates.amin(dim=2)
    return torch.where(
        selected < action_count,
        selected,
        torch.full_like(selected, NO_OP_ACTION),
    )


def _update_digest(digest: hashlib._Hash, value: torch.Tensor) -> None:
    cpu = value.detach().contiguous().cpu()
    digest.update(str(cpu.dtype).encode())
    digest.update(str(tuple(cpu.shape)).encode())
    digest.update(cpu.numpy().tobytes())


def _run_once(
    *,
    seed: int,
    decks: list[list[str]],
    policy: str,
    device: str,
    max_ticks: int,
    decision_interval: int,
    max_entities: int,
    max_objects: int,
    execution_profile: str = RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
) -> EpisodeSummary:
    battle = _battle(seed, decks)
    bridge = TensorResidentSelfPlay.from_battles(
        [battle],
        device=device,
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        max_entities=max_entities,
        max_objects=max_objects,
        event_capacity=(
            1
            if execution_profile == RESIDENT_EXECUTION_PROFILE_GYM_FAST
            else 1_024
        ),
        execution_profile=execution_profile,
        validation_profile=PROJECTED_GYM_TRANSITION_PROFILE,
    )
    previous_actions = torch.full(
        (1, 2), NO_OP_ACTION, dtype=torch.int64, device=bridge.device
    )
    previous_rewards = torch.zeros((1, 2), dtype=torch.float32, device=bridge.device)
    episode_starts = torch.ones((1, 2), dtype=torch.bool, device=bridge.device)
    digest = hashlib.sha256()
    native_ticks = 0
    requested_native_ticks = 0
    decisions = 0
    fallback_rows = 0
    done = False
    winner = -1

    while not done:
        _, _, legal = bridge.observe()
        actions = _actions(legal, policy)
        result = bridge.step(
            actions,
            validation_inputs=ResidentGymTransitionInputs(
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_starts=episode_starts,
            ),
        )
        if result.validation is None:
            raise RuntimeError("projected Gym validation boundary is missing")
        metadata = result.validation.metadata
        if not metadata.all_rows_admitted:
            raise RuntimeError("resident episode lost native admission")
        requested_native_ticks += int(metadata.requested_native_ticks.sum().item())
        native_ticks += int(metadata.native_ticks.sum().item())
        fallback_rows += len(metadata.fallback_rows)
        transition = result.validation.transition
        for tensor in (
            transition.actor.entity_ids,
            transition.actor.entity_features,
            transition.actor.entity_mask,
            transition.actor.hand_ids,
            transition.actor.global_features,
            result.action_masks,
            transition.action_success,
            transition.rewards,
            transition.done,
            transition.winner,
            transition.previous_actions,
            transition.previous_rewards,
            transition.episode_starts,
        ):
            _update_digest(digest, torch.as_tensor(tensor))
        previous_actions = actions.clone()
        previous_rewards = result.rewards.to(torch.float32).clone()
        episode_starts.zero_()
        decisions += 1
        done = bool(result.dones[0].item())
        winner = int(result.reward_outcome.winner[0].item())
        if decisions > (max_ticks + decision_interval - 1) // decision_interval + 1:
            raise RuntimeError("resident episode exceeded its decision budget")

    state = bridge.engine.runtime.battle
    final_tick = int(state.tick[0].item())
    final_time = float(state.time[0].item())
    game_over = bool(state.game_over[0].item())
    entered_overtime = bool(state.sudden_death[0].item())
    overtime_start_time = float(state.overtime_start_time[0].item())
    tiebreaker_time = float(state.tiebreaker_time[0].item())
    reached_regulation_end = final_time >= overtime_start_time
    reached_tiebreak = final_time >= tiebreaker_time
    if reached_tiebreak and game_over:
        terminal_reason = "tiebreak"
    elif entered_overtime and game_over:
        terminal_reason = "overtime_crown"
    elif game_over:
        terminal_reason = "regulation_crown"
    elif final_tick >= max_ticks:
        terminal_reason = "configured_tick_limit"
    else:
        terminal_reason = "unknown"

    return EpisodeSummary(
        seed=seed,
        policy=policy,
        decisions=decisions,
        requested_native_ticks=requested_native_ticks,
        native_ticks=native_ticks,
        fallback_rows=fallback_rows,
        final_tick=final_tick,
        final_time=final_time,
        done=done,
        winner=winner,
        reached_regulation_end=reached_regulation_end,
        entered_overtime=entered_overtime,
        reached_tiebreak=reached_tiebreak,
        terminal_reason=terminal_reason,
        digest=digest.hexdigest(),
    )


def validate(args: argparse.Namespace) -> dict[str, object]:
    decks = [list(deck) for deck in load_deck_pool(args.decks_path)]
    summaries: list[EpisodeSummary] = []
    replay_count = int(getattr(args, "replays", 2))
    require_tiebreak = bool(getattr(args, "require_tiebreak", False))
    if replay_count < 2:
        raise ValueError("deterministic validation requires at least two replays")
    if require_tiebreak and args.max_ticks < STANDARD_MATCH_TICKS:
        raise ValueError(
            "tiebreak validation requires max_ticks >= STANDARD_MATCH_TICKS"
        )
    for policy in args.policy:
        for seed in args.seed:
            replays = [
                _run_once(
                    seed=seed,
                    decks=decks,
                    policy=policy,
                    device=args.device,
                    max_ticks=args.max_ticks,
                    decision_interval=args.decision_interval,
                    max_entities=args.max_entities,
                    max_objects=args.max_objects,
                    execution_profile=getattr(
                        args,
                        "execution_profile",
                        RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
                    ),
                )
                for _ in range(replay_count)
            ]
            first = replays[0]
            if any(replay != first for replay in replays[1:]):
                raise RuntimeError(
                    f"resident replay is nondeterministic for seed={seed} policy={policy}"
                )
            if (
                first.fallback_rows
                or first.native_ticks != first.requested_native_ticks
                or first.native_ticks != first.final_tick
            ):
                raise RuntimeError(
                    f"resident episode is not fully native for seed={seed} policy={policy}"
                )
            if not first.done or first.terminal_reason == "unknown":
                raise RuntimeError(
                    f"resident episode did not reach a terminal boundary for "
                    f"seed={seed} policy={policy}"
                )
            if require_tiebreak and not (
                first.reached_regulation_end
                and first.entered_overtime
                and first.reached_tiebreak
                and first.terminal_reason == "tiebreak"
            ):
                raise RuntimeError(
                    f"resident episode did not traverse regulation, overtime, "
                    f"and tiebreak for seed={seed} policy={policy}"
                )
            summaries.append(first)
    return {
        "schema_version": 2,
        "profile": PROJECTED_GYM_TRANSITION_PROFILE,
        "device": args.device,
        "max_ticks": args.max_ticks,
        "decision_interval": args.decision_interval,
        "execution_profile": getattr(
            args,
            "execution_profile",
            RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
        ),
        "replays": replay_count,
        "acceptance": {
            "deterministic_replay": True,
            "all_requested_ticks_native": True,
            "zero_fallback": True,
            "terminal_boundary_reached": True,
            "required_tiebreak_timeline_reached": (
                True if require_tiebreak else None
            ),
            "python_parity_evaluated": False,
        },
        "requirements": {"tiebreak_timeline": require_tiebreak},
        "episodes": [asdict(summary) for summary in summaries],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-objects", type=int, default=128)
    parser.add_argument(
        "--execution-profile",
        choices=sorted(RESIDENT_EXECUTION_PROFILES),
        default=RESIDENT_EXECUTION_PROFILE_EXACT_DEBUG,
    )
    parser.add_argument(
        "--replays",
        type=int,
        default=2,
        help="identical executions required per seed/policy (minimum: 2)",
    )
    parser.add_argument(
        "--require-tiebreak",
        action="store_true",
        help="require every replay to traverse regulation, overtime, and tiebreak",
    )
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument(
        "--policy", choices=("noop", "first-legal"), action="append", default=[]
    )
    parser.add_argument("--out", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.seed:
        args.seed = [202_608_260]
    if not args.policy:
        args.policy = ["noop", "first-legal"]
    if min(
        args.max_ticks,
        args.decision_interval,
        args.max_entities,
        args.max_objects,
        args.replays,
    ) < 1:
        raise ValueError("tick intervals and capacities must be positive")
    result = validate(args)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(encoded, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
