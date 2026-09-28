from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from clasher.rl.oracle_corpus import file_sha256
from scripts.verify_tv_royale_human_meta_gate import verify_human_meta_gate


def _publish_gate(tmp_path: Path) -> Path:
    decks = []
    uniform = []
    frequency = []
    archetypes: Counter[str] = Counter()
    for index in range(8):
        deck_hash = f"hash-{index}"
        cards = [f"Card-{index}-{card}" for card in range(8)]
        archetype = f"archetype-{index % 6}"
        replays = [f"replay-{index}-0", f"replay-{index}-1"]
        samples = 70
        decks.append(
            {
                "deck_hash": deck_hash,
                "cards": cards,
                "archetype": archetype,
                "replays": replays,
                "arenas": ["arena_31"],
                "samples": samples,
            }
        )
        common = {
            "name": deck_hash,
            "cards": cards,
            "archetype": archetype,
            "source": "tv-royale-recurring-exact-deck-v1",
            "deck_hash": deck_hash,
            "observed_replays": 2,
            "observed_samples": samples,
            "arenas": ["arena_31"],
        }
        uniform.append({**common, "sampling_weight": 1.0})
        frequency.append({**common, "sampling_weight": 2.0})
        archetypes[archetype] += 1
    artifacts = {}
    for name, weighting, rows in (
        ("uniform", "uniform-per-deck", uniform),
        ("frequency_weighted", "observed-replay-frequency", frequency),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "metadata": {"weighting": weighting},
                    "decks": rows,
                }
            )
        )
        artifacts[name] = {"path": str(path), "sha256": file_sha256(path)}
    manifest = {
        "schema_version": 1,
        "source_games": 2_000,
        "min_replays": 2,
        "training_action_labels_used": False,
        "intended_use": "final-evaluation-only",
        "selected_decks": 8,
        "selected_replays": 16,
        "selected_samples": 560,
        "selected_archetypes": dict(sorted(archetypes.items())),
        "artifacts": artifacts,
        "decks": decks,
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path


def test_accepts_broad_exact_human_meta_gate(tmp_path: Path) -> None:
    report = verify_human_meta_gate(_publish_gate(tmp_path), target_games=2_000)

    assert report["status"] == "human_meta_gate_verified"
    assert report["selected_decks"] == 8
    assert report["selected_archetypes"] == 6


def test_rejects_narrow_human_meta_gate(tmp_path: Path) -> None:
    path = _publish_gate(tmp_path)
    payload = json.loads(path.read_text())
    payload["decks"] = payload["decks"][:7]
    payload["selected_decks"] = 7
    payload["selected_replays"] = 14
    payload["selected_samples"] = 490
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="too narrow"):
        verify_human_meta_gate(path, target_games=2_000)


def test_rejects_artifact_digest_or_weight_mismatch(tmp_path: Path) -> None:
    path = _publish_gate(tmp_path)
    payload = json.loads(path.read_text())
    uniform = Path(payload["artifacts"]["uniform"]["path"])
    artifact = json.loads(uniform.read_text())
    artifact["decks"][0]["sampling_weight"] = 2.0
    uniform.write_text(json.dumps(artifact))
    payload["artifacts"]["uniform"]["sha256"] = file_sha256(uniform)
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="sampling weight mismatch"):
        verify_human_meta_gate(path, target_games=2_000)
