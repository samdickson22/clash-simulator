"""Evaluate exact complete-game root interventions on designated-card states."""

# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from clasher.rl.common import NUM_TILES
from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.public_outcome import load_public_outcome_head
from clasher.rl.reward_model import DEFENSE_V2
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import StrategyBot
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_entries(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("win-condition manifest has no entries")
    return entries


def _describe_action(
    env: SelfPlayBattleEnv,
    player_id: int,
    action: int,
) -> dict[str, Any]:
    assert env.battle is not None
    if action == env.action_space.no_op_action:
        return {"action": action, "kind": "no-op"}
    if action == env.action_space.ability_action:
        return {"action": action, "kind": "ability"}
    slot = action // NUM_TILES
    return {
        "action": action,
        "kind": "placement",
        "slot": slot,
        "tile": action % NUM_TILES,
        "card": str(env.battle.players[player_id].hand[slot]),
    }


def _run_intervention(
    *,
    archetype: str,
    designated_card: str,
    deck_pool: Path,
    game: int,
    seed: int,
    policy_path: Path,
    outcome_path: Path,
    decks_path: Path,
    strategy_name: str,
    decision_interval: int,
    max_ticks: int,
    max_candidates: int,
    locations_per_slot: int,
    spatially_diverse_locations: bool,
    device: torch.device,
) -> dict[str, Any]:
    loaded = load_policy_checkpoint(policy_path, device=device, decks_path=decks_path)
    outcome = load_public_outcome_head(outcome_path, device=device)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        sampling_decks_path=deck_pool,
        seed=seed,
        canonical_perspective=True,
        canonical_lane_globals=loaded.model.config.canonical_lane_globals,
        engine_fast_path="on",
        reward_profile=DEFENSE_V2,
    )
    env._structured_obs_builder = loaded.builder
    env.reset(seed=seed)
    assert env.battle is not None
    controlled_player = game % 2
    opponent = 1 - controlled_player
    bot = StrategyBot(strategy_name)
    search = RecurrentValueGuidedSearch(
        policy=loaded,
        outcome=outcome,
        device=device,
        terminal_rollout=True,
        max_candidates=max_candidates,
        locations_per_slot=locations_per_slot,
        spatially_diverse_locations=spatially_diverse_locations,
        minimum_value_gain=0.0,
    )
    states = {
        player: loaded.model.initial_state(1, device=device)
        for player in (0, 1)
    }
    previous_actions = {
        player: env.action_space.no_op_action for player in (0, 1)
    }
    previous_rewards = {0: 0.0, 1: 0.0}
    episode_start = True

    def opponent_selector(
        simulation: SelfPlayBattleEnv,
        player_id: int,
        action_mask: np.ndarray,
    ) -> int:
        return int(
            bot.select_action(simulation, player_id, action_mask=action_mask)
        )

    done = False
    decision_index = 0
    while not done:
        policy_actions, next_states, _outputs, masks = search.observe_policy_pair(
            env,
            states=states,
            previous_actions=previous_actions,
            previous_rewards=previous_rewards,
            episode_start=episode_start,
        )
        hand = env.battle.players[controlled_player].hand
        designated_slots = [
            slot for slot, card in enumerate(hand) if card == designated_card
        ]
        legal_slots = [
            slot
            for slot in designated_slots
            if bool(
                masks[controlled_player][
                    slot * NUM_TILES : (slot + 1) * NUM_TILES
                ].any()
            )
        ]
        if legal_slots:
            exact = search.select_action(
                env,
                controlled_player,
                states=states,
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_start=episode_start,
                opponent_selector=opponent_selector,
            )
            candidate_rows = [
                {
                    **_describe_action(env, controlled_player, candidate.action),
                    "terminal_probability": candidate.probability,
                }
                for candidate in exact.candidates
            ]
            designated_rows = [
                row for row in candidate_rows if row.get("card") == designated_card
            ]
            if not designated_rows:
                raise ValueError(
                    "candidate budget excluded the legal designated action type"
                )
            best_probability = max(
                float(row["terminal_probability"]) for row in candidate_rows
            )
            designated_probability = max(
                float(row["terminal_probability"]) for row in designated_rows
            )
            return {
                "archetype": archetype,
                "designated_card": designated_card,
                "game": game,
                "seed": seed,
                "controlled_player": controlled_player,
                "strategy": strategy_name,
                "tick": int(env.battle.tick),
                "decision_index": decision_index,
                "hand": list(hand),
                "base": _describe_action(env, controlled_player, exact.base_action),
                "base_probability": exact.base_probability,
                "selected": _describe_action(env, controlled_player, exact.action),
                "selected_probability": exact.selected_probability,
                "best_probability": best_probability,
                "designated_best_probability": designated_probability,
                "designated_is_best": designated_probability == best_probability,
                "designated_selected": (
                    _describe_action(env, controlled_player, exact.action).get("card")
                    == designated_card
                ),
                "candidates": candidate_rows,
            }
        policy_actions[opponent] = opponent_selector(
            env,
            opponent,
            masks[opponent],
        )
        rewards, done, _ = env.step(policy_actions, pre_action_masks=masks)
        states = next_states
        previous_actions = policy_actions
        previous_rewards = {player: float(rewards[player]) for player in (0, 1)}
        episode_start = False
        decision_index += 1
    return {
        "archetype": archetype,
        "designated_card": designated_card,
        "game": game,
        "seed": seed,
        "controlled_player": controlled_player,
        "strategy": strategy_name,
        "query_found": False,
        "ticks": int(env.battle.tick),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--archetype", action="append", default=[])
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--seed", type=int, default=1057101)
    parser.add_argument("--strategy", default="balanced")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--max-candidates", type=int, default=10)
    parser.add_argument("--locations-per-slot", type=int, default=2)
    parser.add_argument("--spatially-diverse-locations", action="store_true")
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games <= 0:
        raise ValueError("games must be positive")

    selected = set(args.archetype)
    entries = [
        entry
        for entry in _manifest_entries(args.manifest)
        if not selected or entry.get("archetype") in selected
    ]
    found = {str(entry.get("archetype")) for entry in entries}
    if selected != found:
        raise ValueError(f"unknown requested archetypes: {sorted(selected - found)}")
    rows = []
    for entry_index, entry in enumerate(entries):
        deck_pool = Path(str(entry["deck_pool"])).resolve()
        for game in range(args.games):
            row = _run_intervention(
                archetype=str(entry["archetype"]),
                designated_card=str(entry["designated_card"]),
                deck_pool=deck_pool,
                game=game,
                seed=args.seed + entry_index * 100_003 + game * 1009,
                policy_path=args.policy.resolve(),
                outcome_path=args.outcome.resolve(),
                decks_path=args.decks_path.resolve(),
                strategy_name=args.strategy,
                decision_interval=args.decision_interval,
                max_ticks=args.max_ticks,
                max_candidates=args.max_candidates,
                locations_per_slot=args.locations_per_slot,
                spatially_diverse_locations=args.spatially_diverse_locations,
                device=torch.device(args.device),
            )
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)

    report = {
        "schema_version": 1,
        "purpose": "evaluation_only_exact_terminal_win_condition_intervention",
        "heldout_states_used_for_training": False,
        "policy": str(args.policy.resolve()),
        "policy_sha256": file_sha256(args.policy),
        "outcome": str(args.outcome.resolve()),
        "outcome_sha256": file_sha256(args.outcome),
        "manifest": str(args.manifest.resolve()),
        "manifest_sha256": file_sha256(args.manifest),
        "terminal_rollout": True,
        "locations_per_slot": args.locations_per_slot,
        "spatially_diverse_locations": args.spatially_diverse_locations,
        "max_candidates": args.max_candidates,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
