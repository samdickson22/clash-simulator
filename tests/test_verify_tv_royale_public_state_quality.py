from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.oracle_corpus import file_sha256
from scripts.verify_tv_royale_public_state_quality import (
    verify_public_state_quality,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_game(
    run_root: Path,
    *,
    arena: str,
    replay: str,
    include_hp: bool,
) -> dict[str, object]:
    game_root = run_root / "games" / arena / replay
    game_root.mkdir(parents=True)
    corpus = game_root / "corpus.npz"
    corpus.write_bytes(b"fixture")
    sidecar = game_root / "public_state_v2.npz"
    samples = 2
    entities = 2
    entity_features = np.zeros((samples, entities, 32), dtype=np.float16)
    entity_mask = np.ones((samples, entities), dtype=np.bool_)
    identity_confidence = np.ones((samples, entities), dtype=np.float32)
    feature_confidence = np.zeros((samples, entities, 32), dtype=np.float32)
    feature_confidence[..., 0:2] = 1.0
    if include_hp:
        feature_confidence[..., 9] = 0.7
    feature_confidence[..., 27:29] = 0.6
    global_confidence = np.zeros((samples, 18), dtype=np.float32)
    global_confidence[:, 8:14] = 0.8
    np.savez_compressed(
        sidecar,
        source_frames=np.asarray([10, 20], dtype=np.int64),
        entity_features=entity_features,
        entity_mask=entity_mask,
        entity_id_confidence=identity_confidence,
        entity_feature_confidence=feature_confidence,
        global_feature_confidence=global_confidence,
        schema_version=np.asarray(2),
    )
    visible = samples * entities
    hp = visible if include_hp else 0
    sidecar_sha = file_sha256(sidecar)
    _write_json(
        game_root / "manifest.json",
        {
            "arena": arena,
            "replay": replay,
            "public_state_v2": {
                "path": str(sidecar),
                "sha256": sidecar_sha,
                "statistics": {
                    "schema": "confidence-aware-public-observation-v2",
                    "schema_version": 2,
                    "samples": samples,
                    "visible_entities": visible,
                    "entities_with_measured_hp": hp,
                    "entity_hp_coverage": hp / visible,
                    "mean_observed_hp_confidence": 0.7 if include_hp else 0.0,
                    "entities_with_motion_direction": visible,
                    "motion_direction_coverage": 1.0,
                    "tower_hp_measurements": samples * 6,
                    "legacy_corpus_mutated": False,
                },
            },
        },
    )
    return {
        "status": "complete",
        "arena": arena,
        "replay": replay,
        "corpus": str(corpus),
        "public_state_v2": str(sidecar),
        "public_state_v2_sha256": sidecar_sha,
    }


def _fixture(tmp_path: Path, *, second_game_hp: bool = True) -> Path:
    run_root = tmp_path / "run"
    records = [
        _write_game(
            run_root,
            arena="arena_12",
            replay="replay-12",
            include_hp=True,
        ),
        _write_game(
            run_root,
            arena="arena_13",
            replay="replay-13",
            include_hp=second_game_hp,
        ),
    ]
    run_manifest = run_root / "run_manifest.json"
    _write_json(run_manifest, {"completed_games": 2, "records": records})
    return run_manifest


def test_public_state_quality_accepts_complete_confident_measurements(
    tmp_path: Path,
) -> None:
    run_manifest = _fixture(tmp_path)

    result = verify_public_state_quality(
        run_manifest_path=run_manifest,
        target_games=2,
        expected_arenas=2,
    )

    assert result["passes"]
    assert all(result["gates"].values())
    assert result["aggregate"]["position_coverage"] == 1.0
    assert result["aggregate"]["entity_hp_coverage"] == 1.0
    assert result["aggregate"]["tower_hp_measurements_per_sample"] == 6.0


def test_public_state_quality_rejects_one_arena_without_hp(tmp_path: Path) -> None:
    run_manifest = _fixture(tmp_path, second_game_hp=False)

    result = verify_public_state_quality(
        run_manifest_path=run_manifest,
        target_games=2,
        expected_arenas=2,
    )

    assert not result["passes"]
    assert result["gates"]["entity_hp_coverage"]
    assert not result["gates"]["entity_hp_coverage_each_arena"]


def test_public_state_quality_rejects_edited_manifest_statistics(
    tmp_path: Path,
) -> None:
    run_manifest = _fixture(tmp_path)
    run = json.loads(run_manifest.read_text(encoding="utf-8"))
    game_manifest = Path(run["records"][0]["corpus"]).parent / "manifest.json"
    game = json.loads(game_manifest.read_text(encoding="utf-8"))
    game["public_state_v2"]["statistics"]["visible_entities"] = 99
    _write_json(game_manifest, game)

    with pytest.raises(ValueError, match="statistic changed"):
        verify_public_state_quality(
            run_manifest_path=run_manifest,
            target_games=2,
            expected_arenas=2,
        )
