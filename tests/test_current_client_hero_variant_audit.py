from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/current_client_hero_variant_hud_manifest_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_all_current_hero_variants_have_explicit_hud_template_entries() -> None:
    payload = _load()
    rows = payload["hero_template_queue"]
    assert payload["schema"] == "clasher.current_client.hero_variant_hud_audit.v1"
    assert payload["counts"] == {
        "hero_variants": 14,
        "runtime_visible_hud_variants": 14,
        "exact_local_hero_templates": 1,
        "missing_distinct_hero_templates": 13,
        "video_art_hypotheses": 1,
        "accepted_video_references_test_only": 1,
        "distinct_arena_bodies_proven": 0,
    }
    assert len(rows) == 14
    assert len({row["actor_token_id"] for row in rows}) == 14
    assert all(row["stable_key"].endswith("_hero") for row in rows)
    assert all(row["hud_runtime_visible"] for row in rows)
    assert all(row["stable_manifest_runtime_observable"] is False for row in rows)
    assert sum(row["exact_local_hero_template"] is not None for row in rows) == 1
    assert all(not row["root_family_may_auto_label"] for row in rows)


def test_hero_variants_do_not_create_unproven_arena_classes() -> None:
    payload = _load()
    for row in payload["hero_template_queue"]:
        arena = row["arena_disposition"]
        assert arena["same_payload_identity"] is True
        assert arena["distinct_arena_body_proven"] is False
        assert arena["detector_class_required"] is False


def test_barblog_hero_is_accepted_only_for_reviewed_test_sequence() -> None:
    payload = _load()
    rows = {row["stable_key"]: row for row in payload["hero_template_queue"]}
    row = rows["card_action:BarbLog_hero"]
    assert row["actor_token_id"] == 100
    assert row["mana_cost"] == 2
    assert row["review"]["status"] == (
        "accepted_exact_identity_for_reviewed_test_sequence"
    )
    assert row["review"]["generalize_to_other_video_crops"] is False
    assert row["exact_local_hero_template"]["training_eligible"] is False
    assert len(row["video_review_proposals"]) == 1
    proposal = row["video_review_proposals"][0]
    assert proposal["occurrences"] == 19
    assert proposal["split"] == "test"
    assert proposal["auto_label"] is False
    assert proposal["slot_kind"] == "normal_cycling_hand_card_variant"
    assert proposal["temporary_ability_control_slot"] is False
    assert payload["barblog_hero_visual_audit"]["base_barblog_occurrences"] == 15

    sequence = payload["barblog_hero_slot_sequence"]
    assert sequence["slot_kind_conclusion"] == "normal_cycling_hand_card_variant_proven"
    assert sequence["temporary_ability_control_slot_rejected"] is True
    assert sequence["exact_identity_status"] == (
        "accepted_exact_identity_for_reviewed_test_sequence"
    )
    assert sequence["auto_label"] is False
    assert [row["timestamp_ms"] for row in sequence["observations"]] == [
        25800,
        30800,
        31400,
    ]


def test_hero_audit_authority_and_visual_hashes_resolve() -> None:
    payload = _load()
    for row in payload["authorities"].values():
        path = ROOT / row["path"]
        assert path.is_file()
        assert _sha256(path) == row["sha256"]
    contact = Path(payload["contact_sheet"]["path"])
    assert _sha256(contact) == payload["contact_sheet"]["sha256"]
