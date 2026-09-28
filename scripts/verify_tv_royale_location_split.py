"""Fail closed unless strict TV Royale location splits are trainable and broad."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.imitation import load_corpus
from clasher.rl.oracle_corpus import file_sha256

EXPECTED_SCHEMA = "tv-royale-raw-cascade-location-clock-splits-v1"

REQUIRED_INVARIANTS: dict[str, object] = {
    "replay_overlap": 0,
    "follows_type_split_assignments": True,
    "ignored_replays_are_reserved_only": True,
    "independent_rows": True,
    "required_training_sequence_length": 1,
    "spell_location_policy": "persistent-area-visual-only-v1",
    "location_label_source": "tv-royale-raw-cascade-location-visual-strict-v3",
}

SPLIT_MINIMUMS: dict[str, dict[str, float]] = {
    "train": {
        "samples": 200,
        "replays": 20,
        "distinct_target_cards": 20,
        "distinct_target_tiles": 50,
        "distinct_coarse_regions_3x4": 12,
        "covered_y_bands_4_rows": 3,
        "minority_side_fraction": 0.20,
    },
    "validation": {
        "samples": 50,
        "replays": 6,
        "distinct_target_cards": 8,
        "distinct_target_tiles": 15,
        "distinct_coarse_regions_3x4": 6,
        "covered_y_bands_4_rows": 2,
        "minority_side_fraction": 0.10,
    },
    "archetype_test": {
        "samples": 50,
        "replays": 6,
        "distinct_target_cards": 8,
        "distinct_target_tiles": 15,
        "distinct_coarse_regions_3x4": 6,
        "covered_y_bands_4_rows": 2,
        "minority_side_fraction": 0.10,
    },
    "chronology_test": {
        "samples": 25,
        "replays": 3,
        "distinct_target_cards": 5,
        "distinct_target_tiles": 10,
        "distinct_coarse_regions_3x4": 4,
        "covered_y_bands_4_rows": 2,
        "minority_side_fraction": 0.10,
    },
}


class LocationDataInsufficient(RuntimeError):
    """The split is structurally safe but too small or narrow to train."""

    def __init__(self, details: dict[str, dict[str, dict[str, float]]]) -> None:
        super().__init__("strict location data is insufficient")
        self.details = details


def _metric(split: dict[str, Any], key: str) -> float:
    source = split if key in {"samples", "replays"} else split.get("diversity", {})
    value = source.get(key, 0)
    if not isinstance(value, int | float):
        raise TypeError(f"location metric {key} is not numeric: {value!r}")
    return float(value)


def _published_path(
    row: dict[str, Any],
    *,
    path_key: str,
    digest_key: str,
    label: str,
) -> Path:
    path = Path(str(row.get(path_key, ""))).resolve()
    if not path.is_file() or file_sha256(path) != row.get(digest_key):
        raise ValueError(f"{label} artifact digest mismatch")
    return path


def verify_location_split(
    manifest_path: Path,
    *,
    target_games: int,
) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema") != EXPECTED_SCHEMA:
        raise ValueError("unexpected TV Royale location split schema")
    if int(payload.get("target_games", -1)) != target_games:
        raise ValueError(
            "TV Royale location target-game mismatch: "
            f"expected {target_games}, got {payload.get('target_games')}"
        )

    source_run_path = _published_path(
        payload,
        path_key="source_run_manifest",
        digest_key="source_run_manifest_sha256",
        label="source run manifest",
    )
    source_run = json.loads(source_run_path.read_text(encoding="utf-8"))
    if int(source_run.get("completed_games", -1)) != target_games:
        raise ValueError("source run does not contain the exact target games")

    source_split_path = _published_path(
        payload,
        path_key="source_split_manifest",
        digest_key="source_split_manifest_sha256",
        label="source type split manifest",
    )
    source_split = json.loads(source_split_path.read_text(encoding="utf-8"))
    if (
        int(source_split.get("schema_version", 0)) < 2
        or int(source_split.get("source_replays", -1)) != target_games
    ):
        raise ValueError("source type split is not the exact verified target split")

    invariants = payload.get("invariants", {})
    mismatches = {
        key: {"expected": expected, "actual": invariants.get(key)}
        for key, expected in REQUIRED_INVARIANTS.items()
        if invariants.get(key) != expected
    }
    splits = payload.get("splits", {})
    missing_splits = sorted(set(SPLIT_MINIMUMS).difference(splits))
    if mismatches or missing_splits:
        raise ValueError(
            "unsafe/incomplete location split: "
            f"mismatches={mismatches}, missing_splits={missing_splits}"
        )

    source_splits = source_split.get("splits", {})
    reserved_replays = {
        str(value) for value in source_split.get("reserved_replay_ids", ())
    }
    ignored_replays = {
        str(value) for value in payload.get("ignored_replay_ids", ())
    }
    if len(ignored_replays) != len(payload.get("ignored_replay_ids", ())):
        raise ValueError("location split contains duplicate ignored replay IDs")
    if not ignored_replays.issubset(reserved_replays):
        raise ValueError("location split ignores a non-reserved replay")

    assigned_replays: set[str] = set()
    assigned_samples = 0
    for name in SPLIT_MINIMUMS:
        row = splits[name]
        replay_ids = [str(value) for value in row.get("replay_ids", ())]
        replay_set = set(replay_ids)
        if len(replay_set) != len(replay_ids):
            raise ValueError(f"location split {name} contains duplicate replays")
        overlap = assigned_replays.intersection(replay_set)
        if overlap:
            raise ValueError(f"location replay overlap in {name}: {sorted(overlap)}")
        expected_replays = {
            str(value)
            for value in source_splits.get(name, {}).get("replay_ids", ())
        }
        if not replay_set.issubset(expected_replays):
            raise ValueError(f"location split {name} violates type-split assignment")
        if int(row.get("replays", -1)) != len(replay_ids):
            raise ValueError(f"location split {name} replay accounting mismatch")

        output_path = _published_path(
            row,
            path_key="output",
            digest_key="output_sha256",
            label=f"location split {name}",
        )
        corpus_manifest_path = _published_path(
            row,
            path_key="manifest",
            digest_key="manifest_sha256",
            label=f"location split {name} corpus manifest",
        )
        corpus_manifest = json.loads(
            corpus_manifest_path.read_text(encoding="utf-8")
        )
        if (
            int(corpus_manifest.get("schema_version", 0)) != 1
            or Path(str(corpus_manifest.get("output", ""))).resolve()
            != output_path
            or corpus_manifest.get("output_sha256") != row.get("output_sha256")
            or corpus_manifest.get("independent_rows") is not True
            or int(corpus_manifest.get("samples", -1))
            != int(row.get("samples", -2))
        ):
            raise ValueError(f"location split {name} corpus manifest mismatch")
        sources = corpus_manifest.get("sources")
        if not isinstance(sources, list) or len(sources) != len(replay_ids):
            raise ValueError(f"location split {name} source accounting mismatch")
        if (
            sum(int(source.get("selected_samples", 0)) for source in sources)
            != int(row["samples"])
            or any(
                source.get("label_source")
                != REQUIRED_INVARIANTS["location_label_source"]
                for source in sources
            )
        ):
            raise ValueError(f"location split {name} source-label mismatch")

        metadata, arrays = load_corpus(output_path)
        samples = int(row["samples"])
        noop_action = arrays["action_masks"].shape[-1] - 2
        if (
            metadata.samples != samples
            or not np.all(arrays["episode_starts"])
            or np.unique(arrays["episode_ids"]).size != samples
            or not np.all(arrays["previous_actions"] == noop_action)
            or not np.all(arrays["previous_rewards"] == 0.0)
        ):
            raise ValueError(f"location split {name} violates one-step rows")

        assigned_replays.update(replay_set)
        assigned_samples += samples

    if assigned_replays.intersection(ignored_replays):
        raise ValueError("assigned location replay is also marked ignored")
    if int(payload.get("assigned_location_replays", -1)) != len(assigned_replays):
        raise ValueError("assigned location replay accounting mismatch")
    if int(payload.get("location_replays", -1)) != (
        len(assigned_replays) + len(ignored_replays)
    ):
        raise ValueError("total location replay accounting mismatch")
    if int(payload.get("location_samples", -1)) < assigned_samples:
        raise ValueError("total location sample accounting is impossible")

    insufficient: dict[str, dict[str, dict[str, float]]] = {}
    for name, minimums in SPLIT_MINIMUMS.items():
        failures: dict[str, dict[str, float]] = {}
        for key, required in minimums.items():
            actual = _metric(splits[name], key)
            if actual < required:
                failures[key] = {"required": required, "actual": actual}
        if failures:
            insufficient[name] = failures
    if insufficient:
        raise LocationDataInsufficient(insufficient)

    return {
        "status": "location_split_verified",
        "samples": int(payload["location_samples"]),
        "split_samples": {
            name: int(row["samples"]) for name, row in splits.items()
        },
        "split_diversity": {
            name: row["diversity"] for name, row in splits.items()
        },
        "target_games": target_games,
        "assigned_location_replays": len(assigned_replays),
        "ignored_reserved_replays": len(ignored_replays),
        **REQUIRED_INVARIANTS,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-games", required=True, type=int)
    args = parser.parse_args()
    try:
        report = verify_location_split(
            args.manifest,
            target_games=args.target_games,
        )
    except LocationDataInsufficient as exc:
        print(
            json.dumps(
                {
                    "status": "strict_location_data_insufficient",
                    "details": exc.details,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(3) from exc
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
