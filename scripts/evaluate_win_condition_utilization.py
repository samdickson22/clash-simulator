from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from clasher.data import CardDataLoader
from clasher.rl.card_semantics import (
    building_target_pressure_score,
    semantic_card_profile,
)
from clasher.rl.common import NUM_HAND_SLOTS

DEFAULT_DECISION_SECONDS = 0.4
PRIMARY_PRESSURE_RELATIVE_THRESHOLD = 0.65


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _card_role(card_name: str, loader: CardDataLoader) -> str:
    return str(semantic_card_profile(card_name, loader=loader).role)


def tower_pressure_score(card_name: str, loader: CardDataLoader) -> float:
    """Mechanics-only estimate of a building-targeter's offensive potential."""

    stats = loader.get_card(card_name)
    return 0.0 if stats is None else building_target_pressure_score(stats)


def primary_tower_pressure_cards(cards: list[str], loader: CardDataLoader) -> list[str]:
    scores = {
        card: tower_pressure_score(card, loader)
        for card in cards
        if _card_role(card, loader) == "building_target"
    }
    scores = {card: score for card, score in scores.items() if score > 0.0}
    if not scores:
        return []
    peak = max(scores.values())
    return sorted(
        card
        for card, score in scores.items()
        if score >= PRIMARY_PRESSURE_RELATIVE_THRESHOLD * peak
    )


def _chosen_card(row: dict[str, Any]) -> str | None:
    if bool(row["is_no_op"]) or bool(row["is_ability"]):
        return None
    slot = row["slot"]
    hand = row["hand"]
    if slot is None or not 0 <= int(slot) < len(hand):
        raise ValueError("placement decision has no valid hand slot")
    card = hand[int(slot)]
    return None if card is None else str(card)


def _type_probabilities(row: dict[str, Any]) -> np.ndarray:
    if "action_type_probabilities" not in row:
        raise ValueError(
            "decision trace lacks exact action_type_probabilities; rerun evaluation "
            "with the current evaluator"
        )
    probabilities = np.asarray(row["action_type_probabilities"], dtype=np.float64)
    if probabilities.shape != (NUM_HAND_SLOTS + 2,):
        raise ValueError("decision trace action probabilities have an invalid shape")
    if not np.isfinite(probabilities).all() or not np.isclose(
        probabilities.sum(), 1.0, atol=1e-5
    ):
        raise ValueError("decision trace action probabilities are not normalized")
    return probabilities


def _safe_rate(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if denominator else None


def summarize_utilization(
    decisions: list[dict[str, Any]],
    games: list[dict[str, Any]],
    *,
    role: str = "primary_building_target",
    decision_seconds: float = DEFAULT_DECISION_SECONDS,
    designated_cards: set[str] | None = None,
) -> dict[str, Any]:
    if decision_seconds <= 0.0 or not math.isfinite(decision_seconds):
        raise ValueError("decision_seconds must be positive and finite")
    loader = CardDataLoader()
    role_cache: dict[str, str] = {}
    cost_cache: dict[str, float] = {}

    def role_of(card: str) -> str:
        if card not in role_cache:
            role_cache[card] = _card_role(card, loader)
        return role_cache[card]

    def cost_of(card: str) -> float:
        if card not in cost_cache:
            stats = loader.get_card(card)
            if stats is None:
                raise ValueError(f"unknown card in decision trace: {card!r}")
            cost_cache[card] = float(getattr(stats, "mana_cost", 0) or 0)
        return cost_cache[card]

    role_games: dict[int, list[str]] = {}
    game_seats: dict[int, int] = {}
    for game in games:
        game_id = int(game["game"])
        cards = [str(card) for card in game["candidate_deck"]]
        if designated_cards is not None:
            selected = sorted(card for card in cards if card in designated_cards)
        else:
            selected = (
                primary_tower_pressure_cards(cards, loader)
                if role == "primary_building_target"
                else sorted(card for card in cards if role_of(card) == role)
            )
        if selected:
            role_games[game_id] = selected
            game_seats[game_id] = int(game["candidate_player"])

    rows_by_game: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in decisions:
        game_id = int(row["game"])
        if game_id in role_games:
            rows_by_game[game_id].append(row)
    for rows in rows_by_game.values():
        rows.sort(key=lambda row: int(row["game_decision"]))

    per_game: list[dict[str, Any]] = []
    per_card: dict[str, Counter[str]] = defaultdict(Counter)
    per_seat: dict[int, Counter[str]] = defaultdict(Counter)
    per_slot: dict[int, Counter[str]] = defaultdict(Counter)
    role_probability_sum = 0.0
    role_probability_rows = 0
    for game_id in sorted(role_games):
        role_cards = set(role_games[game_id])
        seat = game_seats[game_id]
        game_rows = rows_by_game.get(game_id, [])
        plays: Counter[str] = Counter()
        hand_decisions = affordable_decisions = legal_affordable_decisions = 0
        affordable_windows = converted_windows = 0
        current_window = False
        current_window_converted = False
        hand_streak = max_hand_streak = 0
        game_probability_sum = 0.0
        game_probability_rows = 0

        def close_window() -> None:
            nonlocal current_window, current_window_converted, converted_windows
            if current_window and current_window_converted:
                converted_windows += 1
            current_window = False
            current_window_converted = False

        for row in game_rows:
            hand = [None if card is None else str(card) for card in row["hand"]]
            role_slots = [
                slot
                for slot, card in enumerate(hand[:NUM_HAND_SLOTS])
                if card is not None and card in role_cards
            ]
            if role_slots:
                hand_decisions += 1
                hand_streak += 1
                max_hand_streak = max(max_hand_streak, hand_streak)
                for slot in role_slots:
                    card = hand[slot]
                    assert card is not None
                    per_card[card]["hand_decisions"] += 1
                    per_slot[slot]["hand_decisions"] += 1
            else:
                hand_streak = 0

            affordable_slots = [
                slot
                for slot in role_slots
                if float(row["elixir"]) + 1e-6 >= cost_of(str(hand[slot]))
            ]
            if affordable_slots:
                affordable_decisions += 1
                probabilities = _type_probabilities(row)
                probability = float(probabilities[affordable_slots].sum())
                if probability > 0.0:
                    legal_affordable_decisions += 1
                    game_probability_sum += probability
                    game_probability_rows += 1
                    role_probability_sum += probability
                    role_probability_rows += 1
                    for slot in affordable_slots:
                        card = hand[slot]
                        assert card is not None
                        per_card[card]["legal_affordable_decisions"] += 1
                        per_slot[slot]["legal_affordable_decisions"] += 1
                    if not current_window:
                        affordable_windows += 1
                        current_window = True
                        current_window_converted = False
                else:
                    close_window()
            else:
                close_window()

            # Process the chosen card after opening the current decision's
            # affordable window. Many policies play immediately on the first
            # affordable frame; counting the choice first would miss exactly
            # those successful conversions.
            chosen = _chosen_card(row)
            if chosen in role_cards:
                plays[chosen] += 1
                per_card[chosen]["plays"] += 1
                per_seat[seat]["plays"] += 1
                selected_slot = int(row["slot"])
                per_slot[selected_slot]["plays"] += 1
                if current_window:
                    current_window_converted = True
        close_window()

        play_count = int(sum(plays.values()))
        per_seat[seat]["games"] += 1
        per_seat[seat]["zero_use_games"] += int(play_count == 0)
        per_seat[seat]["affordable_windows"] += affordable_windows
        per_seat[seat]["converted_windows"] += converted_windows
        per_game.append(
            {
                "game": game_id,
                "seat": seat,
                "role_cards": sorted(role_cards),
                "plays": dict(sorted(plays.items())),
                "play_count": play_count,
                "zero_use": play_count == 0,
                "hand_decisions": hand_decisions,
                "affordable_decisions": affordable_decisions,
                "legal_affordable_decisions": legal_affordable_decisions,
                "affordable_windows": affordable_windows,
                "converted_windows": converted_windows,
                "window_conversion_rate": _safe_rate(
                    converted_windows, affordable_windows
                ),
                "mean_role_probability_when_legal_affordable": _safe_rate(
                    game_probability_sum, game_probability_rows
                ),
                "max_continuous_hand_seconds": max_hand_streak * decision_seconds,
            }
        )

    total_games = len(per_game)
    zero_use_games = sum(int(row["zero_use"]) for row in per_game)
    total_windows = sum(int(row["affordable_windows"]) for row in per_game)
    converted_windows = sum(int(row["converted_windows"]) for row in per_game)

    def counter_report(counter: Counter[str]) -> dict[str, Any]:
        result: dict[str, Any] = {key: int(value) for key, value in counter.items()}
        if "games" in counter:
            result["zero_use_rate"] = _safe_rate(
                counter["zero_use_games"], counter["games"]
            )
        if "affordable_windows" in counter:
            result["window_conversion_rate"] = _safe_rate(
                counter["converted_windows"], counter["affordable_windows"]
            )
        return result

    result = {
        "schema_version": 1,
        "role": role,
        "decision_seconds": decision_seconds,
        "games": total_games,
        "zero_use_games": zero_use_games,
        "zero_use_rate": _safe_rate(zero_use_games, total_games),
        "plays": sum(int(row["play_count"]) for row in per_game),
        "affordable_windows": total_windows,
        "converted_windows": converted_windows,
        "window_conversion_rate": _safe_rate(converted_windows, total_windows),
        "mean_role_probability_when_legal_affordable": _safe_rate(
            role_probability_sum, role_probability_rows
        ),
        "by_seat": {
            str(seat): counter_report(counter)
            for seat, counter in sorted(per_seat.items())
        },
        "by_card": {
            card: counter_report(counter) for card, counter in sorted(per_card.items())
        },
        "by_slot": {
            str(slot): counter_report(counter)
            for slot, counter in sorted(per_slot.items())
        },
        "per_game": per_game,
    }
    if designated_cards is not None:
        result["designated_cards"] = sorted(designated_cards)
    return result


def promotion_gate(
    report: dict[str, Any],
    *,
    max_zero_use_rate: float,
    min_window_conversion_rate: float,
    min_games_per_seat: int,
) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "enough_games_per_seat": all(
            int(report["by_seat"].get(str(seat), {}).get("games", 0))
            >= min_games_per_seat
            for seat in (0, 1)
        ),
        "aggregate_zero_use_rate": (
            report["zero_use_rate"] is not None
            and float(report["zero_use_rate"]) <= max_zero_use_rate
        ),
        "aggregate_window_conversion_rate": (
            report["window_conversion_rate"] is not None
            and float(report["window_conversion_rate"]) >= min_window_conversion_rate
        ),
        "both_seats_zero_use_rate": all(
            report["by_seat"].get(str(seat), {}).get("zero_use_rate") is not None
            and float(report["by_seat"][str(seat)]["zero_use_rate"])
            <= max_zero_use_rate
            for seat in (0, 1)
        ),
        "both_seats_window_conversion_rate": all(
            report["by_seat"].get(str(seat), {}).get("window_conversion_rate")
            is not None
            and float(report["by_seat"][str(seat)]["window_conversion_rate"])
            >= min_window_conversion_rate
            for seat in (0, 1)
        ),
    }
    return {
        "thresholds": {
            "max_zero_use_rate": max_zero_use_rate,
            "min_window_conversion_rate": min_window_conversion_rate,
            "min_games_per_seat": min_games_per_seat,
        },
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--role", default="primary_building_target")
    parser.add_argument(
        "--card",
        action="append",
        default=[],
        help=(
            "explicitly designate a card as the measured win condition; repeat "
            "for multiple cards instead of inferring a semantic role"
        ),
    )
    parser.add_argument("--decision-seconds", type=float, default=0.4)
    parser.add_argument("--max-zero-use-rate", type=float, default=0.10)
    parser.add_argument("--min-window-conversion-rate", type=float, default=0.25)
    parser.add_argument("--min-games-per-seat", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    games = json.loads(args.games.read_text(encoding="utf-8"))
    report = summarize_utilization(
        decisions,
        games,
        role="designated_win_condition" if args.card else args.role,
        decision_seconds=args.decision_seconds,
        designated_cards=set(args.card) if args.card else None,
    )
    report["gate"] = promotion_gate(
        report,
        max_zero_use_rate=args.max_zero_use_rate,
        min_window_conversion_rate=args.min_window_conversion_rate,
        min_games_per_seat=args.min_games_per_seat,
    )
    report["decisions"] = str(args.decisions.resolve())
    report["decisions_sha256"] = _sha256(args.decisions)
    report["game_records"] = str(args.games.resolve())
    report["game_records_sha256"] = _sha256(args.games)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
