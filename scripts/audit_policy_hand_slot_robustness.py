# mypy: disable-error-code="import-untyped"
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from dataclasses import fields
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.model import ClasherPolicy, PolicyInputs, PolicyOutput
from clasher.rl.reward_model import REWARD_PROFILES
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.train_recurrent import _stack_step_inputs, maybe_silence_stdio

ORDERS = torch.tensor(
    list(itertools.permutations(range(NUM_HAND_SLOTS))),
    dtype=torch.long,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _repeat_batch(value: torch.Tensor | None, repeats: int) -> torch.Tensor | None:
    if value is None:
        return None
    return value.expand(repeats, *value.shape[1:]).clone()


def permute_current_hand_slots(
    inputs: PolicyInputs,
    orders: torch.Tensor = ORDERS,
) -> PolicyInputs:
    """Batch current-hand counterfactuals while preserving public history.

    ``orders[row, slot]`` names the original slot placed in that counterfactual
    slot.  The fifth next-card token and the previous action/history are kept
    fixed: this is a current card-choice robustness audit, not a fabricated
    replay with rewritten temporal history.
    """

    if inputs.batch_size != 1 or inputs.sequence_length != 1:
        raise ValueError("slot counterfactuals require one single-step input")
    if orders.ndim != 2 or orders.shape[1] != NUM_HAND_SLOTS:
        raise ValueError("orders must have shape [permutations, four slots]")
    expected = list(range(NUM_HAND_SLOTS))
    if any(sorted(row.tolist()) != expected for row in orders.cpu()):
        raise ValueError("each order row must be a four-slot permutation")

    repeats = int(orders.shape[0])
    device_orders = orders.to(inputs.hand_ids.device)
    payload: dict[str, torch.Tensor | None] = {
        field.name: _repeat_batch(getattr(inputs, field.name), repeats)
        for field in fields(PolicyInputs)
    }

    hand_ids = payload["hand_ids"]
    assert hand_ids is not None
    original_hand = inputs.hand_ids[0, 0, :NUM_HAND_SLOTS]
    hand_ids[:, 0, :NUM_HAND_SLOTS] = original_hand[device_orders]

    hand_confidence = payload["hand_id_confidence"]
    if hand_confidence is not None:
        original_confidence = inputs.hand_id_confidence
        assert original_confidence is not None
        hand_confidence[:, 0, :NUM_HAND_SLOTS] = original_confidence[
            0, 0, :NUM_HAND_SLOTS
        ][device_orders]

    action_mask = payload["action_mask"]
    assert action_mask is not None
    original_placements = inputs.action_mask[
        0, 0, : NUM_HAND_SLOTS * NUM_TILES
    ].reshape(NUM_HAND_SLOTS, NUM_TILES)
    action_mask[:, 0, : NUM_HAND_SLOTS * NUM_TILES] = original_placements[
        device_orders
    ].reshape(repeats, -1)

    critic_cards = payload["critic_card_ids"]
    if critic_cards is not None:
        original_critic = inputs.critic_card_ids
        assert original_critic is not None
        critic_cards[:, 0, :NUM_HAND_SLOTS] = original_critic[0, 0, :NUM_HAND_SLOTS][
            device_orders
        ]

    return PolicyInputs(**payload)  # type: ignore[arg-type]


def _type_probabilities(output: PolicyOutput) -> torch.Tensor:
    probabilities = output.distribution().probs[:, 0]
    placements = probabilities[:, : NUM_HAND_SLOTS * NUM_TILES].reshape(
        -1, NUM_HAND_SLOTS, NUM_TILES
    )
    return torch.cat(
        [placements.sum(dim=-1), probabilities[:, NUM_HAND_SLOTS * NUM_TILES :]],
        dim=-1,
    )


class SlotRobustnessAudit:
    def __init__(
        self,
        *,
        model: ClasherPolicy,
        token_names: tuple[str, ...],
        designated_card: str,
        general_stride: int,
        max_general_decisions: int,
    ) -> None:
        self.model = model
        self.token_names = token_names
        self.designated_card = designated_card
        self.designated_id = token_names.index(designated_card)
        self.general_stride = general_stride
        self.max_general_decisions = max_general_decisions
        self.decisions_seen = 0
        self.general_decisions = 0
        self.episode_start_decisions = 0
        self.designated_legal_decisions = 0
        self.rows: list[dict[str, Any]] = []

    @torch.no_grad()
    def observe(
        self,
        inputs: PolicyInputs,
        state: tuple[torch.Tensor, torch.Tensor],
        original_output: PolicyOutput,
    ) -> None:
        self.decisions_seen += 1
        placement_mask = inputs.action_mask[0, 0, : NUM_HAND_SLOTS * NUM_TILES].reshape(
            NUM_HAND_SLOTS, NUM_TILES
        )
        legal_slots = placement_mask.any(dim=-1)
        hand = inputs.hand_ids[0, 0, :NUM_HAND_SLOTS]
        designated_slots = torch.nonzero(
            (hand == self.designated_id) & legal_slots,
            as_tuple=False,
        ).flatten()
        designated_legal = designated_slots.numel() > 0
        episode_start = bool(inputs.episode_starts[0, 0].item())
        take_general = (
            self.general_decisions < self.max_general_decisions
            and legal_slots.count_nonzero().item() >= 2
            and (self.decisions_seen - 1) % self.general_stride == 0
        )
        if not designated_legal and not take_general and not episode_start:
            return
        if take_general:
            self.general_decisions += 1
        if designated_legal:
            self.designated_legal_decisions += 1
        if episode_start:
            self.episode_start_decisions += 1

        permutations = permute_current_hand_slots(inputs)
        repeated_state = (
            state[0].expand(len(ORDERS), -1).clone(),
            state[1].expand(len(ORDERS), -1).clone(),
        )
        counterfactual = self.model(permutations, repeated_state)
        assert isinstance(counterfactual, PolicyOutput)

        original_force_play = None
        counterfactual_force_play = None
        if self.model.config.play_hazard_enabled:
            original_force_play, _ = self.model._play_hazard_force_gate(  # type: ignore[attr-defined]
                original_output,
                inputs.action_mask,
                state[0][:, -1],
            )
            counterfactual_force_play, _ = self.model._play_hazard_force_gate(  # type: ignore[attr-defined]
                counterfactual,
                permutations.action_mask,
                repeated_state[0][:, -1],
            )

        original_action = int(
            self.model._deterministic_actions(  # type: ignore[attr-defined]
                original_output,
                inputs.action_mask,
                force_play=original_force_play,
            )[0, 0].item()
        )
        actions = self.model._deterministic_actions(  # type: ignore[attr-defined]
            counterfactual,
            permutations.action_mask,
            force_play=counterfactual_force_play,
        )[:, 0]
        original_type = (
            original_action // NUM_TILES
            if original_action < 4 * NUM_TILES
            else original_action
        )
        original_card_id = (
            int(hand[original_type].item()) if original_type < NUM_HAND_SLOTS else None
        )
        original_tile = (
            original_action % NUM_TILES
            if original_action < NUM_HAND_SLOTS * NUM_TILES
            else None
        )

        permuted_hands = permutations.hand_ids[:, 0, :NUM_HAND_SLOTS]
        action_is_play = actions < NUM_HAND_SLOTS * NUM_TILES
        action_slots = torch.where(
            action_is_play,
            actions // NUM_TILES,
            torch.zeros_like(actions),
        )
        selected_cards = permuted_hands.gather(1, action_slots[:, None]).squeeze(1)
        selected_cards = torch.where(
            action_is_play,
            selected_cards,
            torch.full_like(selected_cards, -1),
        )
        selected_tiles = torch.where(
            action_is_play,
            actions % NUM_TILES,
            torch.full_like(actions, -1),
        )

        original_types = original_output.action_type_logits[0, 0, :NUM_HAND_SLOTS]
        expected_types = original_types[ORDERS.to(original_types.device)]
        type_errors = (
            counterfactual.action_type_logits[:, 0, :NUM_HAND_SLOTS] - expected_types
        ).abs()
        original_locations = original_output.location_logits[0, 0]
        expected_locations = original_locations[ORDERS.to(original_locations.device)]
        location_errors = (
            counterfactual.location_logits[:, 0] - expected_locations
        ).abs()

        original_probabilities = _type_probabilities(original_output)[0]
        probabilities = _type_probabilities(counterfactual)
        expected_probabilities = torch.cat(
            [
                original_probabilities[:NUM_HAND_SLOTS][
                    ORDERS.to(original_probabilities.device)
                ],
                original_probabilities[NUM_HAND_SLOTS:]
                .unsqueeze(0)
                .expand(len(ORDERS), -1),
            ],
            dim=-1,
        )
        probability_errors = (probabilities - expected_probabilities).abs()

        designated_destinations = torch.full(
            (len(ORDERS),),
            -1,
            dtype=torch.long,
            device=permuted_hands.device,
        )
        designated_probability = torch.full(
            (len(ORDERS),),
            float("nan"),
            device=probabilities.device,
        )
        if designated_legal:
            matches = permuted_hands == self.designated_id
            designated_destinations = matches.to(torch.int64).argmax(dim=-1)
            designated_probability = probabilities.gather(
                1, designated_destinations[:, None]
            ).squeeze(1)

        special_matches = torch.where(
            ~action_is_play,
            actions == original_action,
            torch.zeros_like(action_is_play),
        )
        card_matches = (
            selected_cards == original_card_id
            if original_card_id is not None
            else special_matches
        )
        card_and_tile_matches = (
            card_matches & (selected_tiles == original_tile)
            if original_tile is not None
            else card_matches
        )

        self.rows.append(
            {
                "decision_index": self.decisions_seen - 1,
                "episode_start": episode_start,
                "designated_legal": designated_legal,
                "original_hand": [
                    self.token_names[int(value)] for value in hand.tolist()
                ],
                "original_action_kind": (
                    "play" if original_card_id is not None else "special"
                ),
                "original_selected_card": (
                    None
                    if original_card_id is None
                    else self.token_names[original_card_id]
                ),
                "card_identity_preserved": int(card_matches.count_nonzero().item()),
                "card_and_tile_preserved": int(
                    card_and_tile_matches.count_nonzero().item()
                ),
                "permutations": len(ORDERS),
                "max_slot_logit_equivariance_error": float(type_errors.max().item()),
                "mean_slot_logit_equivariance_error": float(type_errors.mean().item()),
                "max_location_equivariance_error": float(location_errors.max().item()),
                "max_type_probability_equivariance_error": float(
                    probability_errors.max().item()
                ),
                "designated_selected_by_destination": {
                    str(slot): int(
                        (
                            (designated_destinations == slot)
                            & (selected_cards == self.designated_id)
                        )
                        .count_nonzero()
                        .item()
                    )
                    for slot in range(NUM_HAND_SLOTS)
                },
                "designated_probability_by_destination": {
                    str(slot): float(
                        designated_probability[designated_destinations == slot]
                        .mean()
                        .item()
                    )
                    for slot in range(NUM_HAND_SLOTS)
                    if designated_legal
                },
            }
        )

    def summary(self) -> dict[str, Any]:
        permutation_count = sum(int(row["permutations"]) for row in self.rows)
        designated_rows = [row for row in self.rows if row["designated_legal"]]
        episode_start_rows = [row for row in self.rows if row["episode_start"]]
        episode_start_permutations = sum(
            int(row["permutations"]) for row in episode_start_rows
        )
        designated_trials = {
            str(slot): sum(
                int(row["permutations"]) // NUM_HAND_SLOTS for row in designated_rows
            )
            for slot in range(NUM_HAND_SLOTS)
        }
        designated_selected = {
            str(slot): sum(
                int(row["designated_selected_by_destination"][str(slot)])
                for row in designated_rows
            )
            for slot in range(NUM_HAND_SLOTS)
        }
        probability_by_slot: dict[str, float | None] = {}
        for slot in range(NUM_HAND_SLOTS):
            values = [
                float(row["designated_probability_by_destination"][str(slot)])
                for row in designated_rows
            ]
            probability_by_slot[str(slot)] = float(np.mean(values)) if values else None
        return {
            "decisions_seen": self.decisions_seen,
            "audited_decisions": len(self.rows),
            "audited_permutations": permutation_count,
            "general_decisions": self.general_decisions,
            "episode_start_decisions": self.episode_start_decisions,
            "designated_card": self.designated_card,
            "designated_legal_decisions": self.designated_legal_decisions,
            "card_identity_preservation_rate": (
                sum(int(row["card_identity_preserved"]) for row in self.rows)
                / max(1, permutation_count)
            ),
            "card_and_tile_preservation_rate": (
                sum(int(row["card_and_tile_preserved"]) for row in self.rows)
                / max(1, permutation_count)
            ),
            "episode_start_card_identity_preservation_rate": (
                sum(int(row["card_identity_preserved"]) for row in episode_start_rows)
                / max(1, episode_start_permutations)
            ),
            "episode_start_card_and_tile_preservation_rate": (
                sum(int(row["card_and_tile_preserved"]) for row in episode_start_rows)
                / max(1, episode_start_permutations)
            ),
            "episode_start_max_slot_logit_equivariance_error": max(
                (
                    float(row["max_slot_logit_equivariance_error"])
                    for row in episode_start_rows
                ),
                default=0.0,
            ),
            "episode_start_max_location_equivariance_error": max(
                (
                    float(row["max_location_equivariance_error"])
                    for row in episode_start_rows
                ),
                default=0.0,
            ),
            "max_slot_logit_equivariance_error": max(
                (float(row["max_slot_logit_equivariance_error"]) for row in self.rows),
                default=0.0,
            ),
            "mean_decision_slot_logit_equivariance_error": float(
                np.mean(
                    [
                        float(row["mean_slot_logit_equivariance_error"])
                        for row in self.rows
                    ]
                )
            )
            if self.rows
            else 0.0,
            "max_location_equivariance_error": max(
                (float(row["max_location_equivariance_error"]) for row in self.rows),
                default=0.0,
            ),
            "max_type_probability_equivariance_error": max(
                (
                    float(row["max_type_probability_equivariance_error"])
                    for row in self.rows
                ),
                default=0.0,
            ),
            "designated_trials_by_destination": designated_trials,
            "designated_selected_by_destination": designated_selected,
            "designated_selection_rate_by_destination": {
                slot: designated_selected[slot] / max(1, designated_trials[slot])
                for slot in designated_trials
            },
            "designated_mean_probability_by_destination": probability_by_slot,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit current-hand slot robustness under all 24 permutations"
    )
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--sampling-decks-path", required=True)
    parser.add_argument("--designated-card", default="HogRider")
    parser.add_argument(
        "--opponent-strategy", choices=STRATEGY_NAMES, default="balanced"
    )
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--seed", type=int, default=1_056_017)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default="defense-v2"
    )
    parser.add_argument("--general-stride", type=int, default=17)
    parser.add_argument("--max-general-decisions", type=int, default=256)
    parser.add_argument("--json-out", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.games <= 0 or args.games % 2:
        raise ValueError("games must be a positive even count")
    if args.general_stride <= 0 or args.max_general_decisions < 0:
        raise ValueError("general sampling controls are invalid")

    checkpoint = Path(args.checkpoint).resolve()
    decks_path = Path(args.decks_path).resolve()
    sampling_decks = Path(args.sampling_decks_path).resolve()
    output = Path(args.json_out).resolve()
    device = torch.device("cpu")
    loaded = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    token_names = tuple(str(name) for name in loaded.checkpoint["token_names"])
    audit = SlotRobustnessAudit(
        model=loaded.model,
        token_names=token_names,
        designated_card=args.designated_card,
        general_stride=args.general_stride,
        max_general_decisions=args.max_general_decisions,
    )
    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=decks_path,
        sampling_decks_path=sampling_decks,
        seed=args.seed,
        mirror_match=True,
        canonical_perspective=True,
        canonical_lane_globals=loaded.model.config.canonical_lane_globals,
        reward_profile=args.reward_profile,
    )
    opponent = StrategyBot(args.opponent_strategy)
    wins = losses = draws = 0

    for game in range(args.games):
        matchup_seed = args.seed + (game // 2) * 1009
        with maybe_silence_stdio(True):
            env.reset(seed=matchup_seed)
        torch.manual_seed(matchup_seed + 271_828)
        candidate_player = game % 2
        other_player = 1 - candidate_player
        state = loaded.model.initial_state(1, device=device)
        previous_action = env.action_space.no_op_action
        previous_reward = 0.0
        episode_start = True
        done = False

        while not done:
            assert env.battle is not None
            observation = loaded.builder.build(env.battle, candidate_player)
            mask = env.get_action_mask(candidate_player)[None, :]
            inputs = _stack_step_inputs(
                [observation],
                mask,
                np.asarray([previous_action], dtype=np.int64),
                np.asarray([previous_reward], dtype=np.float32),
                np.asarray([episode_start], dtype=np.bool_),
                device,
                public_observation_confidence=(
                    loaded.model.config.public_observation_confidence
                ),
            )
            action, _, _, next_state, policy_output = loaded.model.act(
                inputs,
                state,
                deterministic=True,
            )
            audit.observe(inputs, state, policy_output)
            candidate_action = int(action[0, 0].item())
            other_mask = env.get_action_mask(other_player)
            other_action = opponent.select_action(
                env,
                other_player,
                action_mask=other_mask,
            )
            with maybe_silence_stdio(True):
                rewards, done, _ = env.step(
                    {
                        candidate_player: candidate_action,
                        other_player: other_action,
                    },
                    pre_action_masks={
                        candidate_player: mask[0],
                        other_player: other_mask,
                    },
                )
            state = next_state
            previous_action = candidate_action
            previous_reward = float(rewards[candidate_player])
            episode_start = False

        assert env.battle is not None
        if env.battle.winner is None:
            draws += 1
        elif env.battle.winner == candidate_player:
            wins += 1
        else:
            losses += 1

    gameplay = {"wins": wins, "losses": losses, "draws": draws}
    summary = audit.summary()
    payload: dict[str, Any] = {
        "schema": "clasher-hand-slot-robustness-v1",
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": _sha256(checkpoint),
        "decks_path": str(decks_path),
        "decks_sha256": _sha256(decks_path),
        "sampling_decks_path": str(sampling_decks),
        "sampling_decks_sha256": _sha256(sampling_decks),
        "protocol": {
            "games": args.games,
            "seed": args.seed,
            "decision_interval": args.decision_interval,
            "max_ticks": args.max_ticks,
            "opponent_strategy": args.opponent_strategy,
            "reward_profile": args.reward_profile,
            "mirror_match": True,
            "permutations": ORDERS.tolist(),
            "counterfactual_scope": (
                "current four-card hand, matching legal-action slot blocks, hand "
                "confidence, and actor-hand critic slots; next card, previous action, "
                "and recurrent history remain fixed"
            ),
            "general_stride": args.general_stride,
            "max_general_decisions": args.max_general_decisions,
        },
        "gameplay": gameplay,
        "summary": summary,
        "decisions": audit.rows,
    }
    if not math.isfinite(summary["card_identity_preservation_rate"]):
        raise RuntimeError("non-finite slot robustness result")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"gameplay": gameplay, **summary}, indent=2))


if __name__ == "__main__":
    main()
