from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collect_hog26_direct_simple_behavior import file_sha256
from scripts.run_hog26_procedural_outcome_shard import load_protocol
from scripts.train_hog26_procedural_outcome_candidate import (
    require_current_audit,
    training_command,
    validate_training_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports" / "hog26_procedural_outcome_protocol_seed1278401.json"


def _values(command: list[str], flag: str) -> list[str]:
    return [command[index + 1] for index, value in enumerate(command) if value == flag]


def test_primary_training_command_is_exact_and_has_no_holdout() -> None:
    protocol = load_protocol(PROTOCOL, ROOT)
    command = training_command(protocol, root=ROOT, device="cuda")
    assert _values(command, "--device") == ["cuda"]
    assert _values(command, "--seed") == ["1278801"]
    assert _values(command, "--feature-set") == ["structured-summary"]
    assert _values(command, "--margin-progress-power") == ["6.0"]
    assert _values(command, "--minimum-natural-phase-auc") == ["0.55"]
    assert _values(command, "--minimum-controlled-draw-auc") == ["0.8"]
    assert _values(command, "--maximum-natural-draw-probability") == ["0.1"]
    assert len(_values(command, "--train-corpus")) == 7
    assert len(_values(command, "--validation-corpus")) == 2
    assert len(_values(command, "--calibration-corpus")) == 1
    assert "--holdout-corpus" not in command
    assert "--phase-balanced-outcome-training" in command
    assert "--phase-balanced-margin-training" in command
    assert "--require-disjoint-natural-decks" in command


def test_training_rejects_original_protocol_without_reassessment() -> None:
    protocol = load_protocol(PROTOCOL, ROOT)
    with pytest.raises(ValueError, match="reassessment missing"):
        validate_training_inputs(protocol, root=ROOT)


def test_dynamic_candidate_command_carries_loss_and_phase_weighting():
    protocol = load_protocol(PROTOCOL, ROOT)
    protocol["primary_candidate"].update(
        feature_set="public-global-dynamics", margin_dynamics="overtime-damage-race-v1",
        margin_loss="absolute", aggregate_phase_margin_training=True,
        margin_progress_power=0.0,
    )
    command = training_command(protocol, root=ROOT, device="cpu")
    assert _values(command, "--feature-set") == ["public-global-dynamics"]
    assert _values(command, "--margin-loss") == ["absolute"]
    assert _values(command, "--margin-progress-power") == ["0.0"]
    assert "--aggregate-phase-margin-training" in command
    assert "--holdout-corpus" not in command


def test_training_rejects_unresolved_margin_design() -> None:
    protocol = load_protocol(
        ROOT / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json",
        ROOT,
    )
    with pytest.raises(ValueError, match="not cleared"):
        validate_training_inputs(protocol, root=ROOT)


def test_audit_must_pass_and_match_current_corpus_bytes(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.npz"
    corpus.write_bytes(b"original corpus")
    report_path = tmp_path / "audit.json"
    report = {
        "schema": "clasher.hog26.outcome-corpus-audit.v1",
        "status": "passed",
        "checks": {"complete_stream_coverage": True},
        "corpora": [{"path": str(corpus), "sha256": file_sha256(corpus)}],
    }
    report_path.write_text(json.dumps(report))
    require_current_audit(corpus, report_path)
    corpus.write_bytes(b"changed after audit")
    with pytest.raises(ValueError, match="stale"):
        require_current_audit(corpus, report_path)
    corpus.write_bytes(b"original corpus")
    report["checks"]["complete_stream_coverage"] = False
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="did not pass"):
        require_current_audit(corpus, report_path)
    report_path.unlink()
    with pytest.raises(FileNotFoundError):
        require_current_audit(corpus, report_path)


def test_reassessed_wrapper_passes_required_slice_protocol() -> None:
    path = ROOT / "reports/hog26_procedural_outcome_protocol_reassessed_20260908.json"
    protocol = load_protocol(path, ROOT)
    with pytest.raises(ValueError, match="protocol path"):
        training_command(protocol, root=ROOT, device="cpu")
    command = training_command(protocol, root=ROOT, device="cpu", protocol_path=path)
    assert _values(command, "--generalization-protocol") == [str(path)]
