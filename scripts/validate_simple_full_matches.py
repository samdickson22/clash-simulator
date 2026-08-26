#!/usr/bin/env python3
"""Validate deterministic, fully native episodes in the practical tensor Gym.

The validator deliberately does not compare against the scalar Python battle.
It constructs :class:`SimpleGymRuntime` from the serialized card catalog, then
checks the training-facing transition boundary itself: actions, projections,
rewards, outcomes, commit flags, and native-tick accounting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import torch

from clasher.data import CardDataLoader
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.torch_sim.actions import NO_OP_ACTION
from clasher.torch_sim.simple_outcomes import FastMatchRules
from clasher.torch_sim.simple_runtime import SimpleGymRuntime, SimpleGymRuntimeStep
from clasher.torch_sim.simple_standard import (
    STANDARD_DOUBLE_ELIXIR_TICK,
    STANDARD_REGULATION_TICK,
    STANDARD_TIEBREAK_TICK,
    STANDARD_TRIPLE_ELIXIR_TICK,
    SimpleStandardSetup,
    compile_standard_simple_setup,
)


# Backwards-compatible script names. The production values now come from the
# same standard setup authority used by training-facing runtime construction.
EXACT_DOUBLE_ELIXIR_TICKS = STANDARD_DOUBLE_ELIXIR_TICK
EXACT_REGULATION_TICKS = STANDARD_REGULATION_TICK
EXACT_TRIPLE_ELIXIR_TICKS = STANDARD_TRIPLE_ELIXIR_TICK
EXACT_TIEBREAK_TICKS = STANDARD_TIEBREAK_TICK


@dataclass(frozen=True)
class SimpleEpisodeSummary:
    seed: int
    policy: str
    final_tick: int
    row_ticks: int
    committed_rows: int
    native_ticks: int
    done: bool
    winner: int
    entered_overtime: bool
    terminal_reason: str
    cumulative_rewards: tuple[float, float]
    digest: str


def build_simple_runtime(
    *,
    seed: int,
    decks: list[list[str]],
    batch_size: int,
    device: str,
    max_entities: int,
    max_effects: int,
    regulation_ticks: int,
    tiebreak_ticks: int,
    supported_only: bool = False,
) -> SimpleGymRuntime:
    """Construct the native runtime at its serialized-data boundary."""

    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    torch_device = torch.device(device)
    loader = CardDataLoader()
    card_names = unique_cards_from_decks(decks)
    setup = compile_standard_simple_setup(
        loader,
        card_names,
        device=torch_device,
        canonical_lane_globals=True,
    )
    if supported_only:
        decks = _supported_decks(setup, decks)
    if (regulation_ticks, tiebreak_ticks) != (
        STANDARD_REGULATION_TICK,
        STANDARD_TIEBREAK_TICK,
    ):
        # Short timelines are retained for bounded validator tests only. All
        # arena/catalog/phase setup still comes from the standard authority.
        setup = replace(
            setup,
            rules=FastMatchRules(
                regulation_ticks=regulation_ticks,
                tiebreak_ticks=tiebreak_ticks,
            ),
        )

    rng = random.Random(seed)
    ordered_decks: list[list[list[str]]] = []
    for _ in range(batch_size):
        seats: list[list[str]] = []
        for _seat in range(2):
            names = list(rng.choice(decks))
            rng.shuffle(names)
            seats.append(names)
        ordered_decks.append(seats)

    # These benchmark-local lookup values retain exact typed catalog identity;
    # the runtime never root-collapses a Hero/Evolution variant.
    catalog = setup.spawn_blueprints.fast_cards
    tokens = torch.arange(catalog.size, dtype=torch.int64, device=torch_device) + 1
    hand_lookup = torch.where(
        setup.public_root_mask,
        tokens,
        torch.zeros_like(tokens),
    )
    # Internal child rows remain absent from the public hand vocabulary but
    # retain their own typed entity tokens when materialized in combat.
    entity_lookup = tokens.view(1, -1).expand(5, -1).clone()
    return setup.create_runtime(
        ordered_decks,
        entity_token_lookup=entity_lookup,
        hand_token_lookup=hand_lookup,
        canonical_lane_globals=True,
        max_entities=max_entities,
        max_effects=max_effects,
    )


def _supported_decks(
    setup: SimpleStandardSetup,
    decks: list[list[str]],
) -> list[list[str]]:
    """Return well-formed decks whose every public root is training-safe."""

    supported: list[list[str]] = []
    for deck in decks:
        if len(deck) != 8:
            raise ValueError("every deck must contain exactly eight cards")
        card_ids = [setup.cards.name_to_id.get(name) for name in deck]
        if any(card_id is None for card_id in card_ids):
            raise ValueError("deck contains a card outside the compiled public roots")
        concrete_ids = [int(card_id) for card_id in card_ids if card_id is not None]
        if all(
            bool(setup.public_root_mask[card_id])
            and bool(setup.supported_public_root_mask[card_id])
            for card_id in concrete_ids
        ):
            supported.append(deck)
    if not supported:
        raise ValueError("deck pool contains no fully supported simple Gym decks")
    return supported


def supported_simple_decks(
    decks: list[list[str]],
    *,
    device: str,
) -> list[list[str]]:
    """Compile truthful support once and filter a benchmark candidate pool."""

    if not decks:
        raise ValueError("deck pool must not be empty")
    loader = CardDataLoader()
    setup = compile_standard_simple_setup(
        loader,
        unique_cards_from_decks(decks),
        device=device,
        canonical_lane_globals=True,
    )
    return _supported_decks(setup, decks)


def select_actions(mask: torch.Tensor, policy: str) -> torch.Tensor:
    """Choose no-op or the stable first legal non-no-op action per actor."""

    if policy == "noop":
        return torch.full(
            mask.shape[:2], NO_OP_ACTION, dtype=torch.int64, device=mask.device
        )
    if policy != "first-legal":
        raise ValueError(f"unknown policy: {policy}")
    action_count = mask.shape[2]
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


def update_digest(digest: "hashlib._Hash", value: torch.Tensor) -> None:
    cpu = value.detach().contiguous().cpu()
    digest.update(str(cpu.dtype).encode())
    digest.update(str(tuple(cpu.shape)).encode())
    digest.update(cpu.numpy().tobytes())


def update_step_digest(
    digest: "hashlib._Hash", step: SimpleGymRuntimeStep, actions: torch.Tensor
) -> None:
    actor = step.observation.actor
    for value in (
        actions,
        actor.entity_ids,
        actor.entity_features,
        actor.entity_mask,
        actor.hand_ids,
        actor.global_features,
        step.observation.legal_mask,
        step.action_success,
        step.reward,
        step.done,
        step.winner,
        step.native_ticks,
        step.committed,
    ):
        update_digest(digest, value)


def run_episode(
    *,
    seed: int,
    decks: list[list[str]],
    policy: str,
    device: str,
    max_entities: int,
    max_effects: int,
    regulation_ticks: int,
    tiebreak_ticks: int,
) -> SimpleEpisodeSummary:
    runtime = build_simple_runtime(
        seed=seed,
        decks=decks,
        batch_size=1,
        device=device,
        max_entities=max_entities,
        max_effects=max_effects,
        regulation_ticks=regulation_ticks,
        tiebreak_ticks=tiebreak_ticks,
    )
    observation = runtime.observe()
    digest = hashlib.sha256()
    cumulative_reward = torch.zeros((1, 2), dtype=torch.float64, device=runtime.device)
    row_ticks = 0
    committed_rows = 0
    native_ticks = 0
    last: SimpleGymRuntimeStep | None = None

    for _ in range(tiebreak_ticks):
        actions = select_actions(observation.legal_mask, policy)
        last = runtime.step_tick(actions)
        update_step_digest(digest, last, actions)
        cumulative_reward += last.reward.to(torch.float64)
        row_ticks += runtime.batch_size
        committed_rows += int(last.committed.sum().item())
        native_ticks += int(last.native_ticks.sum().item())
        observation = last.observation
        if bool(last.done.all().item()):
            break

    if last is None:
        raise RuntimeError("episode executed no native ticks")
    final_tick = int(runtime.state.tick[0].item())
    done = bool(last.done[0].item())
    winner = int(last.winner[0].item())
    entered_overtime = bool(runtime.outcomes.overtime[0].item())
    if not done:
        terminal_reason = "tick_budget_exhausted"
    elif final_tick >= tiebreak_ticks:
        terminal_reason = "tiebreak"
    elif entered_overtime:
        terminal_reason = "overtime_crown"
    else:
        terminal_reason = "regulation_crown"
    reward_cpu = cumulative_reward[0].cpu().tolist()
    return SimpleEpisodeSummary(
        seed=seed,
        policy=policy,
        final_tick=final_tick,
        row_ticks=row_ticks,
        committed_rows=committed_rows,
        native_ticks=native_ticks,
        done=done,
        winner=winner,
        entered_overtime=entered_overtime,
        terminal_reason=terminal_reason,
        cumulative_rewards=(float(reward_cpu[0]), float(reward_cpu[1])),
        digest=digest.hexdigest(),
    )


def validate(args: argparse.Namespace) -> dict[str, object]:
    decks = [list(deck) for deck in load_deck_pool(args.decks_path)]
    regulation_ticks = int(getattr(args, "regulation_ticks", EXACT_REGULATION_TICKS))
    tiebreak_ticks = int(getattr(args, "tiebreak_ticks", EXACT_TIEBREAK_TICKS))
    replays = int(getattr(args, "replays", 2))
    require_exact = bool(getattr(args, "require_exact_timeline", True))
    if replays < 2:
        raise ValueError("deterministic validation requires at least two replays")
    if regulation_ticks < 1 or tiebreak_ticks <= regulation_ticks:
        raise ValueError("invalid regulation/tiebreak timeline")
    if require_exact and (regulation_ticks, tiebreak_ticks) != (
        EXACT_REGULATION_TICKS,
        EXACT_TIEBREAK_TICKS,
    ):
        raise ValueError("exact validation requires regulation/tiebreak ticks 3600/6000")

    summaries: list[SimpleEpisodeSummary] = []
    for policy in args.policy:
        for seed in args.seed:
            repeated = [
                run_episode(
                    seed=seed,
                    decks=decks,
                    policy=policy,
                    device=args.device,
                    max_entities=args.max_entities,
                    max_effects=args.max_effects,
                    regulation_ticks=regulation_ticks,
                    tiebreak_ticks=tiebreak_ticks,
                )
                for _ in range(replays)
            ]
            first = repeated[0]
            if any(replay != first for replay in repeated[1:]):
                raise RuntimeError(
                    f"simple Gym replay is nondeterministic for seed={seed} policy={policy}"
                )
            if first.committed_rows != first.row_ticks or first.native_ticks != first.row_ticks:
                raise RuntimeError(
                    f"simple Gym episode was not fully native for seed={seed} policy={policy}"
                )
            if not first.done:
                raise RuntimeError(
                    f"simple Gym did not terminate for seed={seed} policy={policy}"
                )
            if policy == "noop" and not (
                first.final_tick == tiebreak_ticks
                and first.entered_overtime
                and first.terminal_reason == "tiebreak"
            ):
                raise RuntimeError("no-op episode did not traverse regulation, OT, and tiebreak")
            summaries.append(first)

    return {
        "schema_version": 1,
        "engine": "SimpleGymRuntime",
        "device": args.device,
        "timeline": {
            "regulation_ticks": regulation_ticks,
            "tiebreak_ticks": tiebreak_ticks,
            "exact_3600_6000": (regulation_ticks, tiebreak_ticks)
            == (EXACT_REGULATION_TICKS, EXACT_TIEBREAK_TICKS),
        },
        "replays": replays,
        "acceptance": {
            "deterministic_replay": True,
            "all_rows_committed": True,
            "all_row_ticks_native": True,
            "zero_fallback": True,
            "terminal_boundary_reached": True,
            "noop_regulation_ot_tiebreak": "noop" not in args.policy
            or all(
                summary.final_tick == tiebreak_ticks
                and summary.entered_overtime
                and summary.terminal_reason == "tiebreak"
                for summary in summaries
                if summary.policy == "noop"
            ),
            "python_parity_evaluated": False,
        },
        "episodes": [asdict(summary) for summary in summaries],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-effects", type=int, default=128)
    parser.add_argument("--regulation-ticks", type=int, default=EXACT_REGULATION_TICKS)
    parser.add_argument("--tiebreak-ticks", type=int, default=EXACT_TIEBREAK_TICKS)
    parser.add_argument("--replays", type=int, default=2)
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument(
        "--policy", choices=("noop", "first-legal"), action="append", default=[]
    )
    parser.add_argument("--out", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if not args.seed:
        args.seed = [202_608_263]
    if not args.policy:
        args.policy = ["noop", "first-legal"]
    args.require_exact_timeline = True
    if min(args.max_entities, args.max_effects, args.replays) < 1:
        raise ValueError("capacities and replays must be positive")
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
