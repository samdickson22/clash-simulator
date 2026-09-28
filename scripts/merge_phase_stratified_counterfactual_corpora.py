"""Merge uniform phase roots with screened real-overtime supplements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from scripts.combine_terminal_counterfactual_corpora import _sha256


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(
    *,
    uniform_npz: Path,
    uniform_report_path: Path,
    overtime_npz: Path,
    overtime_report_path: Path,
    output: Path,
    report_path: Path,
) -> dict[str, Any]:
    uniform_report = json.loads(uniform_report_path.read_text(encoding="utf-8"))
    overtime_report = json.loads(overtime_report_path.read_text(encoding="utf-8"))
    authority_keys = (
        "schema_version",
        "policy",
        "outcome",
        "candidate_card_semantics_version",
        "candidate_card_feature_size",
        "best_action_order",
        "structured_state_contract",
        "learner_sampling_decks_path",
        "opponent_sampling_decks_path",
        "input_sha256",
    )
    for key in authority_keys:
        if uniform_report.get(key) != overtime_report.get(key):
            raise ValueError(f"phase-stratified source authority differs at {key}")
    if uniform_report["query_schedule"] != "phase-balanced":
        raise ValueError("uniform phase source is not phase-balanced")
    if overtime_report["query_schedule"] != "phase-balanced" or list(
        overtime_report["query_target_ticks"]
    ) != [3600]:
        raise ValueError("overtime supplement is not the screened tick-3600 slice")
    with np.load(uniform_npz, allow_pickle=False) as uniform_source, np.load(
        overtime_npz, allow_pickle=False
    ) as overtime_source:
        if set(uniform_source.files) != set(overtime_source.files):
            raise ValueError("phase-stratified array names differ")
        arrays: dict[str, np.ndarray] = {}
        for name in uniform_source.files:
            uniform = np.asarray(uniform_source[name])
            overtime = np.asarray(overtime_source[name])
            if uniform.dtype != overtime.dtype or uniform.shape[1:] != overtime.shape[1:]:
                raise ValueError(f"phase-stratified array contract differs at {name}")
            arrays[name] = np.concatenate((uniform, overtime), axis=0)
    keys = list(zip(arrays["game_ids"].tolist(), arrays["ticks"].tolist(), strict=True))
    if len(keys) != len(set(keys)):
        raise ValueError("phase-stratified sources overlap by game and tick")
    if int((arrays["ticks"] >= 3600).sum()) < len(overtime_report["states"]):
        raise ValueError("phase-stratified overtime rows are not all overtime")
    if not np.array_equal(
        arrays["candidate_actions"] >= 0,
        arrays["candidate_valid"],
    ):
        raise ValueError("phase-stratified candidate validity disagrees")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        np.savez_compressed(handle, **arrays)  # type: ignore[arg-type]
    states = [*uniform_report["states"], *overtime_report["states"]]
    games = [*uniform_report["games"], *overtime_report["games"]]
    result = {
        **{
            key: uniform_report[key]
            for key in authority_keys
        },
        "query_schedule": "phase-stratified-uniform-plus-screened-overtime-v1",
        "query_target_ticks": list(uniform_report["query_target_ticks"]),
        "query_target_ticks_by_source": {
            "uniform": list(uniform_report["query_target_ticks"]),
            "screened_overtime": [3600],
        },
        "collection_config_by_source": {
            "uniform": uniform_report["collection_config"],
            "screened_overtime": overtime_report["collection_config"],
        },
        "sampling_decks_path": uniform_report.get("sampling_decks_path"),
        "sampling_decks_paths": uniform_report.get("sampling_decks_paths", []),
        "shards": int(uniform_report["shards"]) + int(overtime_report["shards"]),
        "states_collected": len(states),
        "uniform_states": len(uniform_report["states"]),
        "screened_overtime_states": len(overtime_report["states"]),
        "decisive_improvements": sum(
            bool(row["decisive_improvement"]) for row in states
        ),
        "base_terminal_wins": sum(float(row["base_score"]) == 1.0 for row in states),
        "array_shapes": {name: list(array.shape) for name, array in arrays.items()},
        "array_sha256": {name: _sha256(array) for name, array in arrays.items()},
        "output": str(output.resolve()),
        "source_artifacts": {
            str(uniform_npz.resolve()): _file_sha256(uniform_npz),
            str(uniform_report_path.resolve()): _file_sha256(uniform_report_path),
            str(overtime_npz.resolve()): _file_sha256(overtime_npz),
            str(overtime_report_path.resolve()): _file_sha256(overtime_report_path),
        },
        "games": sorted(games, key=lambda row: int(row["game"])),
        "states": states,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uniform-npz", type=Path, required=True)
    parser.add_argument("--uniform-report", type=Path, required=True)
    parser.add_argument("--overtime-npz", type=Path, required=True)
    parser.add_argument("--overtime-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = merge(
        uniform_npz=args.uniform_npz,
        uniform_report_path=args.uniform_report,
        overtime_npz=args.overtime_npz,
        overtime_report_path=args.overtime_report,
        output=args.output,
        report_path=args.report,
    )
    print(json.dumps({"states_collected": result["states_collected"]}, sort_keys=True))


if __name__ == "__main__":
    main()
