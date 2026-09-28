"""Mirror replay-disjoint TV Royale action splits into public-state sidecars."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from clasher.paths import resolve_path
from clasher.rl.oracle_corpus import atomic_write_json, file_sha256
from scripts.run_tv_royale_raw_cascade import _combine_public_state_v2
from scripts.verify_tv_royale_run_integrity import _verify_public_state_sidecar


def _records_by_replay(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for record in run.get("records", []):
        if record.get("status") != "complete":
            continue
        replay = str(record["replay"])
        if replay in result:
            raise ValueError(f"duplicate completed replay in run: {replay}")
        result[replay] = record
    return result


def _select_split_records(
    replay_ids: list[str],
    *,
    records_by_replay: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not replay_ids or len(replay_ids) != len(set(replay_ids)):
        raise ValueError("split replay IDs must be nonempty and unique")
    missing = sorted(set(replay_ids) - set(records_by_replay))
    if missing:
        raise ValueError(f"split references unavailable replays: {missing[:5]}")
    selected = [records_by_replay[replay] for replay in replay_ids]
    lacking = [str(record["replay"]) for record in selected if not record.get("public_state_v2")]
    if lacking:
        raise ValueError(f"split replays lack public-state v2: {lacking[:5]}")
    return selected


def split_public_sidecars(
    *,
    run_manifest_path: Path,
    split_manifest_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    run_manifest_path = run_manifest_path.resolve()
    split_manifest_path = split_manifest_path.resolve()
    run = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    split = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    if int(split.get("schema_version", 0)) < 2:
        raise ValueError("public sidecars require replay split schema v2")
    if Path(str(split.get("source_run_manifest", ""))).resolve() != run_manifest_path:
        raise ValueError("split was not derived from the requested run manifest")
    split_rows = split.get("splits")
    if not isinstance(split_rows, dict) or not split_rows:
        raise ValueError("split manifest contains no splits")
    records = _records_by_replay(run)
    all_replays: set[str] = set()
    for name, row in split_rows.items():
        replay_ids = [str(value) for value in row.get("replay_ids", [])]
        overlap = all_replays.intersection(replay_ids)
        if overlap:
            raise ValueError(f"replay overlap across public splits: {sorted(overlap)[:5]}")
        all_replays.update(replay_ids)
        if int(row.get("replays", -1)) != len(replay_ids):
            raise ValueError(f"split replay count mismatch: {name}")

    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_manifest_path = output_dir / "public_state_v2_split_manifest.json"
    expected_outputs = [
        path
        for name in split_rows
        for path in (
            output_dir / f"{name}_public_state_v2.npz",
            output_dir / f"{name}_public_state_v2_manifest.json",
        )
    ]
    existing = [
        str(path)
        for path in (*expected_outputs, aggregate_manifest_path)
        if path.exists()
    ]
    if existing:
        raise FileExistsError("refusing to overwrite public split outputs: " + ", ".join(existing))

    published: dict[str, Any] = {}
    for name, row in split_rows.items():
        replay_ids = [str(value) for value in row["replay_ids"]]
        selected = _select_split_records(
            replay_ids,
            records_by_replay=records,
        )
        for record in selected:
            corpus_path = Path(str(record["corpus"])).resolve()
            public_path = Path(str(record["public_state_v2"])).resolve()
            with np.load(corpus_path, allow_pickle=False) as corpus:
                samples = int(corpus["expert_actions"].shape[0])
            _verify_public_state_sidecar(
                public_path,
                expected_sha256=str(record["public_state_v2_sha256"]),
                expected_samples=samples,
                corpus_path=corpus_path,
            )
        combined_corpus = Path(str(row["output"])).resolve()
        if file_sha256(combined_corpus) != str(row["output_sha256"]):
            raise ValueError(f"split corpus digest mismatch: {name}")
        output_path = output_dir / f"{name}_public_state_v2.npz"
        manifest_path = output_dir / f"{name}_public_state_v2_manifest.json"
        manifest = _combine_public_state_v2(
            records=selected,
            combined_corpus_path=combined_corpus,
            output_path=output_path,
            manifest_path=manifest_path,
        )
        if int(manifest["samples"]) != int(row["samples"]):
            raise ValueError(f"public-state split sample mismatch: {name}")
        verified = _verify_public_state_sidecar(
            output_path,
            expected_sha256=str(manifest["output_sha256"]),
            expected_samples=int(row["samples"]),
            corpus_path=combined_corpus,
        )
        published[name] = {
            "replays": len(replay_ids),
            "replay_ids": replay_ids,
            "corpus": str(combined_corpus),
            "corpus_sha256": str(row["output_sha256"]),
            "public_state_v2": str(output_path.resolve()),
            "public_state_v2_sha256": str(manifest["output_sha256"]),
            **verified,
        }
    payload = {
        "schema_version": 1,
        "schema": "replay-disjoint-confidence-aware-public-state-splits-v1",
        "run_manifest": str(run_manifest_path),
        "run_manifest_sha256_at_publication": file_sha256(run_manifest_path),
        "split_manifest": str(split_manifest_path),
        "split_manifest_sha256": file_sha256(split_manifest_path),
        "splits": published,
        "invariants": {
            "replay_overlap": 0,
            "public_action_alignment": "exact",
            "missing_values": "zero-with-zero-confidence",
        },
    }
    atomic_write_json(aggregate_manifest_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--split-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = split_public_sidecars(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        split_manifest_path=resolve_path(args.split_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
