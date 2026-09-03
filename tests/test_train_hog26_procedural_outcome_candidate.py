from __future__ import annotations

from pathlib import Path

from scripts.run_hog26_procedural_outcome_shard import load_protocol
from scripts.train_hog26_procedural_outcome_candidate import training_command

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
