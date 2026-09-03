from __future__ import annotations

from pathlib import Path

from scripts.audit_hog26_procedural_outcome_shard import shard_expectations
from scripts.run_hog26_procedural_outcome_shard import load_protocol

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "reports" / "hog26_procedural_outcome_protocol_seed1278401.json"


def test_training_shard_audit_expectations_are_protocol_exact() -> None:
    protocol = load_protocol(PROTOCOL, ROOT)
    row = protocol["training"][0]
    expected = shard_expectations(protocol, row, root=ROOT)
    assert len(expected["expected_decks"]) == 32
    assert expected["expected_opponents"] == {"balanced", "random"}
    assert expected["expected_split"] == "train"
    assert expected["expected_supported_decks_sha256"] == (
        protocol["procedural_decks"]["sha256"]
    )
