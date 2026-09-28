"""Verify exact chronology separation for the final post-development replay split."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.replay_split import complete_visible_hand_mask


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return payload


def _publishable_replay_ids(
    records: list[dict[str, Any]],
) -> tuple[set[str], set[str]]:
    """Recompute the split publisher's exact complete-visible-hand gate."""
    publishable: set[str] = set()
    excluded: set[str] = set()
    for record in records:
        replay = str(record["replay"])
        corpus = Path(str(record.get("corpus", ""))).resolve()
        if not corpus.is_file():
            raise FileNotFoundError(f"missing source corpus for replay {replay}: {corpus}")
        expected_sha = str(record.get("corpus_sha256", ""))
        if not expected_sha or _sha256(corpus) != expected_sha:
            raise ValueError(f"source corpus digest mismatch for replay {replay}")
        with np.load(corpus, allow_pickle=False) as payload:
            if "hand_ids" not in payload:
                raise ValueError(f"source corpus lacks hand_ids for replay {replay}")
            hand_ids = payload["hand_ids"]
        if hand_ids.ndim != 2 or hand_ids.shape[1] < 4:
            raise ValueError(f"invalid hand_ids shape for replay {replay}: {hand_ids.shape}")
        target = publishable if np.any(complete_visible_hand_mask(hand_ids)) else excluded
        target.add(replay)
    return publishable, excluded


def verify_post260_split(
    *,
    split_manifest_path: Path,
    run_manifest_path: Path,
    target_games: int = 1_000,
    reserved_games: int = 260,
) -> dict[str, Any]:
    if target_games <= 0 or not 0 <= reserved_games < target_games:
        raise ValueError("invalid target/reserved replay counts")
    run = _object(run_manifest_path)
    split = _object(split_manifest_path)
    completed_rows = [
        row
        for row in run.get("records", ())
        if isinstance(row, dict) and row.get("status") == "complete"
    ]
    completed = [str(row["replay"]) for row in completed_rows]
    if len(completed) != target_games or len(set(completed)) != target_games:
        raise ValueError("run manifest must contain exactly the unique target games")
    expected_reserved = set(completed[:reserved_games])
    expected_partition = set(completed[reserved_games:])
    expected_publishable, expected_excluded = _publishable_replay_ids(
        completed_rows[reserved_games:]
    )
    if expected_publishable.union(expected_excluded) != expected_partition:
        raise AssertionError("complete-hand eligibility did not partition source replays")
    declared_reserved = {
        str(value) for value in split.get("reserved_replay_ids", ())
    }
    if declared_reserved != expected_reserved:
        raise ValueError("reserved replay IDs are not the exact development prefix")
    expected_source = run_manifest_path.resolve()
    if Path(str(split.get("source_run_manifest", ""))).resolve() != expected_source:
        raise ValueError("split identifies another source run manifest")
    if split.get("source_run_manifest_sha256") != _sha256(run_manifest_path):
        raise ValueError("source run manifest changed after split publication")
    scalar_checks = {
        "source_replays": int(split.get("source_replays", -1)) == target_games,
        "reserved_final_evaluation_replays": int(
            split.get("reserved_final_evaluation_replays", -1)
        )
        == reserved_games,
        "total_replays": int(split.get("total_replays", -1))
        == len(expected_publishable),
    }
    failed = [name for name, passed in scalar_checks.items() if not passed]
    if failed:
        raise ValueError("post-development split count mismatch: " + ", ".join(failed))
    split_rows = split.get("splits")
    required = {"train", "validation", "archetype_test", "chronology_test"}
    if not isinstance(split_rows, dict) or set(split_rows) != required:
        raise ValueError("post-development split partitions are incomplete")
    observed: list[str] = []
    considered = 0
    removed = 0
    for name, row in split_rows.items():
        if not isinstance(row, dict):
            raise TypeError(f"split row must be an object: {name}")
        replay_ids = [str(value) for value in row.get("replay_ids", ())]
        if int(row.get("replays", -1)) != len(replay_ids):
            raise ValueError(f"split replay count disagrees with IDs: {name}")
        considered += int(row.get("source_replays_considered", -1))
        removed += int(row.get("replays_removed_no_complete_hand", -1))
        observed.extend(replay_ids)
    if len(observed) != len(set(observed)):
        raise ValueError("a replay occurs in more than one post-development split")
    if set(observed) != expected_publishable:
        raise ValueError(
            "post-development splits do not exactly cover publishable games 261-1000"
        )
    if considered != len(expected_partition):
        raise ValueError("split source-considered counts do not cover games 261-1000")
    if removed != len(expected_excluded):
        raise ValueError("split complete-hand exclusion count mismatch")
    invariants = split.get("invariants")
    if not isinstance(invariants, dict):
        raise TypeError("post-development split lacks invariants")
    for name in (
        "replay_overlap",
        "deck_signature_overlap",
        "held_out_archetype_train_overlap",
    ):
        if int(invariants.get(name, -1)) != 0:
            raise ValueError(f"post-development split invariant failed: {name}")
    return {
        "schema": "tv-royale-post-development-split-verification-v1",
        "status": "post260_inputs_verified",
        "source_replays": target_games,
        "reserved_replays": reserved_games,
        "post_reserve_replays": target_games - reserved_games,
        "partition_replays": len(expected_publishable),
        "excluded_no_complete_hand_replays": len(expected_excluded),
        "split_manifest": str(split_manifest_path.resolve()),
        "split_manifest_sha256": _sha256(split_manifest_path),
        "run_manifest": str(run_manifest_path.resolve()),
        "run_manifest_sha256": _sha256(run_manifest_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-manifest", required=True, type=Path)
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--target-games", type=int, default=1_000)
    parser.add_argument("--reserved-games", type=int, default=260)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    payload = verify_post260_split(
        split_manifest_path=args.split_manifest,
        run_manifest_path=args.run_manifest,
        target_games=args.target_games,
        reserved_games=args.reserved_games,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
