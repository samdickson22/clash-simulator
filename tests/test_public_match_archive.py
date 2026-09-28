import numpy as np
import pytest
from pydantic import ValidationError

from clasher.battle import BattleState
from clasher.rl.public_match_archive import (
    MatchProvenance,
    PublicDecision,
    load_match_archive,
    save_match_archive,
    validate_split_assignments,
)
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder


def sample():
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Mirror"], max_entities=16
    )
    sequence = PublicPolicySequence.from_observations(
        builder, [builder.build_actor(BattleState(), 0)]
    )
    provenance = MatchProvenance(
        physical_match_id="test-match",
        duplicate_group_id="test-group",
        perspective=0,
        role="development",
        source_kind="synthetic_diagnostic",
        source_sha256="a" * 64,
        ruleset_sha256="b" * 64,
        producer_sha256="c" * 64,
        game_build="unit-test",
        observation_domain="simulator-exact",
        seed=7,
        opened_for_development=True,
    )
    return sequence, provenance


def test_archive_roundtrip_and_corruption_detection(tmp_path):
    sequence, provenance = sample()
    decisions = [
        PublicDecision(
            observation_tick=0,
            submission_tick=1,
            action=0,
            accepted=False,
            rejection_reason="not legal",
        )
    ]
    mask = np.zeros((1, 2306), dtype=bool)
    mask[0, 2304] = True
    path = tmp_path / "match"
    receipt = save_match_archive(path, sequence, provenance, decisions, mask)
    loaded = load_match_archive(path, token_names=sequence.token_names)
    assert loaded[0] == receipt and loaded[2] == decisions
    np.testing.assert_array_equal(loaded[3], mask)
    with pytest.raises(FileExistsError):
        save_match_archive(path, sequence, provenance, decisions, mask)
    (path / "decisions.json").write_text("[]")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_match_archive(path, token_names=sequence.token_names)


@pytest.mark.parametrize(
    "changes",
    [
        {"submission_tick": 0, "observation_tick": 1},
        {"accepted": False, "execution_tick": 3},
        {"accepted": True, "execution_tick": 0},
        {"accepted": False, "rejection_reason": None},
    ],
)
def test_action_evidence_rejects_contradictory_timing(changes):
    values = {
        "observation_tick": 0,
        "submission_tick": 1,
        "action": 0,
        "accepted": True,
    }
    values.update(changes)
    with pytest.raises(ValidationError):
        PublicDecision(**values)


def test_opened_data_and_related_perspectives_cannot_cross_roles():
    _, provenance = sample()
    values = provenance.model_dump()
    with pytest.raises(ValidationError):
        MatchProvenance(**(values | {"role": "acceptance"}))
    base = values | {
        "source_kind": "observed_game",
        "opened_for_development": False,
        "role": "training",
    }
    first = MatchProvenance(**base)
    second = MatchProvenance(**(base | {"perspective": 1, "role": "acceptance"}))
    with pytest.raises(ValueError, match="crosses data roles"):
        validate_split_assignments([first, second])
    duplicate = MatchProvenance(
        **(base | {"physical_match_id": "different-id", "role": "selection"})
    )
    with pytest.raises(ValueError, match="crosses data roles"):
        validate_split_assignments([first, duplicate])


def test_accepted_action_must_agree_with_public_mask(tmp_path):
    sequence, provenance = sample()
    decision = PublicDecision(
        observation_tick=0, submission_tick=0, action=0, accepted=True, execution_tick=0
    )
    mask = np.zeros((1, 2306), dtype=bool)
    mask[0, 2304] = True
    with pytest.raises(ValueError, match="contradicts its public action mask"):
        save_match_archive(tmp_path / "invalid", sequence, provenance, [decision], mask)
    assert not (tmp_path / "invalid").exists()


def test_archive_publication_failure_does_not_leave_partial_receipt(
    tmp_path, monkeypatch
):
    sequence, provenance = sample()
    decision = PublicDecision(
        observation_tick=0, submission_tick=0, action=2304, accepted=None
    )
    mask = np.zeros((1, 2306), dtype=bool)
    mask[0, 2304] = True

    def fail(*args, **kwargs):
        raise OSError("injected publication failure")

    monkeypatch.setattr("clasher.rl.public_match_archive.os.rename", fail)
    with pytest.raises(OSError):
        save_match_archive(tmp_path / "failed", sequence, provenance, [decision], mask)
    assert list(tmp_path.iterdir()) == []


def test_non_development_archive_requires_original_provenance_bytes(tmp_path):
    from clasher.rl.public_match_archive import digest

    sequence, provenance = sample()
    sources = [
        tmp_path / name for name in ("source.json", "ruleset.json", "producer.json")
    ]
    for index, path in enumerate(sources):
        path.write_text(str(index))
    values = provenance.model_dump() | {
        "role": "training",
        "source_kind": "observed_game",
        "opened_for_development": False,
        "source_sha256": digest(sources[0]),
        "ruleset_sha256": digest(sources[1]),
        "producer_sha256": digest(sources[2]),
    }
    provenance = MatchProvenance(**values)
    decision = PublicDecision(
        observation_tick=0, submission_tick=0, action=2304, accepted=None
    )
    masks = np.zeros((1, 2306), dtype=bool)
    masks[0, 2304] = True
    destination = tmp_path / "archive"
    save_match_archive(destination, sequence, provenance, [decision], masks)
    with pytest.raises(ValueError, match="verified provenance artifacts"):
        load_match_archive(destination, token_names=sequence.token_names)
    references = {
        "source_path": sources[0],
        "ruleset_path": sources[1],
        "producer_path": sources[2],
    }
    load_match_archive(destination, token_names=sequence.token_names, **references)
    sources[0].write_text("changed")
    with pytest.raises(ValueError, match="provenance artifact digest mismatch"):
        load_match_archive(destination, token_names=sequence.token_names, **references)


def test_partial_capture_cannot_claim_complete_game_without_terminal_evidence():
    _, provenance = sample()
    with pytest.raises(ValidationError, match="complete game requires"):
        MatchProvenance(**(provenance.model_dump() | {"coverage": "complete"}))
    with pytest.raises(ValidationError, match="partial capture"):
        MatchProvenance(**(provenance.model_dump() | {"terminal_result": "owner_win"}))


@pytest.mark.parametrize('terminal', [-1, 1])
def test_archive_rejects_commands_enabled_on_inactive_observation(tmp_path, terminal):
    sequence, provenance = sample()
    sequence.arrays['terminal_status'][0] = terminal
    masks = np.ones((1, 2306), dtype=bool)
    decisions = [PublicDecision(observation_tick=0, submission_tick=0, action=0, accepted=True, execution_tick=0)]
    with pytest.raises(ValueError, match='wait-only'):
        save_match_archive(tmp_path / 'invalid', sequence, provenance, decisions, masks)
    assert not (tmp_path / 'invalid').exists()
