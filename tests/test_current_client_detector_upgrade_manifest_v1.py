from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/current_client_detector_upgrade_manifest_v1.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_detector_upgrade_token_map_is_complete_and_typed() -> None:
    payload = _load()
    rows = payload["token_to_katacr"]
    assert payload["schema"] == "clasher.current_client.detector_upgrade_manifest.v1"
    assert [row["actor_token_id"] for row in rows] == list(range(494))
    assert len({row["stable_key"] for row in rows}) == 494
    assert payload["counts"]["arena_detector_tokens"] == 315
    assert payload["counts"]["relationship_counts"] == {
        "exact_or_explicit_visual_class": 84,
        "missing_visual_class": 88,
        "not_arena_detector_target": 177,
        "reserved_not_visual": 2,
        "root_family_only_do_not_autolabel": 143,
    }

    by_key = {row["stable_key"]: row for row in rows}
    assert by_key["troop_body:RoyalGiant"]["exact_visual_labels"] == ["royal-giant"]
    assert by_key["troop_body:RoyalGiant_EV1"]["katacr_relationship"] == (
        "root_family_only_do_not_autolabel"
    )
    assert by_key["troop_body:Goblinstein"]["katacr_relationship"] == (
        "missing_visual_class"
    )
    assert by_key["troop_body:BossBandit"]["katacr_relationship"] == (
        "missing_visual_class"
    )


def test_family_only_rows_cannot_become_automatic_annotations() -> None:
    payload = _load()
    for row in payload["token_to_katacr"]:
        if row["katacr_relationship"] == "root_family_only_do_not_autolabel":
            assert not row["detector_annotation_eligible"]
            assert row["family_only_labels"]
            assert not row["exact_visual_labels"]
    for asset in payload["segment_assets"]:
        if asset["annotation_eligible"]:
            assert len(asset["stable_key_candidates"]) == 1


def test_source_groups_never_cross_splits() -> None:
    payload = _load()
    split_by_group: dict[str, set[str]] = defaultdict(set)
    for row in payload["segment_assets"]:
        split_by_group[row["source_group_id"]].add(row["split"])
    assert all(len(splits) == 1 for splits in split_by_group.values())
    assert payload["authorities"]["current_youtube_canary"]["split"] == "test"
    assert payload["authorities"]["current_youtube_canary"]["forced_canary_holdout"]


def test_card_templates_are_never_arena_detector_annotations() -> None:
    payload = _load()
    assert len(payload["card_template_assets"]) == 161
    assert all(
        not row["arena_detector_annotation_eligible"]
        for row in payload["card_template_assets"]
    )


def test_manifest_artifact_hashes_resolve() -> None:
    payload = _load()
    contact = Path(payload["contact_sheet"]["path"])
    assert contact.is_file()
    assert _sha256(contact) == payload["contact_sheet"]["sha256"]
    for name in ("stable_vocabulary", "katacr_label_list"):
        row = payload["authorities"][name]
        path = ROOT / row["path"]
        assert _sha256(path) == row["sha256"]
