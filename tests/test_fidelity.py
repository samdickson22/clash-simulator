import copy
import json

import pytest
from pydantic import ValidationError

from clasher.fidelity import (
    CandidateTrace,
    ReferenceCase,
    compare,
    compare_files,
    sha256,
)


@pytest.fixture
def records():
    case = {
        "schema_version": 1,
        "case_id": "hog-cannon",
        "ruleset_id": "test-build",
        "tick_ms": 50,
        "evidence": {
            "kind": "external_game_reference",
            "artifact": "capture.bin",
            "artifact_sha256": "0" * 64,
            "source": "test fixture, not actual game evidence",
            "game_build": "test-build",
            "annotation_method": "test observations",
            "timing_method": "test clock",
        },
        "observations": [
            {
                "earliest_tick": 1,
                "latest_tick": 2,
                "facts": {
                    "hog.x": {"kind": "interval", "lower": 3.0, "upper": 3.2},
                    "hog.target": {"kind": "exact", "value": "cannon"},
                },
            }
        ],
    }
    trace = {
        "schema_version": 1,
        "case_id": "hog-cannon",
        "ruleset_id": "test-build",
        "tick_ms": 50,
        "game_build": "test-build",
        "backend": "scalar_reference",
        "source_sha256": "1" * 64,
        "frames": [
            {"tick": 1, "facts": {"hog.x": 3.1, "hog.target": "tower"}},
            {"tick": 2, "facts": {"hog.x": 3.2, "hog.target": "cannon"}},
        ],
    }
    return case, trace


def result(records):
    case, trace = records
    return compare(
        ReferenceCase.model_validate(case), CandidateTrace.model_validate(trace)
    )


def test_joint_time_window_match_does_not_certify_fidelity(records):
    report = result(records)
    assert report["status"] == "comparison-passed"
    assert report["observations"][0]["matched_tick"] == 2
    assert not report["fidelity_acceptance"]
    assert not report["evidence_artifact_verified"]


def test_cannot_match_different_facts_at_different_ticks(records):
    records[1]["frames"][1]["facts"]["hog.x"] = 3.3
    report = result(records)
    assert report["status"] == "comparison-failed"
    assert report["first_divergence"] == 0


def test_missing_is_not_observed_null(records):
    records[0]["observations"][0]["facts"] = {
        "missing": {"kind": "exact", "value": None}
    }
    assert result(records)["status"] == "comparison-failed"


@pytest.mark.parametrize("value", [True, "3.1", None])
def test_non_numbers_do_not_satisfy_numeric_interval(records, value):
    for frame in records[1]["frames"]:
        frame["facts"].update({"hog.x": value, "hog.target": "cannon"})
    assert result(records)["status"] == "comparison-failed"


def test_bool_does_not_satisfy_exact_hit_count(records):
    records[0]["observations"][0]["facts"] = {"hits": {"kind": "exact", "value": 1}}
    for frame in records[1]["frames"]:
        frame["facts"]["hits"] = True
    assert result(records)["status"] == "comparison-failed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("case_id", "other"),
        ("tick_ms", 100),
        ("ruleset_id", "other"),
        ("game_build", "other"),
        ("game_build", None),
    ],
)
def test_incompatible_trace_rejected(records, field, value):
    records[1][field] = value
    with pytest.raises(ValueError):
        result(records)


def test_incomplete_time_window_is_not_a_pass(records):
    records[1]["frames"] = records[1]["frames"][1:]
    with pytest.raises(ValueError, match="full observation window"):
        result(records)


def test_joint_matching_preserves_chronology(records):
    records[0]["observations"].append(
        {
            "earliest_tick": 2,
            "latest_tick": 2,
            "facts": {"hog.target": {"kind": "exact", "value": "cannon"}},
        }
    )
    assert result(records)["status"] == "comparison-failed"


@pytest.mark.parametrize("mutation", ["gap", "duplicate", "nan", "empty", "extra"])
def test_invalid_trace_rejected(records, mutation):
    trace = records[1]
    if mutation == "gap":
        trace["frames"][1]["tick"] = 3
    elif mutation == "duplicate":
        trace["frames"][1]["tick"] = 1
    elif mutation == "nan":
        trace["frames"][0]["facts"]["hog.x"] = float("nan")
    elif mutation == "empty":
        trace["frames"] = []
    else:
        trace["secret"] = 42
    with pytest.raises(ValidationError):
        result(records)


def test_simulator_control_stays_a_control(records):
    records[0]["evidence"].update(kind="simulator_control", game_build=None)
    records[1]["game_build"] = None
    report = result(records)
    assert report["status"] == "comparison-passed"
    assert report["evidence_kind"] == "simulator_control"
    assert not report["fidelity_acceptance"]


def test_source_bytes_verified_and_mutation_rejected(records, tmp_path):
    case, trace = copy.deepcopy(records)
    artifact = tmp_path / "capture.bin"
    artifact.write_bytes(b"unit-test evidence")
    case["evidence"]["artifact_sha256"] = sha256(artifact)
    case_path, trace_path = tmp_path / "case.json", tmp_path / "trace.json"
    case_path.write_text(json.dumps(case))
    trace_path.write_text(json.dumps(trace))
    report = compare_files(case_path, trace_path)
    assert report["evidence_artifact_verified"]
    assert report["inputs"]["trace_sha256"] == sha256(trace_path)
    artifact.write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        compare_files(case_path, trace_path)


def test_artifact_cannot_escape_case_directory(records, tmp_path):
    case, trace = records
    case["evidence"]["artifact"] = "../outside"
    case_path, trace_path = tmp_path / "case.json", tmp_path / "trace.json"
    case_path.write_text(json.dumps(case))
    trace_path.write_text(json.dumps(trace))
    with pytest.raises(ValueError, match="inside the case directory"):
        compare_files(case_path, trace_path)
