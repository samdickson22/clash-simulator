"""Audit policy-visible use of a required card in paired gameplay reports."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _card_plays(row: dict[str, Any], card: str) -> int:
    plays = row.get("card_plays")
    if not isinstance(plays, dict):
        raise TypeError("gameplay row lacks card play counts")
    value = int(plays.get(card, 0))
    if value < 0:
        raise ValueError("card play counts cannot be negative")
    return value


def _arm_metrics(rows: list[tuple[str, dict[str, Any]]], card: str) -> dict[str, Any]:
    opportunities = 0
    games_used = 0
    plays = 0
    by_strategy: dict[str, dict[str, int]] = defaultdict(
        lambda: {"opportunities": 0, "games_used": 0, "plays": 0}
    )
    for strategy, row in rows:
        deck = list(row.get("candidate_deck", []))
        if card not in deck:
            raise ValueError(f"required card {card!r} is absent from a candidate deck")
        count = _card_plays(row, card)
        opportunities += 1
        games_used += int(count > 0)
        plays += count
        bucket = by_strategy[strategy]
        bucket["opportunities"] += 1
        bucket["games_used"] += int(count > 0)
        bucket["plays"] += count
    return {
        "opportunities": opportunities,
        "games_used": games_used,
        "game_usage_rate": games_used / max(1, opportunities),
        "plays": plays,
        "plays_per_game": plays / max(1, opportunities),
        "by_strategy": {
            strategy: {
                **values,
                "game_usage_rate": values["games_used"]
                / max(1, values["opportunities"]),
                "plays_per_game": values["plays"]
                / max(1, values["opportunities"]),
            }
            for strategy, values in sorted(by_strategy.items())
        },
    }


def audit_reports(
    reports: list[dict[str, Any]],
    *,
    required_card: str,
    minimum_game_usage_rate: float,
    minimum_strategy_game_usage_rate: float,
    minimum_plays_per_game: float,
    minimum_selected_overrides: int,
    minimum_override_tiles: int,
    maximum_override_tile_share: float,
) -> dict[str, Any]:
    if not reports:
        raise ValueError("at least one gameplay report is required")
    if not required_card:
        raise ValueError("required card cannot be empty")
    for name, value in (
        ("minimum_game_usage_rate", minimum_game_usage_rate),
        ("minimum_strategy_game_usage_rate", minimum_strategy_game_usage_rate),
        ("maximum_override_tile_share", maximum_override_tile_share),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between zero and one")
    if minimum_plays_per_game < 0.0:
        raise ValueError("minimum plays per game cannot be negative")
    if minimum_selected_overrides < 0 or minimum_override_tiles < 0:
        raise ValueError("override thresholds cannot be negative")

    baseline_rows: list[tuple[str, dict[str, Any]]] = []
    repaired_rows: list[tuple[str, dict[str, Any]]] = []
    selected_tiles: Counter[int] = Counter()
    selected_overrides = 0
    strategies: set[str] = set()
    seen_pairs: set[tuple[str, int]] = set()
    for report in reports:
        strategy = str(report.get("strategy", ""))
        if not strategy or strategy in strategies:
            raise ValueError("gameplay reports need unique nonempty strategies")
        strategies.add(strategy)
        by_game: dict[int, dict[bool, dict[str, Any]]] = defaultdict(dict)
        for row in report.get("games", []):
            game = int(row["game"])
            arm_is_repaired = bool(row["repaired"])
            if arm_is_repaired in by_game[game]:
                raise ValueError("gameplay report duplicates a paired arm")
            by_game[game][arm_is_repaired] = row
        if not by_game:
            raise ValueError("gameplay report has no paired games")
        for game, arms in sorted(by_game.items()):
            if set(arms) != {False, True}:
                raise ValueError("gameplay report is missing a paired arm")
            if (strategy, game) in seen_pairs:
                raise ValueError("gameplay report duplicates a strategy/game pair")
            seen_pairs.add((strategy, game))
            baseline = arms[False]
            repaired = arms[True]
            for field in ("seed", "candidate_player", "candidate_deck", "opponent_deck"):
                if baseline.get(field) != repaired.get(field):
                    raise ValueError(f"paired gameplay arms differ at {field}")
            baseline_rows.append((strategy, baseline))
            repaired_rows.append((strategy, repaired))
            for repair in repaired.get("repair_rows", []):
                base = repair.get("base", {})
                selected = repair.get("selected", {})
                if selected.get("card") != required_card:
                    continue
                if selected.get("kind") != "placement":
                    raise ValueError("required-card override is not a placement")
                if selected.get("action") == base.get("action"):
                    continue
                tile = int(selected["tile"])
                if tile < 0:
                    raise ValueError("override tile cannot be negative")
                selected_overrides += 1
                selected_tiles[tile] += 1

    baseline = _arm_metrics(baseline_rows, required_card)
    repaired = _arm_metrics(repaired_rows, required_card)
    dominant_tile_share = (
        max(selected_tiles.values()) / selected_overrides
        if selected_overrides
        else 1.0
    )
    minimum_strategy_rate = min(
        row["game_usage_rate"] for row in repaired["by_strategy"].values()
    )
    thresholds = {
        "minimum_game_usage_rate": minimum_game_usage_rate,
        "minimum_strategy_game_usage_rate": minimum_strategy_game_usage_rate,
        "minimum_plays_per_game": minimum_plays_per_game,
        "minimum_selected_overrides": minimum_selected_overrides,
        "minimum_override_tiles": minimum_override_tiles,
        "maximum_override_tile_share": maximum_override_tile_share,
    }
    passed = bool(
        repaired["game_usage_rate"] >= minimum_game_usage_rate
        and minimum_strategy_rate >= minimum_strategy_game_usage_rate
        and repaired["plays_per_game"] >= minimum_plays_per_game
        and selected_overrides >= minimum_selected_overrides
        and len(selected_tiles) >= minimum_override_tiles
        and dominant_tile_share <= maximum_override_tile_share
    )
    return {
        "schema": "clasher.action_value_card_utilization_gate.v1",
        "passed": passed,
        "required_card": required_card,
        "strategies": sorted(strategies),
        "paired_games": len(repaired_rows),
        "baseline": baseline,
        "repaired": repaired,
        "selected_overrides": selected_overrides,
        "selected_override_tiles": {
            str(tile): count for tile, count in sorted(selected_tiles.items())
        },
        "selected_override_tile_count": len(selected_tiles),
        "dominant_override_tile_share": dominant_tile_share,
        "thresholds": thresholds,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--required-card", required=True)
    parser.add_argument("--minimum-game-usage-rate", type=float, default=0.75)
    parser.add_argument(
        "--minimum-strategy-game-usage-rate", type=float, default=0.50
    )
    parser.add_argument("--minimum-plays-per-game", type=float, default=1.0)
    parser.add_argument("--minimum-selected-overrides", type=int, default=4)
    parser.add_argument("--minimum-override-tiles", type=int, default=2)
    parser.add_argument("--maximum-override-tile-share", type=float, default=0.75)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.input]
    result = audit_reports(
        reports,
        required_card=args.required_card,
        minimum_game_usage_rate=args.minimum_game_usage_rate,
        minimum_strategy_game_usage_rate=args.minimum_strategy_game_usage_rate,
        minimum_plays_per_game=args.minimum_plays_per_game,
        minimum_selected_overrides=args.minimum_selected_overrides,
        minimum_override_tiles=args.minimum_override_tiles,
        maximum_override_tile_share=args.maximum_override_tile_share,
    )
    result["inputs"] = {str(path.resolve()): _sha256(path) for path in args.input}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))
    if not result["passed"]:
        raise SystemExit("required-card utilization gate failed")


if __name__ == "__main__":
    main()
