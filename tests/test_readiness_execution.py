"""Execution planning/provenance tests; no native process is contacted."""

import dataclasses
import json

import numpy as np
import pytest
from pydantic import ValidationError
from test_training_readiness_v2 import candidates, sha

from clasher.rl.readiness_execution import (
    CAPTURE_FILES,
    CaptureBinding,
    ExecutionPlan,
    canonical_sha,
    condition_styles,
    decision_ticks,
    file_sha,
    jobs,
    packet_sha,
    require_development_execution,
)
from clasher.rl.training_readiness_v2 import CONDITIONS, ROLES, Family, Protocol


def plan(tmp_path, **updates):
    capture = tmp_path / "capture"
    capture.mkdir(exist_ok=True)
    for filename in CAPTURE_FILES:
        (capture / filename).write_text("{}")
    (capture / "plan.json").write_text(
        json.dumps({"role": "development", "config": {"rndSeed": 9}})
    )
    (capture / "result.json").write_text(
        json.dumps({"failure": None, "producer_sources_unchanged": True})
    )
    binding = CaptureBinding(
        family_id="root",
        capture_path=str(capture),
        root_tick=90,
        input_hashes={n: file_sha(capture / n) for n in CAPTURE_FILES},
        config_sha256=canonical_sha({"rndSeed": 9}),
        root_frame_sha256=sha("frame"),
    )
    family = Family(
        family_id="root",
        independence_id="episode",
        root_sha256=binding.root_sha256,
        public_packet_sha256=sha("packet"),
        root_owner=1,
        role="opened_development",
        candidates=candidates(),
        original_recommendation=2304,
    )
    config = {
        "protocol": Protocol(attempt_id="test", families=(family,)),
        "captures": (binding,),
        "catalog_path": str(capture / "gamedata.json"),
        "catalog_sha256": file_sha(capture / "gamedata.json"),
        "source_pins": {
            str(capture / "initial.json"): file_sha(capture / "initial.json")
        },
        "native_attestation_sha256": sha("attestation"),
        "purpose": "identical_repetition",
        "repetitions": 2,
    }
    config.update(updates)
    return ExecutionPlan(**config)


def test_full_design_and_same_execution_id_across_repetitions(tmp_path):
    p = plan(tmp_path)
    rows = jobs(p)
    assert len(rows) == 64
    assert len({r.execution_sha256 for r in rows}) == 32
    assert rows[0].execution_sha256 == rows[1].execution_sha256
    assert rows[0].repetition == 0 and rows[1].repetition == 1
    assert (
        rows[0].execution_sha256 != rows[2].execution_sha256
    )  # engines aren't repetitions
    assert {r.condition for r in rows} == set(CONDITIONS)
    assert {r.candidate_role for r in rows} == set(ROLES)


def test_bounded_noise_study_cannot_be_used_as_coverage(tmp_path):
    p = plan(
        tmp_path,
        selected_conditions=("balanced/pressure",),
        selected_roles=("immediate_play",),
    )
    assert len(jobs(p)) == 4
    with pytest.raises(ValidationError, match="all conditions"):
        ExecutionPlan.model_validate(
            {**p.model_dump(), "purpose": "development_coverage", "repetitions": 1}
        )


def test_readonly_capture_and_source_pins_fail_on_mutation(tmp_path):
    p = plan(tmp_path)
    p.verify_inputs()
    require_development_execution(p)
    (tmp_path / "capture" / "initial.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="source changed"):
        p.verify_inputs()


def test_no_acceptance_capture_relabeling(tmp_path):
    p = plan(tmp_path)
    (tmp_path / "capture" / "plan.json").write_text(json.dumps({"role": "acceptance"}))
    with pytest.raises(ValueError, match="acceptance captures"):
        require_development_execution(p)
    with pytest.raises(ValueError, match="ownership adapter"):
        require_development_execution(
            p.model_copy(update={"purpose": "fresh_acceptance"})
        )


def test_root_binding_and_repetition_validation(tmp_path):
    p = plan(tmp_path)
    bad = p.captures[0].model_copy(update={"root_tick": 95})
    with pytest.raises(ValidationError, match="root binding"):
        ExecutionPlan.model_validate({**p.model_dump(), "captures": (bad,)})
    with pytest.raises(ValidationError, match="at least two"):
        ExecutionPlan.model_validate({**p.model_dump(), "repetitions": 1})
    with pytest.raises(ValidationError, match="attestation"):
        ExecutionPlan.model_validate(
            {**p.model_dump(), "native_attestation_sha256": None}
        )


def test_five_tick_schedule_and_owner_relative_styles():
    assert list(decision_ticks(90))[:4] == [90, 95, 100, 105]
    assert list(decision_ticks(5999)) == [5999]
    assert condition_styles("defense/pressure", 0) == ("defense", "pressure")
    assert condition_styles("defense/pressure", 1) == ("pressure", "defense")
    with pytest.raises(ValueError):
        decision_ticks(6001)
    with pytest.raises(ValueError):
        condition_styles("geometry/geometry", 0)


def test_public_packet_digest_preserves_values_dtypes_and_shapes():
    @dataclasses.dataclass
    class Packet:
        values: np.ndarray

    a = Packet(np.array([1, 2], dtype=np.float32))
    assert packet_sha(a) == packet_sha(Packet(a.values.copy()))
    assert packet_sha(a) != packet_sha(Packet(a.values.astype(np.float64)))
    assert packet_sha(a) != packet_sha(Packet(a.values.reshape((2, 1))))


@pytest.mark.parametrize("v4", [False, True])
def test_scalar_executor_reacts_at_five_ticks_without_native_calls(
    tmp_path, monkeypatch, v4
):
    import gzip
    import importlib.util
    import sys
    import types
    from pathlib import Path

    from test_public_scripted_opponent import fixture, packet

    from clasher.rl.training_readiness_v2 import generate_candidates

    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    spec = importlib.util.spec_from_file_location(
        "readiness_runner_test", Path("scripts/run_readiness_v2.py")
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    p = plan(
        tmp_path,
        engines=("scalar",),
        selected_conditions=("balanced/pressure",),
        selected_roles=("immediate_play",),
    )
    battle, builder, bot = fixture()
    builder.public_hand_levels = v4
    from collections import deque

    for player in battle.players:
        player.hand = ["HogRider", "Cannon", "Fireball", "Skeletons"]
        player.cycle_queue = deque(["Knight", "Archers", "Zap", "Giant"])
    battle.tick = 90
    calls = []

    def step():
        calls.append(battle.tick)
        battle.tick += 1
        if battle.tick >= 96:
            battle.game_over = True
            battle.winner = 0

    monkeypatch.setattr(battle, "step", step)
    monkeypatch.setattr(runner, "scalar_initial", lambda *args: battle)
    monkeypatch.setattr(
        runner, "components", lambda *args: (builder.loader, builder, None, None)
    )

    def native_forbidden(*args):
        raise AssertionError("unexpected native I/O")

    monkeypatch.setattr(runner, "request", native_forbidden)
    frame = {"ordinary": {"tick": 90}, "rich": {}, "level_source": {}}
    monkeypatch.setattr(runner, "load_frame", lambda *args: frame)
    capture = tmp_path / "capture"
    (capture / "result.json").write_text(json.dumps({"commands": []}))
    binding = p.captures[0].model_copy(
        update={"root_frame_sha256": canonical_sha(frame)}
    )
    family = p.protocol.families[0].model_copy(
        update={
            "root_owner": 0,
            "candidates": generate_candidates(bot, packet(battle, builder)),
            "root_sha256": binding.root_sha256,
        }
    )
    p = p.model_copy(
        update={
            "captures": (binding,),
            "protocol": p.protocol.model_copy(update={"families": (family,)}),
        }
    )
    output = tmp_path / "job"
    output.mkdir()
    # Launch location must not matter (a Tier A run from /tmp once failed here).
    monkeypatch.chdir(tmp_path)
    result = runner.execute_job(
        p, jobs(p)[0], output, types.SimpleNamespace(port=26789, deadline=float("inf"))
    )
    assert result["terminal"] is True
    assert result["score"] == 1.0
    assert result["public_contract_valid"] is v4
    assert result["public_calibration_established"] is False
    assert result["level_coverage"]["own_hand_levels"] == {
        "observed": 14 if v4 else 0,
        "visible": 14,
    }
    assert result["legacy_public_projection_valid"] is True
    with gzip.open(output / "decisions.jsonl.gz", "rt") as stream:
        rows = [json.loads(line) for line in stream]
    assert [row["tick"] for row in rows] == [90, 95]
    assert rows[0]["actions"][0] == family.candidates[0].action_id
    assert calls == [90, 91, 92, 93, 94, 95]


def test_structural_v4_accepts_unknown_levels_without_claiming_measurement():
    from dataclasses import replace

    from test_public_scripted_opponent import fixture, packet

    from clasher.rl.native_public_observation import native_public_level_coverage
    from clasher.rl.readiness_execution import public_v4_structure_valid

    battle, builder, _bot = fixture()
    view = packet(battle, builder)
    assert not public_v4_structure_valid(view)
    actor = replace(
        view.observation,
        hand_levels=np.zeros(5, dtype=np.int64),
        hand_level_confidence=np.zeros(5, dtype=np.float32),
    )
    unknown = replace(view, observation=actor)
    assert public_v4_structure_valid(unknown)
    coverage = native_public_level_coverage(builder, unknown)
    assert coverage["own_hand_levels"] == {"observed": 0, "visible": 4}
    assert coverage["own_next_card_level"]["observed"] == 0
    dishonest = replace(
        unknown, observation=replace(actor, hand_levels=np.full(5, 11, dtype=np.int64))
    )
    with pytest.raises(ValueError, match="levels or confidence"):
        public_v4_structure_valid(dishonest)


@pytest.mark.parametrize("close_fails", [False, True])
def test_branch_result_waits_for_native_session_close_and_retains_failure(
    tmp_path, monkeypatch, close_fails
):
    import importlib.util
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path("scripts").resolve()))
    spec = importlib.util.spec_from_file_location(
        "readiness_session_close_test", Path("scripts/run_readiness_v2.py")
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)

    class Session:
        def __init__(self):
            self.state = "new"

        def __enter__(self):
            self.state = "open"
            return self

        def __exit__(self, *args):
            self.state = "failed" if close_fails else "verified"
            if close_fails:
                raise ValueError("changed identity at session close")

        @property
        def provenance(self):
            return {"status": self.state, "session_id": "synthetic-close-order-test"}

    def body(plan, job, output, args, stack, sessions, native_record=None):
        session = Session()
        sessions.append(session)
        stack.enter_context(session)
        assert session.provenance["status"] == "open"
        return {"terminal": True}

    monkeypatch.setattr(runner, "_execute_job_body", body)
    if close_fails:
        with pytest.raises(ValueError, match="changed identity"):
            runner.execute_job(None, None, tmp_path, None)
        assert (
            json.loads((tmp_path / "native-session.json").read_text())["status"]
            == "failed"
        )
    else:
        result = runner.execute_job(None, None, tmp_path, None)
        assert result["native_read_session"]["status"] == "verified"
        assert result["native_session_sha256"] == file_sha(
            tmp_path / "native-session.json"
        )
