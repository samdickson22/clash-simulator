from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from clasher.rl.deck_pool import load_deck_pool
from scripts.build_simple_supported_decks import (
    ArtifactDriftError,
    DeckManifestError,
    build_artifact,
    check_artifact,
)

EXPECTED_SUPPORTED_DECKS = [
    "Pekka Bandit EWiz Bridge Spam",
    "MK Miner ID Bats",
    "Giant",
    "WB Valk Log Bait 2.8",
    "Pekka Bandit EWiz Poison",
    "Hog 2.6 (Zap)",
    "Pekka Loon IWiz EDrag",
    "LavaLoon Miner",
    "Giant Double Prince",
]


def test_current_public_manifest_has_exact_supported_training_pool() -> None:
    source = json.loads(Path("decks.json").read_text(encoding="utf-8"))
    artifact = build_artifact("decks.json")

    assert artifact["contract"] == {
        "name": "clasher.simple_gym_supported_decks",
        "version": 1,
        "deck_size": 8,
        "canonical_lane_globals": True,
        "public_action_mask_contract_version": 2,
    }
    assert artifact["counts"] == {
        "candidate_decks": 33,
        "supported_decks": 9,
        "rejected_decks": 24,
        "public_cards": 66,
        "supported_public_cards": 60,
        "unsupported_public_cards": 6,
    }
    assert [deck["name"] for deck in artifact["decks"]] == (EXPECTED_SUPPORTED_DECKS)
    source_by_name = {deck["name"]: deck for deck in source["decks"]}
    assert artifact["decks"] == [
        source_by_name[name] for name in EXPECTED_SUPPORTED_DECKS
    ]
    assert len(artifact["source"]["sha256"]) == 64
    assert len(artifact["support_profile"]["sha256"]) == 64


def test_committed_artifact_is_exactly_current() -> None:
    expected = build_artifact("decks.json")
    check_artifact("training_decks/simple_gym_supported_v1.json", expected)
    assert load_deck_pool("training_decks/simple_gym_supported_v1.json") == [
        deck["cards"] for deck in expected["decks"]
    ]


def test_input_rejects_non_eight_card_or_duplicate_decks(tmp_path: Path) -> None:
    bad_size = tmp_path / "bad-size.json"
    bad_size.write_text(
        json.dumps({"decks": [{"name": "bad", "cards": ["Knight"] * 7}]}),
        encoding="utf-8",
    )
    with pytest.raises(DeckManifestError, match="exactly 8"):
        build_artifact(bad_size)

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps({"decks": [{"name": "bad", "cards": ["Knight"] * 8}]}),
        encoding="utf-8",
    )
    with pytest.raises(DeckManifestError, match="unique"):
        build_artifact(duplicate)


def test_check_rejects_contract_and_support_drift(tmp_path: Path) -> None:
    expected = build_artifact("decks.json")
    output = tmp_path / "supported.json"

    contract_drift = copy.deepcopy(expected)
    contract_drift["contract"]["public_action_mask_contract_version"] = 1
    output.write_text(json.dumps(contract_drift), encoding="utf-8")
    with pytest.raises(ArtifactDriftError, match="contract drift"):
        check_artifact(output, expected)

    profile_drift = copy.deepcopy(expected)
    profile_drift["support_profile"]["sha256"] = "0" * 64
    output.write_text(json.dumps(profile_drift), encoding="utf-8")
    with pytest.raises(ArtifactDriftError, match="artifact is stale"):
        check_artifact(output, expected)
