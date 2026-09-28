"""Fail-closed baseline gate for an exactly neutral mechanics RL initializer."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.finalize_mechanics_slot_gameplay_gate import (
    PAIRED_SPECS,
    PAIRED_WORKLOADS,
    _object,
    _same_path,
    _sha256,
    _verify_eval_context,
)


def _canonical_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _verify_equivalence_report(
    report: dict[str, Any],
    *,
    source_checkpoint: Path,
    candidate_checkpoint: Path,
) -> None:
    evidence_sha = report.get("evidence_sha256")
    unsigned = dict(report)
    unsigned.pop("evidence_sha256", None)
    checks = {
        "schema": int(report.get("schema_version", -1)) == 1,
        "source_checkpoint": _same_path(
            report.get("source_checkpoint"), source_checkpoint
        ),
        "source_checkpoint_sha256": report.get("source_checkpoint_sha256")
        == _sha256(source_checkpoint),
        "candidate_checkpoint": _same_path(
            report.get("candidate_checkpoint"), candidate_checkpoint
        ),
        "candidate_checkpoint_sha256": report.get("candidate_checkpoint_sha256")
        == _sha256(candidate_checkpoint),
        "evidence_sha256": evidence_sha == _canonical_sha256(unsigned),
        "exact_behavior": report.get("exact_behavior_preservation_verified") is True,
    }
    structure = report.get("structure") or {}
    runtime = report.get("runtime") or {}
    checks.update(
        {
            "query_zero": int(structure.get("query_nonzero_count", -1)) == 0,
            "inherited_tensors": int(structure.get("inherited_tensor_count", 0)) > 0,
            "new_tensors": set(structure.get("new_tensor_names") or ())
            == {
                "mechanics_slot_card_stats",
                "mechanics_slot_choice_query.weight",
            },
            "runtime_outputs": runtime.get("all_policy_outputs_bitwise_equal") is True,
            "runtime_actions": runtime.get("all_deterministic_actions_equal") is True,
            "runtime_sample_count": int(runtime.get("samples", 0)) >= 100,
            "runtime_action_count": int(
                runtime.get("deterministic_actions_compared", -1)
            )
            == int(runtime.get("samples", -2)),
            "runtime_episode_count": int(runtime.get("episodes", 0)) >= 2,
        }
    )
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError("zero-initializer equivalence mismatch: " + ", ".join(failed))


def _verify_game_records(
    path: Path,
    *,
    games: int,
    metrics: dict[str, Any],
) -> None:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != games:
        raise ValueError(f"game-record count mismatch: {path}")
    if [int(row.get("game", -1)) for row in records] != list(range(games)):
        raise ValueError(f"game-record indices are not contiguous: {path}")
    outcomes = [row.get("outcome") for row in records]
    expected = {
        "win": int(metrics.get("wins", -1)),
        "loss": int(metrics.get("losses", -1)),
        "draw": int(metrics.get("draws", -1)),
    }
    if {name: outcomes.count(name) for name in expected} != expected:
        raise ValueError(f"game-record outcomes differ from metrics: {path}")
    crown_difference = (
        sum(
            float(row["candidate_crowns"]) - float(row["opponent_crowns"])
            for row in records
        )
        / games
    )
    if abs(crown_difference - float(metrics["crown_diff_per_game"])) > 1e-12:
        raise ValueError(f"game-record crowns differ from metrics: {path}")
    seats = [int(row.get("candidate_player", -1)) for row in records]
    if seats.count(0) != games // 2 or seats.count(1) != games // 2:
        raise ValueError(f"game-record seats are not paired: {path}")


def finalize_zero_initializer(
    *,
    root: Path,
    equivalence_report: Path,
    source_checkpoint: Path,
    candidate_checkpoint: Path,
    heldout_decks: Path,
    hog_decks: Path,
) -> dict[str, Any]:
    for path in (
        equivalence_report,
        source_checkpoint,
        candidate_checkpoint,
        heldout_decks,
        hog_decks,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    _verify_equivalence_report(
        _object(equivalence_report),
        source_checkpoint=source_checkpoint,
        candidate_checkpoint=candidate_checkpoint,
    )

    metrics: dict[str, dict[str, Any]] = {}
    evidence_paths = [equivalence_report]
    for name in PAIRED_WORKLOADS:
        games, seed, mode, strategy, deck_group = PAIRED_SPECS[name]
        decks = hog_decks if deck_group == "hog" else heldout_decks
        metrics_path = root / f"candidate_{name}.metrics.json"
        games_path = root / f"candidate_{name}.games.json"
        metrics[name] = _verify_eval_context(
            _object(metrics_path),
            checkpoint=candidate_checkpoint,
            opponent_checkpoint=None,
            decks_path=decks,
            games=games,
            seed=seed,
            opponent_mode=mode,
            opponent_strategy=strategy,
        )
        _verify_game_records(games_path, games=games, metrics=metrics[name])
        evidence_paths.extend((metrics_path, games_path))

    hog_utilization_path = root / "candidate_hog12.utilization.json"
    hog_decisions_path = root / "candidate_hog12.decisions.json"
    hog_games_path = root / "candidate_hog12.games.json"
    hog = _object(hog_utilization_path)
    if not _same_path(hog.get("decisions"), hog_decisions_path) or hog.get(
        "decisions_sha256"
    ) != _sha256(hog_decisions_path):
        raise ValueError("Hog utilization decision provenance mismatch")
    if not _same_path(hog.get("game_records"), hog_games_path) or hog.get(
        "game_records_sha256"
    ) != _sha256(hog_games_path):
        raise ValueError("Hog utilization game provenance mismatch")
    evidence_paths.extend((hog_decisions_path, hog_utilization_path))

    return {
        "schema": "zero-mechanics-rl-initializer-v1",
        "status": "rl_initializer_ready",
        "rl_initializer_eligible": True,
        "candidate_checkpoint": str(candidate_checkpoint.resolve()),
        "candidate_checkpoint_sha256": _sha256(candidate_checkpoint),
        "source_checkpoint": str(source_checkpoint.resolve()),
        "source_checkpoint_sha256": _sha256(source_checkpoint),
        "equivalence_report": str(equivalence_report.resolve()),
        "equivalence_report_sha256": _sha256(equivalence_report),
        "baseline_games": sum(spec[0] for spec in PAIRED_SPECS.values()),
        "workload_metrics": metrics,
        "hog": hog,
        "evidence_sha256": {
            str(path.resolve()): _sha256(path) for path in evidence_paths
        },
        "claim_scope": (
            "eligible only as an outcome-trained diversified PFSP initializer; "
            "the zero adapter itself makes no skill-improvement claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--equivalence-report", required=True, type=Path)
    parser.add_argument("--source-checkpoint", required=True, type=Path)
    parser.add_argument("--candidate-checkpoint", required=True, type=Path)
    parser.add_argument("--heldout-decks", required=True, type=Path)
    parser.add_argument("--hog-decks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = finalize_zero_initializer(
        root=args.root,
        equivalence_report=args.equivalence_report,
        source_checkpoint=args.source_checkpoint,
        candidate_checkpoint=args.candidate_checkpoint,
        heldout_decks=args.heldout_decks,
        hog_decks=args.hog_decks,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
