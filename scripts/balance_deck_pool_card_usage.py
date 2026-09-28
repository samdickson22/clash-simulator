"""Reweight a deck pool for card exposure without changing deck membership."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


def _signature(row: dict[str, Any]) -> tuple[str, ...]:
    cards = tuple(sorted(str(card) for card in row.get("cards", ())))
    if len(cards) != 8 or len(set(cards)) != 8:
        raise ValueError("every deck must contain exactly eight unique cards")
    return cards


def _summary(frequencies: np.ndarray) -> dict[str, float]:
    mean = float(frequencies.mean())
    return {
        "minimum": float(frequencies.min()),
        "maximum": float(frequencies.max()),
        "maximum_to_minimum_ratio": float(frequencies.max() / frequencies.min()),
        "coefficient_of_variation": float(frequencies.std() / mean),
    }


def _project_bounded_sum(
    values: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    target: float,
) -> np.ndarray:
    if lower.sum() > target or upper.sum() < target:
        raise ValueError("bounded weight projection is infeasible")
    low = 0.0
    high = 1.0
    while float(np.clip(values * high, lower, upper).sum()) < target:
        high *= 2.0
    for _ in range(80):
        midpoint = (low + high) / 2.0
        total = float(np.clip(values * midpoint, lower, upper).sum())
        if total < target:
            low = midpoint
        else:
            high = midpoint
    result = np.clip(values * high, lower, upper)
    if not math.isclose(float(result.sum()), target, abs_tol=1e-12):
        raise AssertionError("bounded projection did not preserve target mass")
    return result


def balance_card_usage(
    payload: dict[str, Any],
    *,
    iterations: int,
    learning_rate: float,
    weight_ratio_cap: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = payload.get("decks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("source deck pool must contain decks")
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not math.isfinite(learning_rate) or learning_rate <= 0.0:
        raise ValueError("learning rate must be finite and positive")
    if not math.isfinite(weight_ratio_cap) or weight_ratio_cap <= 1.0:
        raise ValueError("weight ratio cap must be finite and greater than one")

    signatures: set[tuple[str, ...]] = set()
    archetypes: list[str] = []
    cards: set[str] = set()
    raw_weights: list[float] = []
    for raw in rows:
        if not isinstance(raw, dict):
            raise TypeError("deck rows must be objects")
        signature = _signature(raw)
        if signature in signatures:
            raise ValueError("source deck pool contains a duplicate signature")
        signatures.add(signature)
        cards.update(signature)
        archetype = str(raw.get("archetype", ""))
        if not archetype:
            raise ValueError("every deck must identify an archetype")
        archetypes.append(archetype)
        weight = float(raw.get("sampling_weight", 1.0))
        if not math.isfinite(weight) or weight <= 0.0:
            raise ValueError("deck sampling weights must be finite and positive")
        raw_weights.append(weight)

    card_names = sorted(cards)
    archetype_names = sorted(set(archetypes))
    card_index = {name: index for index, name in enumerate(card_names)}
    count = len(rows)
    incidence = np.zeros((len(card_names), count), dtype=np.float64)
    groups: dict[str, np.ndarray] = {}
    for column, raw in enumerate(rows):
        for card in raw["cards"]:
            incidence[card_index[str(card)], column] = 1.0
    for archetype in archetype_names:
        groups[archetype] = np.asarray(
            [value == archetype for value in archetypes], dtype=np.bool_
        )

    base = np.asarray(raw_weights, dtype=np.float64)
    base /= base.sum()
    weights = base.copy()
    lower = base / weight_ratio_cap
    upper = base * weight_ratio_cap
    target_archetype_mass = 1.0 / len(archetype_names)
    target_card_frequency = 8.0 / len(card_names)
    before = incidence @ base
    for _ in range(iterations):
        frequencies = incidence @ weights
        relative_error = (target_card_frequency - frequencies) / target_card_frequency
        deck_signal = (incidence.T @ relative_error) / 8.0
        weights *= np.exp(np.clip(learning_rate * deck_signal, -0.2, 0.2))
        for mask in groups.values():
            weights[mask] = _project_bounded_sum(
                weights[mask],
                lower[mask],
                upper[mask],
                target_archetype_mass,
            )
    after = incidence @ weights
    if (
        _summary(after)["maximum_to_minimum_ratio"]
        >= _summary(before)["maximum_to_minimum_ratio"]
    ):
        raise ValueError("card balancing did not improve weighted exposure")

    output_rows = [
        {**raw, "sampling_weight": float(weight)}
        for raw, weight in zip(rows, weights, strict=True)
    ]
    output = {
        **payload,
        "decks": output_rows,
        "metadata": {
            **dict(payload.get("metadata", {})),
            "card_usage_balanced": True,
            "card_usage_balance_iterations": iterations,
            "card_usage_balance_learning_rate": learning_rate,
            "card_usage_balance_weight_ratio_cap": weight_ratio_cap,
        },
    }
    archetype_mass = {name: float(weights[mask].sum()) for name, mask in groups.items()}
    report = {
        "schema_version": 1,
        "method": "bounded-multiplicative-card-exposure-v1",
        "decks": count,
        "cards": len(card_names),
        "archetypes": archetype_names,
        "iterations": iterations,
        "learning_rate": learning_rate,
        "weight_ratio_cap": weight_ratio_cap,
        "before": _summary(before),
        "after": _summary(after),
        "weight_ratio_minimum": float((weights / base).min()),
        "weight_ratio_maximum": float((weights / base).max()),
        "archetype_mass": archetype_mass,
        "signature_changes": 0,
        "card_frequencies": {
            name: {
                "before": float(before[index]),
                "after": float(after[index]),
            }
            for index, name in enumerate(card_names)
        },
    }
    return output, report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    parser.add_argument("--weight-ratio-cap", type=float, default=10.0)
    args = parser.parse_args()
    if args.output.exists() or args.report_out.exists():
        raise SystemExit("refusing to overwrite card-balanced deck artifacts")
    payload = json.loads(args.source.read_text(encoding="utf-8"))
    output, report = balance_card_usage(
        payload,
        iterations=args.iterations,
        learning_rate=args.learning_rate,
        weight_ratio_cap=args.weight_ratio_cap,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report.update(
        {
            "source": str(args.source.resolve()),
            "source_sha256": _sha256(args.source),
            "output": str(args.output.resolve()),
            "output_sha256": _sha256(args.output),
        }
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
