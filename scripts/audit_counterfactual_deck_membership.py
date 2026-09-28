"""Verify sampled counterfactual games against their frozen deck pools."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signature(cards: list[str]) -> tuple[str, ...]:
    if len(cards) != 8 or len(set(cards)) != 8:
        raise ValueError("deck signatures require eight unique cards")
    return tuple(sorted(cards))


def _load_pool(path: Path) -> dict[tuple[str, ...], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("decks")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"deck pool is empty or malformed: {path}")
    result: dict[tuple[str, ...], str] = {}
    for row in rows:
        signature = _signature([str(card) for card in row["cards"]])
        archetype = str(row.get("archetype", "unknown"))
        if signature in result and result[signature] != archetype:
            raise ValueError("one deck signature has conflicting archetypes")
        result[signature] = archetype
    return result


def audit_membership(
    report: dict[str, Any],
    *,
    learner_pool: dict[tuple[str, ...], str],
    opponent_pool: dict[tuple[str, ...], str],
    forbidden_opponent_pool: set[tuple[str, ...]],
    expected_games: int,
) -> dict[str, Any]:
    games = report.get("games")
    if not isinstance(games, list) or len(games) != expected_games:
        raise ValueError("counterfactual report game count changed")
    if set(opponent_pool).intersection(forbidden_opponent_pool):
        raise ValueError("opponent and forbidden deck pools overlap")
    sampled_opponents: Counter[tuple[str, ...]] = Counter()
    archetypes: Counter[str] = Counter()
    learner_signatures: Counter[tuple[str, ...]] = Counter()
    seats: Counter[int] = Counter()
    for row in games:
        controlled = int(row["controlled_player"])
        if controlled not in (0, 1):
            raise ValueError("controlled player is outside the two-player contract")
        decks = row.get("decks")
        if not isinstance(decks, list) or len(decks) != 2:
            raise ValueError("counterfactual game does not contain two decks")
        learner = _signature([str(card) for card in decks[controlled]])
        opponent = _signature([str(card) for card in decks[1 - controlled]])
        if learner not in learner_pool:
            raise ValueError("sampled learner deck is outside learner authority")
        if opponent not in opponent_pool:
            raise ValueError("sampled opponent deck is outside opponent authority")
        if opponent in forbidden_opponent_pool:
            raise ValueError("sampled opponent deck leaked from forbidden authority")
        learner_signatures[learner] += 1
        sampled_opponents[opponent] += 1
        archetypes[opponent_pool[opponent]] += 1
        seats[controlled] += 1
    return {
        "schema": "clasher.counterfactual_deck_membership_audit.v1",
        "passed": True,
        "games": len(games),
        "learner_pool_decks": len(learner_pool),
        "opponent_pool_decks": len(opponent_pool),
        "sampled_learner_decks": len(learner_signatures),
        "sampled_opponent_decks": len(sampled_opponents),
        "opponent_archetypes": dict(sorted(archetypes.items())),
        "candidate_seats": {str(key): value for key, value in sorted(seats.items())},
        "maximum_opponent_deck_repetitions": max(sampled_opponents.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--learner-pool", type=Path, required=True)
    parser.add_argument("--opponent-pool", type=Path, required=True)
    parser.add_argument("--forbidden-opponent-pool", type=Path)
    parser.add_argument("--expected-games", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.expected_games <= 0:
        raise ValueError("expected games must be positive")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    learner_pool = _load_pool(args.learner_pool)
    opponent_pool = _load_pool(args.opponent_pool)
    forbidden = (
        set()
        if args.forbidden_opponent_pool is None
        else set(_load_pool(args.forbidden_opponent_pool))
    )
    result = audit_membership(
        report,
        learner_pool=learner_pool,
        opponent_pool=opponent_pool,
        forbidden_opponent_pool=forbidden,
        expected_games=args.expected_games,
    )
    result["inputs"] = {
        "report": {"path": str(args.report.resolve()), "sha256": _sha256(args.report)},
        "learner_pool": {
            "path": str(args.learner_pool.resolve()),
            "sha256": _sha256(args.learner_pool),
        },
        "opponent_pool": {
            "path": str(args.opponent_pool.resolve()),
            "sha256": _sha256(args.opponent_pool),
        },
        "forbidden_opponent_pool": (
            None
            if args.forbidden_opponent_pool is None
            else {
                "path": str(args.forbidden_opponent_pool.resolve()),
                "sha256": _sha256(args.forbidden_opponent_pool),
            }
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
