"""Paired reference responses must share coverage and avoid duplicate seed labels."""

import importlib
from pathlib import Path

import numpy as np
import pytest

from clasher.battle import BattleState
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.structured_obs import StructuredObservationBuilder


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("compare_reacting_public_branches")


def test_legacy_geometry_keeps_its_response_seed_behavior(runner):
    assert runner.response_styles({"response_seeds": [1, 2]}) == [
        "geometry",
        "geometry",
    ]


def test_deterministic_styles_cannot_masquerade_as_independent_seed_replicas(runner):
    with pytest.raises(ValueError, match="exactly one"):
        runner.response_styles(
            {
                "response_seeds": [1, 2],
                "response_styles_by_owner": ["balanced", "pressure"],
            }
        )
    assert runner.response_styles(
        {"response_seeds": [1], "response_styles_by_owner": ["balanced", "pressure"]}
    ) == ["balanced", "pressure"]


@pytest.mark.parametrize(
    "styles", [["balanced"], ["unknown", "balanced"], ["balanced", {}]]
)
def test_unknown_or_malformed_controllers_fail_before_collection(runner, styles):
    with pytest.raises(ValueError, match="two supported"):
        runner.response_styles(
            {"response_seeds": [1], "response_styles_by_owner": styles}
        )


def test_reference_projection_preserves_levels_but_removes_unobserved_effects_and_history():
    builder = StructuredObservationBuilder(
        card_vocab=["Knight", "Cannon"],
        canonical_lane_globals=True,
        public_entity_levels=True,
        public_history_slots=4,
        public_seen_card_slots=4,
        card_semantics_version=4,
    )
    battle = BattleState()
    battle.public_card_play_history = {0: [], 1: [(0, "Knight")]}
    obs = builder.build_actor(battle, 0)
    before = obs.entity_features.copy()
    packet = reference_public_observation(obs)
    assert np.array_equal(packet.observation.entity_features[:, :10], before[:, :10])
    assert not np.any(packet.observation.entity_features[:, 10:])
    assert not np.any(packet.entity_feature_confidence[:, 10:])
    assert np.array_equal(packet.observation.entity_levels, obs.entity_levels)
    assert np.array_equal(
        packet.observation.entity_level_confidence, obs.entity_level_confidence
    )
    assert np.any(obs.opponent_history_ids)
    assert not np.any(packet.observation.opponent_history_ids)
    assert not np.any(packet.opponent_history_confidence)
    assert set(np.flatnonzero(packet.global_feature_confidence)) == {
        5,
        8,
        9,
        10,
        11,
        12,
        13,
    }
    assert np.array_equal(obs.entity_features, before)
    packet.validate()


def test_changed_acceptance_candidates_fail_before_native_access(
    runner, monkeypatch, tmp_path
):
    import json
    import sys

    path = tmp_path / "branch.json"
    path.write_text(json.dumps({"role": "acceptance", "root_tick": 999}))
    monkeypatch.setattr(
        runner,
        "prepare_prospective_branch",
        lambda *args: {"role": "acceptance", "root_tick": 900},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("native engine must not be touched by invalid protocol")

    monkeypatch.setattr(runner, "request", forbidden)
    argv = ["runner", "--protocol", str(path), "--family-id", "f"]
    for option in (
        "capture",
        "gamedata",
        "catalog",
        "adb",
        "output",
        "collection-protocol",
        "registry",
    ):
        argv += ["--" + option, str(tmp_path / option)]
    argv += ["--catalog-sha256", "a" * 64]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(ValueError, match="frozen candidate"):
        runner.main()
    assert not (tmp_path / "output").exists()


def test_native_tiebreak_finalizes_without_overwriting_playable_health(runner, monkeypatch):
    playable = {"tick": 6001, "ended": False, "finalized": False, "hp": 899}
    calls = []

    def request(port, command):
        assert port == 26789
        calls.append(command)
        if command == "observe":
            elapsed = calls.count("step 1")
            return {"tick": 6001 + elapsed, "ended": elapsed == 128,
                    "finalized": elapsed == 128, "hp": max(0, 899 - elapsed * 8)}
        assert command == "step 1"

    monkeypatch.setattr(runner, "request", request)
    final = runner.finalize_native(playable)
    assert final["tick"] == 6129 and final["finalized"]
    assert playable["hp"] == 899 and playable["tick"] == 6001
    assert len(calls) == 256


def test_native_finalization_rejects_premature_stop_and_bounds_wait(runner, monkeypatch):
    calls = []
    stuck = {"tick": 6001, "ended": False, "finalized": False}

    def request(port, command):
        calls.append(command)
        return stuck

    monkeypatch.setattr(runner, "request", request)
    with pytest.raises(AssertionError, match="before the playable horizon"):
        runner.finalize_native(dict(stuck, tick=5999))
    assert not calls
    with pytest.raises(AssertionError, match="exceeded 400 ticks"):
        runner.finalize_native(stuck)
    assert calls.count("step 1") == 400
    calls.clear()
    already_done = dict(stuck, tick=2300, ended=True, finalized=True)
    assert runner.finalize_native(already_done) is already_done
    assert not calls
