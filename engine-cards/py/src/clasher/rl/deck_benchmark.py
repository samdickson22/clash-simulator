from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def canonical_deck(cards: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(str(card) for card in cards))


def _record_key(record: Mapping[str, Any]) -> tuple[int, int]:
    return int(record["matchup_seed"]), int(record["candidate_player"])


def compare_game_records(
    baseline: Iterable[Mapping[str, Any]],
    candidate: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare identical seeded games and expose every outcome regression."""

    def indexed(
        records: Iterable[Mapping[str, Any]],
    ) -> dict[tuple[int, int], Mapping[str, Any]]:
        result: dict[tuple[int, int], Mapping[str, Any]] = {}
        for record in records:
            key = _record_key(record)
            if key in result:
                raise ValueError(f"duplicate game record key {key!r}")
            result[key] = record
        return result

    before = indexed(baseline)
    after = indexed(candidate)
    if before.keys() != after.keys():
        raise ValueError("baseline and candidate game keys must match exactly")
    rank = {"loss": 0, "draw": 1, "win": 2}
    improvements: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    unchanged = 0
    baseline_crowns = 0.0
    candidate_crowns = 0.0
    for key in sorted(before):
        old = before[key]
        new = after[key]
        for deck_key in ("candidate_deck", "opponent_deck"):
            if canonical_deck(old[deck_key]) != canonical_deck(new[deck_key]):
                raise ValueError(f"game {key!r} changed {deck_key}")
        old_outcome = str(old["outcome"])
        new_outcome = str(new["outcome"])
        if old_outcome not in rank or new_outcome not in rank:
            raise ValueError(f"game {key!r} has an invalid outcome")
        old_crowns = float(old["candidate_crowns"]) - float(old["opponent_crowns"])
        new_crowns = float(new["candidate_crowns"]) - float(new["opponent_crowns"])
        baseline_crowns += old_crowns
        candidate_crowns += new_crowns
        change = {
            "matchup_seed": key[0],
            "candidate_player": key[1],
            "baseline_outcome": old_outcome,
            "candidate_outcome": new_outcome,
            "baseline_crown_difference": old_crowns,
            "candidate_crown_difference": new_crowns,
        }
        if rank[new_outcome] > rank[old_outcome]:
            improvements.append(change)
        elif rank[new_outcome] < rank[old_outcome]:
            regressions.append(change)
        else:
            unchanged += 1
    return {
        "games": len(before),
        "improvements": improvements,
        "regressions": regressions,
        "improvement_count": len(improvements),
        "regression_count": len(regressions),
        "unchanged_count": unchanged,
        "baseline_crown_difference": baseline_crowns,
        "candidate_crown_difference": candidate_crowns,
        "crown_difference_change": candidate_crowns - baseline_crowns,
        "passes_strict_no_regression": not regressions,
    }


def deck_archetype_index(deck_rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, ...], str]:
    index: dict[tuple[str, ...], str] = {}
    for row in deck_rows:
        cards = canonical_deck(row.get("cards", ()))
        archetype = str(row.get("archetype", ""))
        if len(cards) != 8 or not archetype:
            raise ValueError("every benchmark deck needs eight cards and an archetype")
        previous = index.setdefault(cards, archetype)
        if previous != archetype:
            raise ValueError("the same deck cannot belong to two archetypes")
    return index


def summarize_deck_records(
    records: Iterable[Mapping[str, Any]],
    *,
    archetypes_by_deck: Mapping[tuple[str, ...], str],
) -> dict[str, Any]:
    counters: dict[tuple[str, str], dict[str, float]] = defaultdict(
        lambda: {
            "games": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "draws": 0.0,
            "crown_difference": 0.0,
        }
    )
    observed_candidate_decks: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    for record in records:
        candidate_deck = canonical_deck(record.get("candidate_deck", ()))
        opponent_deck = canonical_deck(record.get("opponent_deck", ()))
        try:
            candidate_archetype = archetypes_by_deck[candidate_deck]
            opponent_archetype = archetypes_by_deck[opponent_deck]
        except KeyError as exc:
            raise ValueError("game record contains a deck outside the benchmark pool") from exc
        outcome = str(record.get("outcome"))
        if outcome not in {"win", "loss", "draw"}:
            raise ValueError(f"unknown game outcome {outcome!r}")
        observed_candidate_decks[candidate_archetype].add(candidate_deck)
        values = counters[(candidate_archetype, opponent_archetype)]
        values["games"] += 1.0
        outcome_key = {
            "win": "wins",
            "loss": "losses",
            "draw": "draws",
        }[outcome]
        values[outcome_key] += 1.0
        values["crown_difference"] += float(record["candidate_crowns"]) - float(
            record["opponent_crowns"]
        )

    def finalize(values: Mapping[str, float]) -> dict[str, float | int]:
        games = int(values["games"])
        wins = int(values["wins"])
        losses = int(values["losses"])
        draws = int(values["draws"])
        return {
            "games": games,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "score_rate": (wins + 0.5 * draws) / max(1, games),
            "crown_difference_per_game": values["crown_difference"] / max(1, games),
        }

    by_archetype: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "games": 0.0,
            "wins": 0.0,
            "losses": 0.0,
            "draws": 0.0,
            "crown_difference": 0.0,
        }
    )
    for (candidate_archetype, _), values in counters.items():
        for key, value in values.items():
            by_archetype[candidate_archetype][key] += value

    return {
        "archetypes": {
            archetype: {
                **finalize(values),
                "distinct_candidate_decks": len(observed_candidate_decks[archetype]),
            }
            for archetype, values in sorted(by_archetype.items())
        },
        "matchups": {
            f"{candidate}_vs_{opponent}": finalize(values)
            for (candidate, opponent), values in sorted(counters.items())
        },
    }
