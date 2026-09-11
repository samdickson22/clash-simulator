"""Synthetic corruption checks for atomic complete-game publication."""

from types import SimpleNamespace

import numpy as np
import pytest

from scripts.hog26_scalar_corpus import (
    ScalarGameCorpusWriter,
    validate_scalar_corpus,
)


def fixture():
    actor = SimpleNamespace(
        entity_ids=np.array([2, 0]),
        entity_features=np.zeros((2, 32), np.float32),
        entity_mask=np.array([True, False]),
        hand_ids=np.array([2, 3, 4, 5, 6]),
        global_features=np.zeros(18, np.float32),
        opponent_history_ids=np.zeros(0, int),
        opponent_history_ages=np.zeros(0, np.float32),
        opponent_seen_card_ids=np.zeros(0, int),
    )
    inputs = SimpleNamespace(
        entity_id_confidence=np.array([[[1.0, 0.0]], [[1.0, 0.0]]]),
        entity_feature_confidence=np.ones((2, 1, 2, 32)),
        hand_id_confidence=np.ones((2, 1, 5)),
        global_feature_confidence=np.ones((2, 1, 18)),
        action_mask=np.ones((2, 1, 2306), bool),
        previous_actions=np.zeros((2, 1), int),
        episode_starts=np.ones((2, 1), bool),
    )
    return actor, inputs


def write(path, **overrides):
    actor, inputs = fixture()
    writer = ScalarGameCorpusWriter(path, {"source": "frozen", "scenario": "a"})
    writer.append(actor, inputs, learner_seat=0, tick=0, action=1, success=True)
    inputs.previous_actions[:] = 1
    inputs.episode_starts[:] = False
    writer.append(actor, inputs, learner_seat=0, tick=8, action=2, success=True)
    kwargs = {
        "terminal_tick": 13,
        "winner": 0,
        "learner_seat": 0,
        "terminal_tower_hp": [[100, 100, 400], [0, 100, 400]],
        "initial_tower_hp": [[100, 100, 400], [100, 100, 400]],
        "actual_terminal": True,
    }
    kwargs.update(overrides)
    return writer.finish(**kwargs)


def test_roundtrip_preserves_original_unweighted_margin(tmp_path):
    path = tmp_path / "game.npz"
    result = write(path)
    assert result["rows"] == 2
    assert result["terminal_tower_margin"] == pytest.approx(1 / 3)
    assert result["outcome_wdl"] == [1, 0, 0]
    with np.load(path, allow_pickle=False) as data:
        assert data["episode_start"].tolist() == [True, False]
        assert data["opponent_history_ids"].shape == (2, 0)
    with pytest.raises(ValueError, match="external authority"):
        validate_scalar_corpus(path, expected_metadata={"source": "other"})


def test_exclusive_publication(tmp_path):
    path = tmp_path / "game.npz"
    write(path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write(path)
    assert before == path.read_bytes()
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "overrides",
    [
        {"actual_terminal": False},
        {"terminal_tick": 8},
        {"terminal_tick": 17},
        {"learner_seat": 1},
        {"winner": 3},
        {"initial_tower_hp": [[0, 100, 400]] * 2},
    ],
)
def test_invalid_terminal_never_published(tmp_path, overrides):
    path = tmp_path / "game.npz"
    with pytest.raises(ValueError):
        write(path, **overrides)
    assert not path.exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("tick", [0, 16]),
        ("action", [1, 99999]),
        ("success", [1, 0]),
        ("previous_action", [0, 0]),
        ("outcome_wdl", [0, 1, 0]),
        ("terminal_tower_margin", 1 / 6),
        ("entity_features", np.full((2, 2, 32), np.nan)),
        ("private_future_target", [1]),
    ],
)
def test_independent_validator_rejects_corruption(tmp_path, key, value):
    path = tmp_path / "game.npz"
    write(path)
    with np.load(path, allow_pickle=False) as data:
        payload = dict(data)
    payload[key] = np.array(value)
    np.savez_compressed(path, **payload)
    with pytest.raises(ValueError):
        validate_scalar_corpus(path)


def test_boundary_rejects_critic_and_missing_decisions(tmp_path):
    actor, inputs = fixture()
    writer = ScalarGameCorpusWriter(tmp_path / "never.npz", {"source": "a"})
    with pytest.raises(ValueError, match="noncontiguous"):
        writer.append(actor, inputs, learner_seat=0, tick=8, action=0, success=True)
    inputs.critic_global_features = np.zeros(2)
    with pytest.raises(ValueError, match="critic"):
        writer.append(actor, inputs, learner_seat=0, tick=0, action=0, success=True)


def test_copies_input_and_metadata_before_mutation(tmp_path):
    actor, inputs = fixture()
    metadata = {"scenario": {"id": "original"}, "source": "frozen"}
    path = tmp_path / "copy.npz"
    writer = ScalarGameCorpusWriter(path, metadata)
    writer.append(actor, inputs, learner_seat=1, tick=0, action=1, success=True)
    actor.entity_ids[0] = 999
    inputs.action_mask[:] = False
    metadata["scenario"]["id"] = "changed"
    writer.finish(
        terminal_tick=1,
        winner=None,
        learner_seat=1,
        terminal_tower_hp=[[100, 100, 400]] * 2,
        initial_tower_hp=[[100, 100, 400]] * 2,
        actual_terminal=True,
    )
    with np.load(path, allow_pickle=False) as data:
        assert data["entity_ids"][0, 0] == 2
        assert data["action_mask"].all()
        assert data["outcome_wdl"].tolist() == [0, 1, 0]
    assert validate_scalar_corpus(path)["metadata"]["scenario"]["id"] == "original"


def test_illegal_public_action_not_published(tmp_path):
    actor, inputs = fixture()
    inputs.action_mask[:] = False
    path = tmp_path / "illegal.npz"
    writer = ScalarGameCorpusWriter(path, {"source": "frozen"})
    writer.append(actor, inputs, learner_seat=0, tick=0, action=1, success=True)
    with pytest.raises(ValueError, match="public mask"):
        writer.finish(
            terminal_tick=1,
            winner=1,
            learner_seat=0,
            terminal_tower_hp=[[100, 100, 400]] * 2,
            initial_tower_hp=[[100, 100, 400]] * 2,
            actual_terminal=True,
        )
    assert not path.exists()
    assert not list(tmp_path.iterdir())


def test_failed_card_and_noop_results_retained(tmp_path):
    actor, inputs = fixture()
    path = tmp_path / "retained.npz"
    writer = ScalarGameCorpusWriter(path, {"source": "frozen"})
    writer.append(actor, inputs, learner_seat=0, tick=0, action=2304, success=False)
    inputs.previous_actions[:] = 2304
    inputs.episode_starts[:] = False
    writer.append(actor, inputs, learner_seat=0, tick=8, action=1, success=False)
    result = writer.finish(
        terminal_tick=12,
        winner=1,
        learner_seat=0,
        terminal_tower_hp=[[100, 100, 400]] * 2,
        initial_tower_hp=[[100, 100, 400]] * 2,
        actual_terminal=True,
    )
    assert result["rows"] == 2
    assert result["rejected_card_actions"] == 1
    assert result["noop_false_results"] == 1
    with np.load(path, allow_pickle=False) as data:
        assert data["action"].tolist() == [2304, 1]
        assert data["success"].tolist() == [False, False]


def test_outcome_keeps_extra_identities_with_separate_policy_confidence(tmp_path):
    actor, inputs = fixture()
    actor.entity_ids[:] = [4, 496]
    actor.entity_mask[:] = True
    path = tmp_path / "extra.npz"
    writer = ScalarGameCorpusWriter(
        path, {"source": "frozen", "extra_tokens": [496, 497]}
    )
    writer.append(actor, inputs, learner_seat=0, tick=0, action=2304, success=False)
    writer.finish(
        terminal_tick=1,
        winner=None,
        learner_seat=0,
        terminal_tower_hp=[[100, 100, 400]] * 2,
        initial_tower_hp=[[100, 100, 400]] * 2,
        actual_terminal=True,
    )
    with np.load(path, allow_pickle=False) as data:
        assert data["entity_ids"].tolist() == [[4, 496]]
        assert data["entity_id_confidence"].tolist() == [[1.0, 1.0]]
        assert data["policy_entity_id_confidence"].tolist() == [[1.0, 0.0]]


def vocabulary_game(path):
    actor, inputs = fixture()
    actor.entity_ids[:] = [4, 6]
    actor.entity_mask[:] = True
    actor.entity_features[1, 7] = 1
    metadata = {
        "schema": "clasher.scalar-pilot-game-metadata.v1",
        "policy_token_names": ["pad", "unknown", "two", "three", "four", "five"],
        "outcome_token_names": [
            "pad",
            "unknown",
            "two",
            "three",
            "four",
            "five",
            "public_effect:chain_bolt",
        ],
    }
    writer = ScalarGameCorpusWriter(path, metadata)
    writer.append(actor, inputs, learner_seat=0, tick=0, action=2304, success=False)
    writer.finish(
        terminal_tick=1,
        winner=None,
        learner_seat=0,
        terminal_tower_hp=[[100, 100, 400]] * 2,
        initial_tower_hp=[[100, 100, 400]] * 2,
        actual_terminal=True,
    )


def test_valid_pilot_vocabulary(tmp_path):
    path = tmp_path / "vocab.npz"
    vocabulary_game(path)
    assert validate_scalar_corpus(path)["rows"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "prefix",
        "out_of_range",
        "unknown",
        "padding_visible",
        "base_conf",
        "extra_conf",
        "combat_extra",
        "untyped_extra",
    ],
)
def test_vocabulary_contradictions_rejected(tmp_path, mutation):
    import json

    path = tmp_path / "vocab.npz"
    vocabulary_game(path)
    with np.load(path, allow_pickle=False) as archive:
        data = dict(archive)
    metadata = json.loads(data["metadata_json"].item())
    if mutation == "missing":
        del metadata["policy_token_names"]
    elif mutation == "duplicate":
        metadata["outcome_token_names"][-1] = "four"
    elif mutation == "prefix":
        metadata["policy_token_names"][2] = "changed"
    elif mutation == "out_of_range":
        data["entity_ids"][0, 1] = 7
    elif mutation == "unknown":
        data["entity_ids"][0, 0] = 1
    elif mutation == "padding_visible":
        data["entity_ids"][0, 0] = 0
    elif mutation == "base_conf":
        data["policy_entity_id_confidence"][0, 0] = 0
    elif mutation == "extra_conf":
        data["policy_entity_id_confidence"][0, 1] = 1
    elif mutation == "combat_extra":
        data["entity_features"][0, 1, 4] = 1
    elif mutation == "untyped_extra":
        data["entity_features"][0, 1, 7] = 0
    data["metadata_json"] = np.array(json.dumps(metadata))
    np.savez_compressed(path, **data)
    with pytest.raises(ValueError):
        validate_scalar_corpus(path)
