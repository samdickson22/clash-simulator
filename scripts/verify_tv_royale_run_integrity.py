# mypy: disable-error-code="import-untyped"

"""Verify every published artifact in a completed TV Royale extraction run."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.imitation import load_corpus
from clasher.rl.oracle_corpus import file_sha256
from clasher.rl.public_observation import PUBLIC_OBSERVATION_SCHEMA_VERSION
from clasher.rl.replay_split import complete_visible_hand_mask

PUBLIC_STATE_ARRAYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "entity_id_confidence",
    "entity_feature_confidence",
    "hand_ids",
    "hand_id_confidence",
    "global_features",
    "global_feature_confidence",
    "opponent_history_ids",
    "opponent_history_ages",
    "opponent_history_confidence",
    "opponent_seen_card_ids",
    "opponent_seen_card_confidence",
    "source_indices",
    "source_frames",
    "expert_actions",
    "schema_version",
)
PUBLIC_CONFIDENCE_PAIRS = (
    ("entity_ids", "entity_id_confidence"),
    ("entity_features", "entity_feature_confidence"),
    ("hand_ids", "hand_id_confidence"),
    ("global_features", "global_feature_confidence"),
    ("opponent_history_ids", "opponent_history_confidence"),
    ("opponent_history_ages", "opponent_history_confidence"),
    ("opponent_seen_card_ids", "opponent_seen_card_confidence"),
)
COMBINED_ALIGNMENT_ARRAYS = (
    "entity_ids",
    "entity_features",
    "entity_mask",
    "hand_ids",
    "global_features",
    "action_masks",
    "expert_actions",
)


def _require_under(path: Path, root: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"{label} escapes extraction root: {resolved}")
    return resolved


def _verify_corpus(
    path: Path,
    *,
    expected_sha256: str,
    expected_samples: int | None = None,
) -> tuple[int, tuple[str, ...], str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    digest = file_sha256(path)
    if digest != expected_sha256:
        raise ValueError(f"corpus digest mismatch: {path}")
    metadata, arrays = load_corpus(path)
    samples = int(metadata.samples)
    if samples <= 0 or arrays["expert_actions"].shape[0] != samples:
        raise ValueError(f"empty or structurally invalid corpus: {path}")
    if expected_samples is not None and samples != expected_samples:
        raise ValueError(
            f"corpus sample mismatch for {path}: {samples} != {expected_samples}"
        )
    return samples, tuple(metadata.token_names), metadata.label_source


def _verify_public_state_sidecar(
    path: Path,
    *,
    expected_sha256: str,
    expected_samples: int,
    corpus_path: Path,
    require_corpus_provenance: bool = True,
) -> dict[str, int | float]:
    """Re-verify a confidence-aware sidecar independently of extraction."""

    if not path.is_file():
        raise FileNotFoundError(path)
    if file_sha256(path) != expected_sha256:
        raise ValueError(f"public-state digest mismatch: {path}")
    with (
        np.load(path, allow_pickle=False) as public,
        np.load(corpus_path, allow_pickle=False) as corpus,
    ):
        missing = sorted(set(PUBLIC_STATE_ARRAYS) - set(public.files))
        if missing:
            raise ValueError(f"public-state sidecar lacks arrays: {missing}")
        if (
            public["schema_version"].shape != ()
            or int(public["schema_version"].item())
            != PUBLIC_OBSERVATION_SCHEMA_VERSION
        ):
            raise ValueError(f"unsupported public-state schema: {path}")
        samples = int(public["expert_actions"].shape[0])
        if samples != expected_samples:
            raise ValueError(
                f"public-state sample mismatch for {path}: "
                f"{samples} != {expected_samples}"
            )
        for name in PUBLIC_STATE_ARRAYS:
            if name == "schema_version":
                continue
            value = public[name]
            if value.ndim == 0 or value.shape[0] != samples:
                raise ValueError(
                    f"public-state {name} rows do not match samples: {path}"
                )
            if np.issubdtype(value.dtype, np.number) and not np.all(
                np.isfinite(value)
            ):
                raise ValueError(f"public-state {name} contains non-finite values")
        for name in ("source_indices", "source_frames", "expert_actions"):
            # Replay-disjoint split corpora retain replay/frame provenance but
            # intentionally omit the extractor-local source row index. The
            # public sidecar may preserve it as additional provenance.
            if name != "expert_actions" and not require_corpus_provenance:
                continue
            if name == "source_indices" and name not in corpus:
                continue
            if name not in corpus or not np.array_equal(public[name], corpus[name]):
                raise ValueError(f"public-state sidecar is not aligned on {name}")
        if require_corpus_provenance and "source_replays" in public and (
            "source_replays" not in corpus
            or not np.array_equal(public["source_replays"], corpus["source_replays"])
        ):
            raise ValueError("public-state sidecar is not aligned on source_replays")

        entity_ids = public["entity_ids"]
        entity_features = public["entity_features"]
        entity_mask = public["entity_mask"].astype(np.bool_, copy=False)
        if entity_mask.shape != entity_ids.shape:
            raise ValueError("public-state entity mask shape mismatch")
        if entity_features.shape[:-1] != entity_ids.shape:
            raise ValueError("public-state entity feature shape mismatch")
        for value_name, confidence_name in PUBLIC_CONFIDENCE_PAIRS:
            value = public[value_name]
            confidence = public[confidence_name]
            if confidence.shape != value.shape:
                raise ValueError(
                    f"public-state confidence shape mismatch: {confidence_name}"
                )
            if not np.all(np.isfinite(confidence)) or np.any(confidence < 0.0) or np.any(
                confidence > 1.0
            ):
                raise ValueError(
                    f"public-state confidence outside [0, 1]: {confidence_name}"
                )
            if np.any(value[confidence <= 0.0] != 0):
                raise ValueError(
                    f"public-state fabricates {value_name} where confidence is zero"
                )
        padded = ~entity_mask
        if (
            np.any(entity_ids[padded] != 0)
            or np.any(entity_features[padded] != 0.0)
            or np.any(public["entity_id_confidence"][padded] != 0.0)
            or np.any(public["entity_feature_confidence"][padded] != 0.0)
        ):
            raise ValueError("public-state padded entities are nonzero")
        if entity_features.shape[-1] <= 28:
            raise ValueError("public-state entity feature schema is too narrow")
        visible = int(np.count_nonzero(entity_mask))
        hp = int(
            np.count_nonzero(
                (public["entity_feature_confidence"][..., 9] > 0.0) & entity_mask
            )
        )
        motion = int(
            np.count_nonzero(
                (public["entity_feature_confidence"][..., 27] > 0.0) & entity_mask
            )
        )
    return {
        "samples": samples,
        "visible_entities": visible,
        "entities_with_hp": hp,
        "entities_with_motion": motion,
        "entity_hp_coverage": hp / max(1, visible),
        "motion_coverage": motion / max(1, visible),
    }


def _verify_combined_public_alignment(
    *,
    public_path: Path,
    combined_corpus_path: Path,
    game_corpus_paths: list[Path],
) -> None:
    """Reconstruct the exact combined-row provenance independently.

    The generic imitation combiner intentionally omits extractor-only replay and
    frame arrays. Rebuild the same content-addressed row selection from the
    immutable per-game corpora instead of weakening the combined-sidecar gate.
    """

    with np.load(combined_corpus_path, allow_pickle=False) as combined:
        combined_identity = {
            name: combined[name].copy() for name in COMBINED_ALIGNMENT_ARRAYS
        }
        combined_episode_ids = combined["episode_ids"].copy()
    canonical_dtypes = {
        name: value.dtype for name, value in combined_identity.items()
    }

    def fingerprint(arrays: dict[str, np.ndarray], row: int) -> bytes:
        digest = hashlib.sha256()
        for name in COMBINED_ALIGNMENT_ARRAYS:
            value = np.ascontiguousarray(
                arrays[name][row], dtype=canonical_dtypes[name]
            )
            digest.update(name.encode("ascii"))
            digest.update(value.dtype.str.encode("ascii"))
            digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
            digest.update(value.tobytes())
        return digest.digest()

    replay_chunks: list[np.ndarray] = []
    index_chunks: list[np.ndarray] = []
    frame_chunks: list[np.ndarray] = []
    action_chunks: list[np.ndarray] = []
    row_by_fingerprint: dict[bytes, int] = {}
    source_row_offset = 0
    for corpus_path in game_corpus_paths:
        with np.load(corpus_path, allow_pickle=False) as corpus:
            source_rows = int(corpus["expert_actions"].shape[0])
            identity = {
                name: corpus[name].copy() for name in COMBINED_ALIGNMENT_ARRAYS
            }
            replay_chunks.append(corpus["source_replays"].copy())
            index_chunks.append(corpus["source_indices"].copy())
            frame_chunks.append(corpus["source_frames"].copy())
            action_chunks.append(corpus["expert_actions"].copy())
            for row in range(source_rows):
                row_by_fingerprint.setdefault(
                    fingerprint(identity, row), source_row_offset + row
                )
            source_row_offset += source_rows

    try:
        selection = np.asarray(
            [
                row_by_fingerprint[fingerprint(combined_identity, row)]
                for row in range(combined_episode_ids.shape[0])
            ],
            dtype=np.int64,
        )
    except KeyError as error:
        raise ValueError(
            "combined corpus row has no exact public-state source fingerprint"
        ) from error
    if np.unique(selection).size != selection.size:
        raise ValueError("combined public-state alignment selected a source row twice")

    expected = {
        "source_replays": np.concatenate(replay_chunks)[selection],
        "source_indices": np.concatenate(index_chunks)[selection],
        "source_frames": np.concatenate(frame_chunks)[selection],
        "expert_actions": np.concatenate(action_chunks)[selection],
        "episode_ids": combined_episode_ids,
    }
    with np.load(public_path, allow_pickle=False) as public:
        for name, value in expected.items():
            if name not in public or not np.array_equal(public[name], value):
                raise ValueError(
                    f"combined public-state sidecar is not aligned on {name}"
                )


def _verify_exact_unique_members(
    actual: list[str],
    expected: list[str],
    *,
    label: str,
) -> None:
    """Require a manifest membership list to be duplicate-free and exact."""
    if len(actual) != len(set(actual)):
        raise ValueError(f"{label} contains duplicate members")
    actual_set = set(actual)
    expected_set = set(expected)
    if actual_set != expected_set:
        missing = sorted(expected_set - actual_set)
        unexpected = sorted(actual_set - expected_set)
        raise ValueError(
            f"{label} membership mismatch: "
            f"missing={missing[:5]}, unexpected={unexpected[:5]}"
        )


def verify_run_integrity(
    run_manifest_path: Path,
    *,
    scratch_root: Path,
    target_games: int,
    artifact_root: Path | None = None,
    required_location_label_source: str | None = None,
    require_public_state_v2: bool = False,
) -> dict[str, Any]:
    run_manifest_path = run_manifest_path.resolve()
    output_root = (
        run_manifest_path.parent
        if artifact_root is None
        else artifact_root.resolve()
    )
    run = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if run.get("schema") != "tv-royale-raw-cascade-run-v1":
        raise ValueError("unexpected TV Royale run schema")
    if int(run.get("target_games", -1)) != target_games:
        raise ValueError("run target does not match requested integrity target")
    records = run.get("records")
    if not isinstance(records, list):
        raise TypeError("run manifest records must be a list")
    complete = [row for row in records if row.get("status") == "complete"]
    failed = [row for row in records if row.get("status") == "failed"]
    if len(complete) != target_games:
        raise ValueError(f"run has {len(complete)}/{target_games} completed games")
    if int(run.get("completed_games", -1)) != len(complete):
        raise ValueError("completed-game counter disagrees with records")
    if int(run.get("failed_games", -1)) != len(failed):
        raise ValueError("failed-game counter disagrees with records")
    if int(run.get("attempted_games", -1)) != len(records):
        raise ValueError("attempt counter disagrees with records")
    replay_ids = [str(row["replay"]) for row in complete]
    if len(set(replay_ids)) != len(replay_ids):
        raise ValueError("completed run contains duplicate replay IDs")

    token_names: tuple[str, ...] | None = None
    primary_samples = 0
    location_samples = 0
    location_replays = 0
    location_samples_by_source: Counter[str] = Counter()
    location_replays_by_source: Counter[str] = Counter()
    eligible_location_samples_by_source: Counter[str] = Counter()
    eligible_location_replays_by_source: Counter[str] = Counter()
    eligible_location_replay_ids_by_source: defaultdict[str, list[str]] = defaultdict(
        list
    )
    game_corpus_paths: list[str] = []
    audit_images = 0
    public_state_games = 0
    public_state_samples = 0
    public_visible_entities = 0
    public_entities_with_hp = 0
    public_entities_with_motion = 0
    for row in complete:
        if row.get("raw_deleted") is not True:
            raise ValueError(f"completed replay did not record raw deletion: {row}")
        replay = str(row["replay"])
        arena = str(row["arena"])
        corpus_path = _require_under(
            Path(str(row["corpus"])), output_root, label="game corpus"
        )
        game_corpus_paths.append(str(corpus_path))
        game_root = corpus_path.parent
        game_manifest_path = game_root / "manifest.json"
        game = json.loads(game_manifest_path.read_text(encoding="utf-8"))
        if game.get("replay") != replay or game.get("arena") != arena:
            raise ValueError(f"game manifest identity mismatch: {game_manifest_path}")
        if game.get("source_sha256") != row.get("sha256"):
            raise ValueError(f"source digest mismatch: {game_manifest_path}")
        corpus_manifest = game.get("corpus") or {}
        expected_digest = str(row.get("corpus_sha256", ""))
        if corpus_manifest.get("sha256") != expected_digest:
            raise ValueError(f"game/run corpus digest disagreement: {replay}")
        samples, corpus_tokens, _ = _verify_corpus(
            corpus_path,
            expected_sha256=expected_digest,
            expected_samples=int(row["samples"]),
        )
        if token_names is None:
            token_names = corpus_tokens
        elif corpus_tokens != token_names:
            raise ValueError(f"token vocabulary drift in replay {replay}")
        if int(row.get("accepted_type_events", 0)) + int(
            row.get("accepted_noops", 0)
        ) != samples:
            raise ValueError(f"accepted-label count mismatch in replay {replay}")
        primary_samples += samples

        public_manifest = game.get("public_state_v2")
        public_record_path = row.get("public_state_v2")
        if public_manifest is None or public_record_path is None:
            if require_public_state_v2:
                raise ValueError(f"completed replay lacks public-state v2: {replay}")
        else:
            public_path = _require_under(
                Path(str(public_record_path)), output_root, label="public-state sidecar"
            )
            manifest_path = _require_under(
                Path(str(public_manifest["path"])),
                output_root,
                label="manifest public-state sidecar",
            )
            if public_path != manifest_path:
                raise ValueError(f"game/run public-state path disagreement: {replay}")
            expected_public_digest = str(row.get("public_state_v2_sha256", ""))
            if str(public_manifest.get("sha256", "")) != expected_public_digest:
                raise ValueError(f"game/run public-state digest disagreement: {replay}")
            public_stats = _verify_public_state_sidecar(
                public_path,
                expected_sha256=expected_public_digest,
                expected_samples=samples,
                corpus_path=corpus_path,
            )
            public_state_games += 1
            public_state_samples += int(public_stats["samples"])
            public_visible_entities += int(public_stats["visible_entities"])
            public_entities_with_hp += int(public_stats["entities_with_hp"])
            public_entities_with_motion += int(
                public_stats["entities_with_motion"]
            )

        for output in game.get("audit_outputs", []):
            audit_path = _require_under(
                Path(str(output)), output_root, label="audit image"
            )
            if not audit_path.is_file():
                raise FileNotFoundError(audit_path)
            audit_images += 1

        location_manifest = game.get("location_corpus")
        if location_manifest:
            location_path = _require_under(
                Path(str(location_manifest["path"])),
                output_root,
                label="location corpus",
            )
            expected_location_samples = int(
                (location_manifest.get("statistics") or {}).get("samples", -1)
            )
            samples, location_tokens, location_label_source = _verify_corpus(
                location_path,
                expected_sha256=str(location_manifest["sha256"]),
                expected_samples=expected_location_samples,
            )
            if location_tokens != token_names:
                raise ValueError(f"location vocabulary drift in replay {replay}")
            with np.load(location_path, allow_pickle=False) as arrays:
                sources = {str(value) for value in arrays["source_replays"].tolist()}
                arenas = {str(value) for value in arrays["source_arenas"].tolist()}
                eligible_samples = int(
                    np.count_nonzero(complete_visible_hand_mask(arrays["hand_ids"]))
                )
            if sources != {replay} or arenas != {arena}:
                raise ValueError(f"location provenance mismatch in replay {replay}")
            location_samples += samples
            location_replays += 1
            location_samples_by_source[location_label_source] += samples
            location_replays_by_source[location_label_source] += 1
            if eligible_samples > 0:
                eligible_location_samples_by_source[
                    location_label_source
                ] += eligible_samples
                eligible_location_replays_by_source[location_label_source] += 1
                eligible_location_replay_ids_by_source[
                    location_label_source
                ].append(replay)

    stem = f"tv_royale_raw_cascade_{target_games}"
    combined_path = output_root / f"{stem}.npz"
    combined_manifest_path = output_root / f"{stem}_manifest.json"
    combined_manifest = json.loads(
        combined_manifest_path.read_text(encoding="utf-8")
    )
    combined_sources = combined_manifest.get("sources", [])
    if not isinstance(combined_sources, list):
        raise TypeError("combined corpus sources must be a list")
    combined_source_paths = [
        str(
            _require_under(
                Path(str(source["path"])), output_root, label="combined source"
            )
        )
        for source in combined_sources
    ]
    _verify_exact_unique_members(
        combined_source_paths,
        game_corpus_paths,
        label="combined corpus sources",
    )
    combined_samples, combined_tokens, _ = _verify_corpus(
        combined_path,
        expected_sha256=str(combined_manifest["output_sha256"]),
        expected_samples=int(combined_manifest["samples"]),
    )
    if combined_tokens != token_names:
        raise ValueError("combined corpus vocabulary differs from game corpora")

    combined_public_samples = 0
    if 0 < public_state_games < len(complete):
        raise ValueError("only some completed games contain public-state v2")
    if public_state_games:
        combined_public_path = output_root / f"{stem}_public_state_v2.npz"
        combined_public_manifest_path = (
            output_root / f"{stem}_public_state_v2_manifest.json"
        )
        combined_public_manifest = json.loads(
            combined_public_manifest_path.read_text(encoding="utf-8")
        )
        if (
            combined_public_manifest.get("schema")
            != "combined-confidence-aware-public-observation-v2"
            or int(combined_public_manifest.get("schema_version", -1))
            != PUBLIC_OBSERVATION_SCHEMA_VERSION
        ):
            raise ValueError("combined public-state manifest schema mismatch")
        if int(combined_public_manifest.get("source_games", -1)) != len(complete):
            raise ValueError("combined public-state source-game count mismatch")
        if (
            str(Path(str(combined_public_manifest.get("output", ""))).resolve())
            != str(combined_public_path.resolve())
        ):
            raise ValueError("combined public-state output path mismatch")
        if (
            str(Path(str(combined_public_manifest.get("combined_corpus", ""))).resolve())
            != str(combined_path.resolve())
            or combined_public_manifest.get("combined_corpus_sha256")
            != file_sha256(combined_path)
        ):
            raise ValueError("combined public-state corpus provenance mismatch")
        combined_public_stats = _verify_public_state_sidecar(
            combined_public_path,
            expected_sha256=str(combined_public_manifest["output_sha256"]),
            expected_samples=combined_samples,
            corpus_path=combined_path,
            require_corpus_provenance=False,
        )
        _verify_combined_public_alignment(
            public_path=combined_public_path,
            combined_corpus_path=combined_path,
            game_corpus_paths=[Path(path) for path in game_corpus_paths],
        )
        combined_public_samples = int(combined_public_stats["samples"])
        for name in (
            "samples",
            "visible_entities",
            "entities_with_hp",
            "entities_with_motion",
        ):
            if int(combined_public_manifest.get(name, -1)) != int(
                combined_public_stats[name]
            ):
                raise ValueError(f"combined public-state {name} mismatch")
        for name in ("entity_hp_coverage", "motion_coverage"):
            if not np.isclose(
                float(combined_public_manifest.get(name, -1.0)),
                float(combined_public_stats[name]),
                rtol=0.0,
                atol=1e-12,
            ):
                raise ValueError(f"combined public-state {name} mismatch")
    elif require_public_state_v2:
        raise ValueError("completed run contains no public-state v2 sidecars")

    combined_location_path = output_root / f"{stem}_locations.npz"
    combined_location_manifest_path = output_root / f"{stem}_locations_manifest.json"
    combined_location_samples = 0
    if combined_location_manifest_path.is_file():
        location_manifest = json.loads(
            combined_location_manifest_path.read_text(encoding="utf-8")
        )
        combined_location_samples, combined_location_tokens, _ = _verify_corpus(
            combined_location_path,
            expected_sha256=str(location_manifest["output_sha256"]),
            expected_samples=int(location_manifest["samples"]),
        )
        if combined_location_tokens != token_names:
            raise ValueError("combined location vocabulary differs from game corpora")
        if location_manifest.get("independent_rows") is not True:
            raise ValueError("combined locations are not independent one-step rows")
        if required_location_label_source is not None:
            if (
                location_manifest.get("required_label_source")
                != required_location_label_source
            ):
                raise ValueError("combined locations use the wrong label contract")
            strict_samples = eligible_location_samples_by_source[
                required_location_label_source
            ]
            strict_replays = eligible_location_replays_by_source[
                required_location_label_source
            ]
            if strict_samples <= 0 or strict_replays <= 0:
                raise ValueError("run contains no strict location supervision")
            if int(location_manifest.get("location_replays", -1)) != strict_replays:
                raise ValueError("combined location replay count is not strict-only")
            combined_location_replay_ids = location_manifest.get("replay_ids")
            if not isinstance(combined_location_replay_ids, list):
                raise TypeError("combined location replay_ids must be a list")
            _verify_exact_unique_members(
                [str(value) for value in combined_location_replay_ids],
                eligible_location_replay_ids_by_source[
                    required_location_label_source
                ],
                label="combined location replay IDs",
            )
            if not 0 < combined_location_samples <= strict_samples:
                raise ValueError("combined location sample count is not strict-only")
    elif required_location_label_source is not None:
        raise FileNotFoundError(combined_location_manifest_path)

    scratch_files = sorted(
        str(path)
        for pattern in ("*.parquet", "*.parquet.part")
        for path in scratch_root.resolve().rglob(pattern)
    )
    if scratch_files:
        raise ValueError(f"raw replay files remain after publication: {scratch_files}")
    return {
        "schema_version": 1,
        "run_manifest": str(run_manifest_path),
        "artifact_root": str(output_root),
        "target_games": target_games,
        "completed_games": len(complete),
        "failed_games": len(failed),
        "unique_replays": len(set(replay_ids)),
        "primary_samples_before_deduplication": primary_samples,
        "combined_samples": combined_samples,
        "public_state_games": public_state_games,
        "public_state_samples_before_deduplication": public_state_samples,
        "public_state_visible_entities_before_deduplication": public_visible_entities,
        "public_state_entities_with_hp_before_deduplication": public_entities_with_hp,
        "public_state_entities_with_motion_before_deduplication": public_entities_with_motion,
        "public_state_hp_coverage_before_deduplication": public_entities_with_hp
        / max(1, public_visible_entities),
        "public_state_motion_coverage_before_deduplication": public_entities_with_motion
        / max(1, public_visible_entities),
        "combined_public_state_samples": combined_public_samples,
        "game_location_replays": location_replays,
        "game_location_samples_before_filtering": location_samples,
        "game_location_replays_by_label_source": dict(
            sorted(location_replays_by_source.items())
        ),
        "game_location_samples_by_label_source": dict(
            sorted(location_samples_by_source.items())
        ),
        "eligible_game_location_replays_by_label_source": dict(
            sorted(eligible_location_replays_by_source.items())
        ),
        "eligible_game_location_samples_by_label_source": dict(
            sorted(eligible_location_samples_by_source.items())
        ),
        "required_location_label_source": required_location_label_source,
        "combined_location_samples": combined_location_samples,
        "audit_images": audit_images,
        "raw_files_remaining": 0,
        "passes": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True, type=Path)
    parser.add_argument("--scratch-root", required=True, type=Path)
    parser.add_argument("--target-games", required=True, type=int)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--required-location-label-source")
    parser.add_argument("--require-public-state-v2", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = verify_run_integrity(
        args.run_manifest,
        scratch_root=args.scratch_root,
        target_games=args.target_games,
        artifact_root=args.artifact_root,
        required_location_label_source=args.required_location_label_source,
        require_public_state_v2=args.require_public_state_v2,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "tv_royale_run_integrity_verified", **report}))


if __name__ == "__main__":
    main()
