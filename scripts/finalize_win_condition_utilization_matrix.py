"""Validate matched utilization evidence for every designated win condition."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.build_win_condition_utilization_matrix import (
    WIN_CONDITION_SPECS,
    WinConditionSpec,
    _selection_key,
)
from scripts.evaluate_win_condition_utilization import (
    promotion_gate,
    summarize_utilization,
)
from scripts.finalize_mechanics_slot_gameplay_gate import (
    _object,
    _same_path,
    _sha256,
    _verify_comparison_context,
    _verify_eval_context,
)


def _verify_utilization(
    payload: dict[str, Any],
    *,
    decisions_path: Path,
    games_path: Path,
    card: str,
) -> dict[str, Any]:
    if not _same_path(payload.get("decisions"), decisions_path) or payload.get(
        "decisions_sha256"
    ) != _sha256(decisions_path):
        raise ValueError(f"{card} utilization decision provenance mismatch")
    if not _same_path(payload.get("game_records"), games_path) or payload.get(
        "game_records_sha256"
    ) != _sha256(games_path):
        raise ValueError(f"{card} utilization game provenance mismatch")
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    games = json.loads(games_path.read_text(encoding="utf-8"))
    if not isinstance(decisions, list) or not isinstance(games, list):
        raise TypeError(f"{card} decision and game records must be arrays")
    expected = summarize_utilization(
        decisions,
        games,
        role="designated_win_condition",
        designated_cards={card},
    )
    expected["gate"] = promotion_gate(
        expected,
        max_zero_use_rate=0.0,
        min_window_conversion_rate=0.25,
        min_games_per_seat=1,
    )
    expected.update(
        {
            "decisions": str(decisions_path.resolve()),
            "decisions_sha256": _sha256(decisions_path),
            "game_records": str(games_path.resolve()),
            "game_records_sha256": _sha256(games_path),
        }
    )
    if payload != expected:
        raise ValueError(f"{card} utilization does not match its decision records")
    return payload


def _optional_finite_rate(payload: dict[str, Any], name: str) -> float | None:
    raw = payload.get(name)
    if raw is None:
        return None
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"utilization has non-finite {name}")
    return value


def verify_win_condition_manifest(
    *,
    manifest_path: Path,
    validation_pool: Path,
    heldout_pool: Path,
) -> list[tuple[WinConditionSpec, Path]]:
    """Re-derive every frozen singleton deck from its authoritative source pool."""

    manifest = _object(manifest_path)
    if manifest.get("schema") != "clasher-win-condition-utilization-matrix-v1":
        raise ValueError("unsupported win-condition utilization matrix")
    if (
        not _same_path(manifest.get("validation_pool"), validation_pool)
        or manifest.get("validation_pool_sha256") != _sha256(validation_pool)
        or not _same_path(manifest.get("heldout_pool"), heldout_pool)
        or manifest.get("heldout_pool_sha256") != _sha256(heldout_pool)
    ):
        raise ValueError("win-condition matrix source pool changed")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != len(WIN_CONDITION_SPECS):
        raise ValueError("win-condition matrix entry count is incomplete")
    source_payloads = {
        "validation": _object(validation_pool),
        "heldout": _object(heldout_pool),
    }
    resolved: list[tuple[WinConditionSpec, Path]] = []
    for entry, spec in zip(entries, WIN_CONDITION_SPECS, strict=True):
        if not isinstance(entry, dict):
            raise TypeError("win-condition matrix entry must be an object")
        if (
            entry.get("archetype") != spec.archetype
            or entry.get("designated_card") != spec.card
            or entry.get("source_pool") != spec.source
        ):
            raise ValueError("win-condition matrix taxonomy or order changed")
        source_decks = source_payloads[spec.source].get("decks")
        if not isinstance(source_decks, list):
            raise TypeError(f"{spec.source} pool lacks a deck array")
        matches = [
            row
            for row in source_decks
            if isinstance(row, dict)
            and row.get("archetype") == spec.archetype
            and spec.card in row.get("cards", ())
        ]
        if not matches:
            raise ValueError(
                f"source pool no longer contains {spec.archetype}/{spec.card}"
            )
        selected = min(matches, key=_selection_key)
        cards = [str(card) for card in selected.get("cards", ())]
        if len(cards) != 8 or len(set(cards)) != 8:
            raise ValueError(f"source deck is not eight unique cards: {spec.archetype}")
        deck_pool = Path(str(entry.get("deck_pool", ""))).resolve()
        if not deck_pool.is_file() or entry.get("deck_pool_sha256") != _sha256(
            deck_pool
        ):
            raise ValueError(f"win-condition deck pool changed: {spec.archetype}")
        expected_deck = {**selected, "cards": cards, "sampling_weight": 1.0}
        expected_pool = {
            "schema_version": 1,
            "metadata": {
                "purpose": "win_condition_utilization_evaluation",
                "archetype": spec.archetype,
                "designated_card": spec.card,
                "source_pool": spec.source,
            },
            "decks": [expected_deck],
        }
        if (
            _object(deck_pool) != expected_pool
            or entry.get("source_deck") != str(selected.get("name", ""))
            or entry.get("signature") != sorted(cards)
        ):
            raise ValueError(f"matrix deck provenance changed: {spec.archetype}")
        resolved.append((spec, deck_pool))
    return resolved


def finalize_win_condition_matrix(
    *,
    root: Path,
    manifest_path: Path,
    validation_pool: Path,
    heldout_pool: Path,
    parent: Path,
    candidate: Path,
) -> dict[str, Any]:
    resolved_entries = verify_win_condition_manifest(
        manifest_path=manifest_path,
        validation_pool=validation_pool,
        heldout_pool=heldout_pool,
    )

    results: dict[str, dict[str, Any]] = {}
    evidence_paths = [
        manifest_path,
        validation_pool,
        heldout_pool,
        *(deck_pool for _, deck_pool in resolved_entries),
    ]
    for index, (spec, deck_pool) in enumerate(resolved_entries):
        tag = spec.archetype.replace("-", "_")
        seed = 1_056_401 + index
        role_payloads: dict[str, dict[str, Any]] = {}
        for role, checkpoint in (("parent", parent), ("candidate", candidate)):
            metrics_path = root / f"{role}_{tag}2.metrics.json"
            games_path = root / f"{role}_{tag}2.games.json"
            decisions_path = root / f"{role}_{tag}2.decisions.json"
            utilization_path = root / f"{role}_{tag}2.utilization.json"
            _verify_eval_context(
                _object(metrics_path),
                checkpoint=checkpoint,
                opponent_checkpoint=None,
                decks_path=deck_pool,
                games=2,
                seed=seed,
                opponent_mode="strategy",
                opponent_strategy="balanced",
            )
            role_payloads[role] = _verify_utilization(
                _object(utilization_path),
                decisions_path=decisions_path,
                games_path=games_path,
                card=spec.card,
            )
            evidence_paths.extend(
                [metrics_path, games_path, decisions_path, utilization_path]
            )
        comparison_path = root / f"{tag}2.compare.json"
        comparison = _verify_comparison_context(
            _object(comparison_path),
            baseline=root / f"parent_{tag}2.games.json",
            candidate=root / f"candidate_{tag}2.games.json",
            games=2,
        )
        evidence_paths.append(comparison_path)
        before = role_payloads["parent"]
        after = role_payloads["candidate"]
        candidate_conversion = _optional_finite_rate(
            after, "window_conversion_rate"
        )
        candidate_probability = _optional_finite_rate(
            after, "mean_role_probability_when_legal_affordable"
        )
        parent_conversion = _optional_finite_rate(before, "window_conversion_rate")
        parent_probability = _optional_finite_rate(
            before, "mean_role_probability_when_legal_affordable"
        )
        gates = {
            "absolute_candidate_use": after.get("gate", {}).get("passed") is True,
            "strict_outcome_no_regression": comparison.get(
                "passes_strict_no_regression"
            )
            is True,
            "zero_use_no_regression": int(after["zero_use_games"])
            <= int(before["zero_use_games"]),
            "conversion_no_regression": candidate_conversion is not None
            and (
                parent_conversion is None
                or candidate_conversion >= parent_conversion - 0.02
            ),
            "probability_no_regression": candidate_probability is not None
            and (
                parent_probability is None
                or candidate_probability >= parent_probability - 0.02
            ),
        }
        results[spec.archetype] = {
            "designated_card": spec.card,
            "source_pool": spec.source,
            "deck_pool": str(deck_pool),
            "seed": seed,
            "parent": before,
            "candidate": after,
            "comparison": comparison,
            "gates": gates,
            "passes": all(gates.values()),
        }

    passes = all(row["passes"] for row in results.values())
    return {
        "schema": "clasher-win-condition-utilization-evidence-v1",
        "status": "passed" if passes else "rejected",
        "passes": passes,
        "parent": str(parent.resolve()),
        "parent_sha256": _sha256(parent),
        "candidate": str(candidate.resolve()),
        "candidate_sha256": _sha256(candidate),
        "manifest": str(manifest_path.resolve()),
        "manifest_sha256": _sha256(manifest_path),
        "archetypes": results,
        "evidence_sha256": {
            str(path.resolve()): _sha256(path) for path in evidence_paths
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--validation-pool", required=True, type=Path)
    parser.add_argument("--heldout-pool", required=True, type=Path)
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = finalize_win_condition_matrix(
        root=args.root,
        manifest_path=args.manifest,
        validation_pool=args.validation_pool,
        heldout_pool=args.heldout_pool,
        parent=args.parent,
        candidate=args.candidate,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
