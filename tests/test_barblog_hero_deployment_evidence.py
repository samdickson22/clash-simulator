from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/barblog_hero_deployment_evidence_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_exact_public_cycle_play_and_barrel_sequence() -> None:
    payload = _load()
    sequence = payload["observed_sequence"]
    assert [row["sample_index"] for row in sequence["normal_cycle"]] == [308, 314]
    transition = sequence["play_transition"]
    assert transition["before"]["sample_index"] == 371
    assert transition["after"]["sample_index"] == 372
    assert transition["before"]["public_displayed_elixir"] == 4
    assert transition["after"]["public_displayed_elixir"] == 2
    assert transition["displayed_elixir_drop"] == 2
    assert transition["hand_disappearance_proven"] is True
    barrels = sequence["arena_result"]["barrel_detector_proposals"]
    assert [row["sample_index"] for row in barrels] == [374, 375]
    assert all(
        row["detector_box_is_proposal_not_identity_authority"] for row in barrels
    )
    assert sequence["arena_result"]["visual_reviewed"] is True


def test_only_barblog_matches_official_cost_two_hero_mechanics() -> None:
    payload = _load()
    candidates = {
        row["stable_key"]: row for row in payload["official_cost_two_hero_candidates"]
    }
    assert set(candidates) == {
        "card_action:BarbLog_hero",
        "card_action:Goblins_hero",
        "card_action:IceGolemite_hero",
    }
    assert candidates["card_action:BarbLog_hero"]["projectile"] == ("BarbLogProjectile")
    assert candidates["card_action:BarbLog_hero"]["spell_as_deploy"] is True
    assert candidates["card_action:Goblins_hero"]["summon_character"] == "Goblin_Stab"
    assert candidates["card_action:Goblins_hero"]["summon_number"] == 4
    assert candidates["card_action:IceGolemite_hero"]["summon_character"] == (
        "IceGolemite"
    )


def test_identity_is_accepted_only_for_reviewed_test_sequence() -> None:
    decision = _load()["identity_decision"]
    assert decision["stable_key"] == "card_action:BarbLog_hero"
    assert decision["actor_token_id"] == 100
    assert decision["status"] == "accepted_exact_identity_for_reviewed_test_sequence"
    assert decision["root_family_only_auto_label"] is False
    assert decision["generalize_to_other_video_crops"] is False
    assert decision["arena_detector_class_required"] is False


def test_deployment_evidence_authority_hashes_resolve() -> None:
    payload = _load()
    for row in payload["authorities"].values():
        path = ROOT / row["path"]
        assert path.is_file()
        assert _sha256(path) == row["sha256"]
    contact = Path(payload["contact_sheet"]["path"])
    assert _sha256(contact) == payload["contact_sheet"]["sha256"]
