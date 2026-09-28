"""Audit typed runtime identities on deterministic free-running battles."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import torch

from clasher.rl.eval import load_policy_checkpoint
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.strategy_bots import STRATEGY_NAMES, StrategyBot
from clasher.rl.value_guided_search import RecurrentValueGuidedSearch


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(args: argparse.Namespace) -> dict[str, Any]:
    device = torch.device(args.device)
    loaded = load_policy_checkpoint(
        args.policy,
        device=device,
        decks_path=args.decks_path,
    )
    unknown_by_kind: Counter[str] = Counter()
    seen_tokens: Counter[str] = Counter()
    unknown_examples: dict[str, dict[str, Any]] = {}
    visible_entities = 0
    observations = 0
    game_rows = []
    for game in range(args.game_offset, args.game_offset + args.games):
        game_seed = args.seed + game * 1009
        controlled_player = (game // len(STRATEGY_NAMES)) % 2
        opponent = 1 - controlled_player
        strategy_name = STRATEGY_NAMES[game % len(STRATEGY_NAMES)]
        bot = StrategyBot(strategy_name)
        player_paths = (
            (args.learner_decks, args.opponent_decks)
            if controlled_player == 0
            else (args.opponent_decks, args.learner_decks)
        )
        env = SelfPlayBattleEnv(
            decision_interval_ticks=8,
            max_ticks=args.max_ticks,
            decks_path=args.decks_path,
            sampling_decks_path=args.opponent_decks,
            player0_sampling_decks_path=player_paths[0],
            player1_sampling_decks_path=player_paths[1],
            seed=game_seed,
            canonical_perspective=True,
            canonical_lane_globals=loaded.model.config.canonical_lane_globals,
            engine_fast_path="on",
        )
        env._structured_obs_builder = loaded.builder
        env.reset(seed=game_seed)
        assert env.battle is not None
        search = RecurrentValueGuidedSearch(
            policy=loaded,
            outcome=None,
            device=device,
            terminal_rollout=False,
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
        done = False
        game_unknown = 0
        game_visible = 0
        while not done:
            actions, next_states, _outputs, masks = search.observe_policy_pair(
                env,
                states=states,
                previous_actions=previous_actions,
                previous_rewards=previous_rewards,
                episode_start=episode_start,
            )
            for player in (0, 1):
                observations += 1
                for entity in env.battle.entities.values():
                    if not entity.is_alive or not entity.is_visible_to(player):
                        continue
                    token_id, _features = loaded.builder._entity_row(entity, player)
                    visible_entities += 1
                    game_visible += 1
                    token_name = loaded.builder.token_names[token_id]
                    seen_tokens[token_name] += 1
                    if token_id != 1:
                        continue
                    game_unknown += 1
                    kind = str(getattr(entity, "entity_kind", 4))
                    unknown_by_kind[kind] += 1
                    stats = getattr(entity, "card_stats", None)
                    key = "|".join(
                        (
                            type(entity).__name__,
                            str(getattr(stats, "name", "")),
                            str(getattr(entity, "spell_name", "")),
                            str(getattr(entity, "source_name", "")),
                        )
                    )
                    unknown_examples.setdefault(
                        key,
                        {
                            "entity_type": type(entity).__name__,
                            "entity_kind": int(getattr(entity, "entity_kind", 4)),
                            "stats_name": str(getattr(stats, "name", "")),
                            "spell_name": str(getattr(entity, "spell_name", "")),
                            "source_name": str(getattr(entity, "source_name", "")),
                        },
                    )
            actions[opponent] = int(
                bot.select_action(env, opponent, action_mask=masks[opponent])
            )
            rewards, done, _ = env.step(actions, pre_action_masks=masks)
            states = next_states
            previous_actions = actions
            previous_rewards = {
                player: float(rewards[player]) for player in (0, 1)
            }
            episode_start = False
        game_rows.append(
            {
                "game": game,
                "seed": game_seed,
                "strategy": strategy_name,
                "candidate_player": controlled_player,
                "ticks": int(env.battle.tick),
                "winner": env.battle.winner,
                "visible_entities": game_visible,
                "unknown_visible_entities": game_unknown,
            }
        )
        print(
            f"game={game} strategy={strategy_name} visible={game_visible} "
            f"unknown={game_unknown}",
            flush=True,
        )
    return {
        "schema": "clasher.runtime_entity_identity_audit.v1",
        "policy": str(args.policy.resolve()),
        "policy_sha256": _sha256(args.policy),
        "games": args.games,
        "observations": observations,
        "visible_entities": visible_entities,
        "unknown_visible_entities": sum(unknown_by_kind.values()),
        "unknown_by_entity_kind": dict(sorted(unknown_by_kind.items())),
        "unknown_examples": list(unknown_examples.values()),
        "seen_typed_tokens": len(
            [name for name in seen_tokens if not name.startswith("<")]
        ),
        "top_seen_tokens": seen_tokens.most_common(40),
        "game_rows": game_rows,
        "passed": not unknown_by_kind,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument(
        "--learner-decks",
        type=Path,
        default=Path("training_decks/katacr_hog26_only.json"),
    )
    parser.add_argument("--opponent-decks", type=Path, required=True)
    parser.add_argument("--games", type=int, default=12)
    parser.add_argument("--game-offset", type=int, default=0)
    parser.add_argument("--seed", type=int, default=1190001)
    parser.add_argument("--max-ticks", type=int, default=6000)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.games <= 0 or args.game_offset < 0 or args.max_ticks <= 0:
        raise ValueError("identity audit games and max ticks must be positive")
    result = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("runtime entity identity audit found unknown visible entities")


if __name__ == "__main__":
    main()
