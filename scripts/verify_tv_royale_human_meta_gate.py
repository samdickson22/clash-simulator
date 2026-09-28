"""Verify breadth and exact artifacts for the reserved TV Royale meta gate."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from clasher.rl.oracle_corpus import file_sha256

MINIMUM_DECKS = 8
MINIMUM_ARCHETYPES = 6
MINIMUM_REPLAYS = 16
MINIMUM_SAMPLES = 500


def _signature(cards: object) -> tuple[str, ...]:
    if not isinstance(cards, list):
        raise TypeError("human-meta cards must be a list")
    signature = tuple(sorted(str(card) for card in cards))
    if len(signature) != 8 or len(set(signature)) != 8:
        raise ValueError("human-meta decks must contain eight unique cards")
    return signature


def _artifact_decks(
    artifact_path: Path,
    *,
    weighting: str,
) -> dict[str, dict[str, Any]]:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError(f"invalid human-meta artifact schema: {artifact_path}")
    metadata = payload.get("metadata", {})
    if metadata.get("weighting") != weighting:
        raise ValueError(f"human-meta artifact weighting mismatch: {artifact_path}")
    rows = payload.get("decks")
    if not isinstance(rows, list):
        raise TypeError(f"human-meta artifact decks are not a list: {artifact_path}")
    by_hash: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("human-meta artifact deck is not an object")
        deck_hash = str(row.get("deck_hash", ""))
        if not deck_hash or deck_hash in by_hash:
            raise ValueError("human-meta artifact contains a missing/duplicate hash")
        _signature(row.get("cards"))
        by_hash[deck_hash] = row
    return by_hash


def verify_human_meta_gate(manifest_path: Path, *, target_games: int) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("human-meta manifest requires schema version 1")
    if int(payload.get("source_games", -1)) != target_games:
        raise ValueError(
            "human-meta source game count mismatch: "
            f"expected {target_games}, got {payload.get('source_games')}"
        )
    if payload.get("training_action_labels_used") is not False:
        raise ValueError("human-meta gate must remain evaluation-only")
    if payload.get("intended_use") != "final-evaluation-only":
        raise ValueError("human-meta gate intended-use mismatch")
    min_replays = int(payload.get("min_replays", 0))
    if min_replays < 2:
        raise ValueError("human-meta recurrence minimum must be at least two")

    decks = payload.get("decks")
    if not isinstance(decks, list):
        raise TypeError("human-meta manifest decks are not a list")
    hashes: set[str] = set()
    signatures: set[tuple[str, ...]] = set()
    replay_ids: set[str] = set()
    archetypes: Counter[str] = Counter()
    selected_replays = 0
    selected_samples = 0
    manifest_rows: dict[str, dict[str, Any]] = {}
    for row in decks:
        if not isinstance(row, dict):
            raise TypeError("human-meta manifest deck is not an object")
        deck_hash = str(row.get("deck_hash", ""))
        signature = _signature(row.get("cards"))
        archetype = str(row.get("archetype", ""))
        replays = row.get("replays")
        samples = int(row.get("samples", 0))
        if not deck_hash or deck_hash in hashes:
            raise ValueError("human-meta manifest contains a missing/duplicate hash")
        if signature in signatures:
            raise ValueError("human-meta manifest contains a duplicate deck")
        if not archetype:
            raise ValueError("human-meta manifest deck lacks an archetype")
        if not isinstance(replays, list) or len(set(map(str, replays))) < min_replays:
            raise ValueError("human-meta manifest deck lacks recurring replays")
        replay_set = {str(replay) for replay in replays}
        overlap = replay_ids.intersection(replay_set)
        if overlap:
            raise ValueError(f"human-meta replays occur in multiple decks: {overlap}")
        if samples <= 0:
            raise ValueError("human-meta manifest deck has no samples")
        hashes.add(deck_hash)
        signatures.add(signature)
        replay_ids.update(replay_set)
        archetypes[archetype] += 1
        selected_replays += len(replay_set)
        selected_samples += samples
        manifest_rows[deck_hash] = row

    failures: dict[str, dict[str, int]] = {}
    actuals = {
        "selected_decks": len(decks),
        "selected_archetypes": len(archetypes),
        "selected_replays": selected_replays,
        "selected_samples": selected_samples,
    }
    minimums = {
        "selected_decks": MINIMUM_DECKS,
        "selected_archetypes": MINIMUM_ARCHETYPES,
        "selected_replays": MINIMUM_REPLAYS,
        "selected_samples": MINIMUM_SAMPLES,
    }
    for key, required in minimums.items():
        if actuals[key] < required:
            failures[key] = {"required": required, "actual": actuals[key]}
    if failures:
        raise ValueError(f"human-meta gate is too narrow: {failures}")

    accounting = {
        "selected_decks": len(decks),
        "selected_replays": selected_replays,
        "selected_samples": selected_samples,
        "selected_archetypes": dict(sorted(archetypes.items())),
    }
    mismatches = {
        key: {"expected": expected, "actual": payload.get(key)}
        for key, expected in accounting.items()
        if payload.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"human-meta manifest accounting mismatch: {mismatches}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise TypeError("human-meta manifest lacks artifacts")
    for name, weighting in (
        ("uniform", "uniform-per-deck"),
        ("frequency_weighted", "observed-replay-frequency"),
    ):
        published = artifacts.get(name)
        if not isinstance(published, dict):
            raise TypeError(f"human-meta manifest lacks {name} artifact")
        path = Path(str(published.get("path", ""))).resolve()
        if not path.is_file() or file_sha256(path) != published.get("sha256"):
            raise ValueError(f"human-meta {name} artifact digest mismatch")
        artifact_rows = _artifact_decks(path, weighting=weighting)
        if set(artifact_rows) != hashes:
            raise ValueError(f"human-meta {name} artifact deck set mismatch")
        for deck_hash, artifact_row in artifact_rows.items():
            manifest_row = manifest_rows[deck_hash]
            if (
                _signature(artifact_row.get("cards"))
                != _signature(manifest_row.get("cards"))
                or artifact_row.get("archetype") != manifest_row.get("archetype")
                or int(artifact_row.get("observed_replays", -1))
                != len(manifest_row["replays"])
                or int(artifact_row.get("observed_samples", -1))
                != int(manifest_row["samples"])
            ):
                raise ValueError(f"human-meta {name} artifact row mismatch")
            expected_weight = (
                1.0 if name == "uniform" else float(len(manifest_row["replays"]))
            )
            if float(artifact_row.get("sampling_weight", -1.0)) != expected_weight:
                raise ValueError(f"human-meta {name} sampling weight mismatch")

    return {
        "status": "human_meta_gate_verified",
        "source_games": target_games,
        **actuals,
        "archetypes": dict(sorted(archetypes.items())),
        "minimum_decks": MINIMUM_DECKS,
        "minimum_archetypes": MINIMUM_ARCHETYPES,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-games", required=True, type=int)
    args = parser.parse_args()
    print(
        json.dumps(
            verify_human_meta_gate(args.manifest, target_games=args.target_games),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
