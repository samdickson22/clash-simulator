from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from pathlib import Path
from typing import Any

from clasher.paths import resolve_path
from clasher.rl.imitation_mix import combine_imitation_corpora
from clasher.rl.oracle_corpus import atomic_write_json, file_sha256
from scripts.run_tv_royale_raw_cascade import _combine_public_state_v2


def snapshot_public_corpus(
    *,
    run_manifest_path: Path,
    output_dir: Path,
    games: int,
    seed: int,
) -> dict[str, Any]:
    if games <= 0:
        raise ValueError("games must be positive")
    run_payload = json.loads(run_manifest_path.read_text())
    completed = [
        record
        for record in run_payload.get("records", [])
        if record.get("status") == "complete"
    ]
    if len(completed) < games:
        raise ValueError(
            f"requested {games} games but only {len(completed)} are complete"
        )
    selected = completed[:games]
    missing_public = [
        str(record.get("replay"))
        for record in selected
        if not record.get("public_state_v2")
    ]
    if missing_public:
        raise ValueError(
            "selected games lack public-state sidecars: " + ", ".join(missing_public)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = output_dir / f"tv_royale_public_snapshot_{games}.npz"
    corpus_manifest_path = (
        output_dir / f"tv_royale_public_snapshot_{games}_corpus_manifest.json"
    )
    public_path = output_dir / f"tv_royale_public_snapshot_{games}_state_v2.npz"
    public_manifest_path = (
        output_dir / f"tv_royale_public_snapshot_{games}_state_v2_manifest.json"
    )
    snapshot_manifest_path = output_dir / "snapshot_manifest.json"
    owned_outputs = (
        corpus_path,
        corpus_manifest_path,
        public_path,
        public_manifest_path,
        snapshot_manifest_path,
    )
    existing = [str(path) for path in owned_outputs if path.exists()]
    if existing:
        raise FileExistsError("refusing to overwrite snapshot outputs: " + ", ".join(existing))

    combine_imitation_corpora(
        sources=[Path(record["corpus"]) for record in selected],
        output_path=corpus_path,
        manifest_path=corpus_manifest_path,
        seed=seed,
        deduplicate=True,
    )
    public_manifest = _combine_public_state_v2(
        records=selected,
        combined_corpus_path=corpus_path,
        output_path=public_path,
        manifest_path=public_manifest_path,
    )
    manifest = {
        "schema_version": 1,
        "schema": "frozen-tv-royale-public-corpus-snapshot-v1",
        "source_run_manifest": str(run_manifest_path),
        "source_target_games": int(run_payload.get("target_games", 0)),
        "selected_games": games,
        "seed": seed,
        "replays": [str(record["replay"]) for record in selected],
        "corpus": str(corpus_path),
        "corpus_sha256": file_sha256(corpus_path),
        "public_state_v2": str(public_path),
        "public_state_v2_sha256": file_sha256(public_path),
        "samples": int(public_manifest["samples"]),
        "entity_hp_coverage": float(public_manifest["entity_hp_coverage"]),
        "motion_coverage": float(public_manifest["motion_coverage"]),
        "selected_source_records": [
            {
                "arena": str(record["arena"]),
                "replay": str(record["replay"]),
                "corpus_sha256": str(record["corpus_sha256"]),
                "public_state_v2_sha256": str(record["public_state_v2_sha256"]),
            }
            for record in selected
        ],
    }
    atomic_write_json(snapshot_manifest_path, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze a validated prefix of a live TV Royale public corpus"
    )
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--games", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    manifest = snapshot_public_corpus(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
        games=args.games,
        seed=args.seed,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
