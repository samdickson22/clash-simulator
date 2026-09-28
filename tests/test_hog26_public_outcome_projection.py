import hashlib
import json

import numpy as np
import pytest

from scripts.hog26_public_outcome_projection import load_public_outcome_projection


def fixture(tmp_path, **extra):
    path = tmp_path / "corpus.npz"
    arrays = {
        "metadata_json": np.asarray(json.dumps({"complete_episodes_only": True, "row_count": 6, "episode_count": 2})),
        "global_features": np.ones((6, 18), dtype=np.float32),
        "next_global_features": np.ones((6, 18), dtype=np.float32),
        "final_outcomes": np.array([-1] * 3 + [1] * 3),
        "terminal_tower_margins": np.zeros(6, dtype=np.float32),
        "terminal_winners": np.array([1] * 3 + [0] * 3),
        "episode_starts": np.array([1, 0, 0, 1, 0, 0], dtype=bool),
        "dones": np.array([0, 0, 1, 0, 0, 1], dtype=bool),
        "episode_offsets": np.array([0, 3, 6]),
        "episode_stream_rows": np.array([0, 1]), "episode_ordinals": np.array([0, 0]),
        "initial_hidden": np.zeros((2, 1)), "initial_cell": np.zeros((2, 1)),
        "episode_final_outcomes": np.array([-1, 1]),
        "episode_terminal_tower_margins": np.zeros(2),
        "episode_opponent_indices": np.zeros(2, dtype=int),
        "episode_learner_players": np.array([0, 1]),
        "entity_features": np.ones((6, 100, 34), dtype=np.float32),
        **extra,
    }
    np.savez(path, **arrays)
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"schema": "clasher.hog26.outcome-corpus-audit.v1",
        "status": "passed", "checks": {"complete_stream_coverage": True},
        "corpora": [{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]}))
    return path, audit, arrays


def test_projection_preserves_selected_bytes_without_reading_entities(tmp_path, monkeypatch):
    path, audit, arrays = fixture(tmp_path)
    with np.load(path) as opened:
        archive_type = type(opened)
    original = archive_type.__getitem__
    def read(self, key):
        assert key != "entity_features", "projection expanded entity data"
        return original(self, key)
    monkeypatch.setattr(archive_type, "__getitem__", read)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    _, corpus = load_public_outcome_projection(path, audit_path=audit)
    for key, values in corpus.arrays.items():
        np.testing.assert_array_equal(values, arrays[key])
    assert "entity_features" not in corpus.arrays
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_projection_rejects_stale_full_audit(tmp_path):
    path, audit, _ = fixture(tmp_path)
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="stale"):
        load_public_outcome_projection(path, audit_path=audit)


def test_projection_cannot_hide_critic_fields(tmp_path):
    path, audit, _ = fixture(tmp_path, critic_entities=np.ones(3))
    with pytest.raises(ValueError, match="privileged critic"):
        load_public_outcome_projection(path, audit_path=audit)


def test_seeded_projection_retains_public_hands_for_opening_audit(tmp_path):
    metadata = {"complete_episodes_only": True, "row_count": 6, "episode_count": 2,
                "opening_schedule": "seeded-ordered-decks-v1"}
    hands = np.arange(30, dtype=np.int64).reshape(6, 5)
    path, audit, _ = fixture(tmp_path, metadata_json=np.asarray(json.dumps(metadata)),
                             hand_ids=hands)
    _, corpus = load_public_outcome_projection(path, audit_path=audit)
    np.testing.assert_array_equal(corpus.arrays["hand_ids"], hands)
    assert "entity_features" not in corpus.arrays
