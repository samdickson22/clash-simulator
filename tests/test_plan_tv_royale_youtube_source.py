from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts.plan_tv_royale_youtube_source import build_source_plan


def _metadata_row(
    index: int,
    *,
    uploaded: date,
    availability: str = "public",
    title: str | None = None,
    duration: int | None = None,
) -> dict[str, object]:
    return {
        "id": f"v{index:010d}",
        "title": title or f"TOP 200 Player {index} vs Rival {index}",
        "upload_date": uploaded.strftime("%Y%m%d"),
        "duration": duration or 180 + index,
        "availability": availability,
        "license": None,
        "width": 888 if index % 2 else 1182,
        "height": 1920 if index % 2 else 2560,
        "fps": 60,
        "filesize_approx": 100_000_000 + index,
        "webpage_url": f"https://www.youtube.com/watch?v=v{index:010d}",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_builds_rights_gated_atomic_chronology_plan(tmp_path: Path) -> None:
    start = date(2026, 1, 1)
    rows = [_metadata_row(index, uploaded=start + timedelta(days=index)) for index in range(20)]
    rows.append(
        _metadata_row(
            99,
            uploaded=start + timedelta(days=99),
            availability="subscriber_only",
        )
    )
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(inventory, rows)

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[],
        seed=17,
        chronology_fraction=0.10,
        validation_fraction=0.20,
        canary_count=10,
    )

    assert plan["metadata"]["videos"] == 21
    assert plan["metadata"]["eligible_public_date_complete"] == 20
    assert plan["metadata"]["availability_counts"]["subscriber_only"] == 1
    assert plan["rights_gate"]["bounded_ten_video_canary_authorized"] is False
    assert plan["rights_gate"]["bulk_wave_operationally_authorized"] is False
    assert plan["rights_gate"]["license_metadata_null_is_permission"] is False
    assignments = {row["id"]: row["split"] for row in plan["entries"]}
    assert assignments["v0000000018"] == "chronology_test"
    assert assignments["v0000000019"] == "chronology_test"
    assert "v0000000099" not in assignments
    assert len(plan["canary"]["video_ids"]) == 10


def test_candidate_duplicate_group_never_crosses_splits(tmp_path: Path) -> None:
    start = date(2025, 1, 1)
    rows = [_metadata_row(index, uploaded=start + timedelta(days=index)) for index in range(12)]
    rows[0]["title"] = "same match"
    rows[1]["title"] = "same match"
    rows[0]["duration"] = 240
    rows[1]["duration"] = 240
    rows[1]["upload_date"] = rows[0]["upload_date"]
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(inventory, rows)

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[],
        seed=3,
        chronology_fraction=0.10,
        validation_fraction=0.20,
    )

    by_id = {row["id"]: row for row in plan["entries"]}
    assert by_id["v0000000000"]["weak_metadata_fingerprint"] == by_id[
        "v0000000001"
    ]["weak_metadata_fingerprint"]
    assert by_id["v0000000000"]["split"] == by_id["v0000000001"]["split"]
    assert plan["deduplication"]["weak_metadata_fingerprint_is_proof"] is False


def test_title_card_names_are_candidates_not_certified_coverage(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(
        inventory,
        [
            _metadata_row(
                1,
                uploaded=date(2026, 8, 9),
                title="TOP200 I love Mini Pekka vs Rival",
            )
        ],
    )

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[],
        enabled_card_names=("Mini Pekka", "Hog Rider"),
    )

    assert plan["label_coverage"]["certified_enabled_cards_from_titles"] == []
    assert plan["label_coverage"]["uncertified_title_candidate_videos"] == 1
    assert plan["entries"][0]["uncertified_title_card_candidates"] == [
        "Mini Pekka"
    ]


def test_reports_explicit_hf_id_overlap_but_requires_media_for_legacy_ids(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(inventory, [_metadata_row(7, uploaded=date(2026, 8, 9))])
    hf = tmp_path / "hf.json"
    hf.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "status": "complete",
                        "replay": "a-legacy-uuid",
                        "youtube_id": "v0000000007",
                    }
                ]
            }
        )
    )

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[hf],
    )

    assert plan["deduplication"]["explicit_cross_source_youtube_ids"] == [
        "v0000000007"
    ]
    assert plan["deduplication"]["cross_source_status"] == (
        "explicit_id_overlap_found"
    )


def test_rejects_flat_metadata_without_dates_for_split_assignment(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "inventory.jsonl"
    row = _metadata_row(1, uploaded=date(2026, 8, 9))
    row["upload_date"] = None
    row["availability"] = None
    _write_jsonl(inventory, [row])

    with pytest.raises(ValueError, match="no date-complete public videos"):
        build_source_plan(metadata_path=inventory, hf_run_manifests=[])


def test_records_user_attested_permission_without_claiming_cc(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(inventory, [_metadata_row(1, uploaded=date(2026, 8, 9))])

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[],
        permission_basis="user_attested_channel_owner_approval",
        permission_date="2026-08-17",
    )

    rights = plan["rights_gate"]
    assert rights["permission_attested"] is True
    assert rights["bounded_ten_video_canary_authorized"] is True
    assert rights["bulk_wave_operationally_authorized"] is False
    assert rights["public_cc_license_claimed"] is False
    assert rights["permission_source_channel"].endswith("/@TVroyale-tv1sn/videos")


def test_accepts_sanitized_canary_metadata_schema(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.jsonl"
    _write_jsonl(
        inventory,
        [
            {
                "video_id": "abcdefghijk",
                "url": "https://www.youtube.com/watch?v=abcdefghijk",
                "upload_date": "2026-08-09",
                "duration_seconds": 320,
                "availability": "public",
                "youtube_license_metadata": None,
                "selected_format": {"filesize_approx_bytes": 123_456},
            }
        ],
    )

    plan = build_source_plan(
        metadata_path=inventory,
        hf_run_manifests=[],
        permission_basis="user_attested_channel_owner_approval",
        permission_date="2026-08-17",
    )

    assert plan["entries"][0]["id"] == "abcdefghijk"
    assert plan["storage"]["known_filesize_samples"] == 1
