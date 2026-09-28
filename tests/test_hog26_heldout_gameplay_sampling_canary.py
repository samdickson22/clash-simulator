# mypy: disable-error-code="import-untyped"

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from clasher.rl.selfplay_env import SelfPlayBattleEnv

ROOT = Path(__file__).resolve().parents[1]
CANARY = ROOT / "reports/hog26_heldout_gameplay_sampling_canary_seed1164811.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _deck_signatures(path: Path) -> set[tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {tuple(sorted(row["cards"])) for row in payload["decks"]}


def test_heldout_gameplay_draws_match_frozen_archetype_canary() -> None:
    payload = json.loads(CANARY.read_text(encoding="utf-8"))
    assert payload["schema"] == "clasher.hog26_heldout_gameplay_sampling_canary.v1"
    assert payload["passed"] is True
    assert payload["promotion_authorized"] is False
    learner = ROOT / payload["learner_pool"]["path"]
    assert _sha256(learner) == payload["learner_pool"]["sha256"]
    sampling_source = ROOT / payload["sampling_source"]["path"]
    assert _sha256(sampling_source) == payload["sampling_source"]["sha256"]

    for name in ("screen", "quarantine"):
        row = payload[name]
        opponent_pool = ROOT / row["pool_path"]
        assert _sha256(opponent_pool) == row["pool_sha256"]
        pool_payload = json.loads(opponent_pool.read_text(encoding="utf-8"))
        archetype_by_deck = {
            tuple(sorted(deck["cards"])): deck["archetype"]
            for deck in pool_payload["decks"]
        }
        archetypes: Counter[str] = Counter()
        seats: Counter[int] = Counter()
        opponent_decks: set[tuple[str, ...]] = set()
        sample_rows = []
        for game in range(int(row["games"])):
            candidate_player = game % 2
            game_seed = int(row["seed"]) + game * 1009
            player_paths = (
                (learner, opponent_pool)
                if candidate_player == 0
                else (opponent_pool, learner)
            )
            env = SelfPlayBattleEnv(
                decks_path=ROOT / "decks.json",
                sampling_decks_path=opponent_pool,
                player0_sampling_decks_path=player_paths[0],
                player1_sampling_decks_path=player_paths[1],
                seed=game_seed,
                canonical_perspective=True,
                engine_fast_path="on",
            )
            env.reset(seed=game_seed)
            assert env.battle is not None
            signature = tuple(
                sorted(env.battle.players[1 - candidate_player].deck)
            )
            archetype = archetype_by_deck[signature]
            archetypes[archetype] += 1
            seats[candidate_player] += 1
            opponent_decks.add(signature)
            sample_rows.append(
                {
                    "game": game,
                    "seed": game_seed,
                    "candidate_player": candidate_player,
                    "archetype": archetype,
                    "opponent_deck": list(signature),
                }
            )
        digest_payload = (
            json.dumps(sample_rows, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode()
        assert dict(sorted(archetypes.items())) == row["archetype_games"]
        assert {str(seat): seats[seat] for seat in (0, 1)} == row[
            "candidate_seats"
        ]
        assert len(opponent_decks) == row["unique_opponent_decks"]
        assert hashlib.sha256(digest_payload).hexdigest() == row[
            "sample_rows_sha256"
        ]


def test_heldout_gameplay_pools_are_exact_deck_disjoint() -> None:
    payload = json.loads(CANARY.read_text(encoding="utf-8"))
    paths = {
        "screen": ROOT / payload["screen"]["pool_path"],
        "quarantine": ROOT / payload["quarantine"]["pool_path"],
        "train": ROOT
        / "datasets/deck_curriculum_v3_seed1056101/train_strict_v2_holdouts_card_balanced.json",
        "validation": ROOT
        / "datasets/deck_curriculum_v3_seed1056101/validation.json",
    }
    signatures = {name: _deck_signatures(path) for name, path in paths.items()}
    observed = {
        "screen_vs_quarantine": len(signatures["screen"] & signatures["quarantine"]),
        "screen_vs_train": len(signatures["screen"] & signatures["train"]),
        "screen_vs_validation": len(signatures["screen"] & signatures["validation"]),
        "quarantine_vs_train": len(signatures["quarantine"] & signatures["train"]),
        "quarantine_vs_validation": len(
            signatures["quarantine"] & signatures["validation"]
        ),
    }
    assert observed == payload["exact_deck_overlap"]
