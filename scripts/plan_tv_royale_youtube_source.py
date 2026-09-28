"""Build a metadata-only TV Royale YouTube source and split plan."""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import hashlib
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from clasher.rl.oracle_corpus import atomic_write_json, file_sha256

CHANNEL_HANDLE = "@TVroyale-tv1sn"
CHANNEL_URL = "https://www.youtube.com/@TVroyale-tv1sn/videos"
CHANNEL_ID = "UCAa38XE9i5QhRT1ixzvJIDg"
STANDARD_LICENSE_HELP = "https://support.google.com/youtube/answer/2797468?hl=en"
BITRATE_SCENARIOS_MBPS = (1.5, 3.0, 5.0)
USER_ATTESTED_PERMISSION = "user_attested_channel_owner_approval"


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _parsed_date(row: dict[str, Any]) -> date | None:
    raw = row.get("upload_date")
    if isinstance(raw, str) and re.fullmatch(r"\d{8}", raw):
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    if isinstance(raw, str):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    timestamp = row.get("timestamp")
    if isinstance(timestamp, int | float):
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()
    return None


def _required_date(row: dict[str, Any]) -> date:
    value = _parsed_date(row)
    if value is None:
        raise ValueError(f"video {row.get('id')} has no upload date")
    return value


def _public_availability(row: dict[str, Any]) -> bool:
    return row.get("availability") == "public"


def _weak_metadata_fingerprint(row: dict[str, Any]) -> str:
    """Candidate-duplicate key, never proof that two videos are identical."""
    uploaded = _parsed_date(row)
    payload = {
        "title": _normalized_text(str(row.get("title", ""))),
        "duration_seconds": round(float(row.get("duration") or 0.0)),
        "upload_date": uploaded.isoformat() if uploaded else None,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if "id" not in row and "video_id" in row:
            row["id"] = row["video_id"]
        if "duration" not in row and "duration_seconds" in row:
            row["duration"] = row["duration_seconds"]
        if "webpage_url" not in row and "url" in row:
            row["webpage_url"] = row["url"]
        if "license" not in row and "youtube_license_metadata" in row:
            row["license"] = row["youtube_license_metadata"]
        selected_format = row.get("selected_format")
        if (
            "filesize_approx" not in row
            and isinstance(selected_format, dict)
            and selected_format.get("filesize_approx_bytes") is not None
        ):
            row["filesize_approx"] = selected_format["filesize_approx_bytes"]
        video_id = str(row.get("id", ""))
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError(f"invalid YouTube ID on line {line_number}")
        previous = by_id.get(video_id)
        if previous is not None:
            if previous != row:
                raise ValueError(f"conflicting metadata for YouTube ID {video_id}")
            continue
        by_id[video_id] = row
        rows.append(row)
    if not rows:
        raise ValueError("metadata inventory is empty")
    return rows


def _hf_identity_inventory(paths: list[Path]) -> dict[str, Any]:
    replay_ids: set[str] = set()
    youtube_ids: set[str] = set()
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for row in payload.get("records", ()):
            if not isinstance(row, dict) or row.get("status") != "complete":
                continue
            if row.get("replay"):
                replay_ids.add(str(row["replay"]))
            if row.get("youtube_id"):
                youtube_ids.add(str(row["youtube_id"]))
    return {
        "run_manifests": [str(path.resolve()) for path in paths],
        "completed_replay_ids": len(replay_ids),
        "explicit_youtube_ids": sorted(youtube_ids),
    }


def _title_card_candidates(
    title: str, *, enabled_card_names: tuple[str, ...]
) -> list[str]:
    normalized = f" {_normalized_text(title)} "
    candidates = []
    for card in enabled_card_names:
        token = _normalized_text(card)
        if len(token) >= 4 and f" {token} " in normalized:
            candidates.append(card)
    return sorted(candidates)


def _recent_patch_weight(uploaded: date, latest: date) -> float:
    age_days = (latest - uploaded).days
    if age_days <= 90:
        return 4.0
    if age_days <= 365:
        return 2.0
    return 1.0


def _hash_unit(seed: int, value: str) -> float:
    digest = hashlib.sha256(f"{seed}:{value}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64)


def _select_canary(rows: list[dict[str, Any]], *, count: int, seed: int) -> list[str]:
    if count <= 0:
        return []
    ordered = sorted(rows, key=lambda row: (_parsed_date(row) or date.min, row["id"]))
    selected: list[str] = []

    def add(row: dict[str, Any]) -> None:
        video_id = str(row["id"])
        if video_id not in selected and len(selected) < count:
            selected.append(video_id)

    for row in ordered[:2] + ordered[-2:]:
        add(row)
    by_duration = sorted(ordered, key=lambda row: float(row.get("duration") or 0.0))
    if by_duration:
        add(by_duration[0])
        add(by_duration[-1])
    by_format: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
    for row in sorted(ordered, key=lambda item: str(item["id"])):
        key = (row.get("width"), row.get("height"), row.get("fps"))
        by_format.setdefault(key, row)
    for row in by_format.values():
        add(row)
    for row in sorted(ordered, key=lambda item: _hash_unit(seed, str(item["id"]))):
        add(row)
    return selected


def build_source_plan(
    *,
    metadata_path: Path,
    hf_run_manifests: list[Path],
    enabled_card_names: tuple[str, ...] = (),
    seed: int = 1_064_201,
    chronology_fraction: float = 0.10,
    validation_fraction: float = 0.10,
    canary_count: int = 10,
    permission_basis: str | None = None,
    permission_date: str | None = None,
) -> dict[str, Any]:
    if not 0.0 < chronology_fraction < 0.5:
        raise ValueError("chronology fraction must be in (0, 0.5)")
    if not 0.0 < validation_fraction < 0.5:
        raise ValueError("validation fraction must be in (0, 0.5)")
    permission_attested = permission_basis == USER_ATTESTED_PERMISSION
    if permission_attested:
        if permission_date is None:
            raise ValueError("attested permission requires a date")
        date.fromisoformat(permission_date)
    elif permission_basis is not None or permission_date is not None:
        raise ValueError("unsupported or incomplete permission provenance")
    rows = _load_jsonl(metadata_path)
    hf = _hf_identity_inventory(hf_run_manifests)
    youtube_ids = {str(row["id"]) for row in rows}
    explicit_cross_source_ids = sorted(
        youtube_ids.intersection(hf["explicit_youtube_ids"])
    )

    availability = Counter(str(row.get("availability")) for row in rows)
    licenses = Counter(str(row.get("license")) for row in rows)
    eligible = [
        row
        for row in rows
        if _public_availability(row)
        and _parsed_date(row) is not None
        and float(row.get("duration") or 0.0) > 0.0
    ]
    if not eligible:
        raise ValueError("inventory has no date-complete public videos")
    concrete_dates = sorted(_required_date(row) for row in eligible)
    latest = concrete_dates[-1]
    chronology_count = max(1, math.ceil(len(eligible) * chronology_fraction))
    chronology_cutoff = concrete_dates[-chronology_count]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[_weak_metadata_fingerprint(row)].append(row)

    assignments: dict[str, str] = {}
    weak_candidate_groups = 0
    for fingerprint, group in sorted(groups.items()):
        if len(group) > 1:
            weak_candidate_groups += 1
        group_dates = [_parsed_date(row) for row in group]
        if any(value is not None and value >= chronology_cutoff for value in group_dates):
            split = "chronology_test"
        elif _hash_unit(seed, fingerprint) < validation_fraction:
            split = "validation"
        else:
            split = "train"
        assignments.update({str(row["id"]): split for row in group})

    title_candidates = {
        str(row["id"]): _title_card_candidates(
            str(row.get("title", "")), enabled_card_names=enabled_card_names
        )
        for row in eligible
    }
    title_candidates = {
        video_id: cards for video_id, cards in title_candidates.items() if cards
    }
    canary_ids = _select_canary(eligible, count=canary_count, seed=seed)
    by_id = {str(row["id"]): row for row in eligible}
    duration_hours = sum(float(row.get("duration") or 0.0) for row in rows) / 3600.0
    known_sizes = [
        float(row["filesize_approx"])
        for row in rows
        if isinstance(row.get("filesize_approx"), int | float)
        and float(row["filesize_approx"]) > 0.0
    ]
    known_size_duration = sum(
        float(row.get("duration") or 0.0)
        for row in rows
        if isinstance(row.get("filesize_approx"), int | float)
        and float(row["filesize_approx"]) > 0.0
    )
    observed_bitrate = (
        sum(known_sizes) * 8.0 / known_size_duration / 1_000_000.0
        if known_size_duration > 0.0
        else None
    )
    entries = []
    for row in eligible:
        uploaded = _parsed_date(row)
        assert uploaded is not None
        video_id = str(row["id"])
        entries.append(
            {
                "id": video_id,
                "url": row.get("webpage_url")
                or f"https://www.youtube.com/watch?v={video_id}",
                "upload_date": uploaded.isoformat(),
                "duration_seconds": float(row["duration"]),
                "width": row.get("width"),
                "height": row.get("height"),
                "fps": row.get("fps"),
                "availability": row.get("availability"),
                "license": row.get("license"),
                "weak_metadata_fingerprint": _weak_metadata_fingerprint(row),
                "split": assignments[video_id],
                "recent_patch_weight": _recent_patch_weight(uploaded, latest),
                "uncertified_title_card_candidates": title_candidates.get(
                    video_id, []
                ),
            }
        )

    split_counts = Counter(assignments.values())
    return {
        "schema": "tv-royale-youtube-source-plan-v1",
        "channel": {
            "handle": CHANNEL_HANDLE,
            "url": CHANNEL_URL,
            "channel_id": CHANNEL_ID,
        },
        "metadata": {
            "path": str(metadata_path.resolve()),
            "sha256": file_sha256(metadata_path),
            "videos": len(rows),
            "eligible_public_date_complete": len(eligible),
            "duration_hours": duration_hours,
            "date_min": concrete_dates[0].isoformat(),
            "date_max": latest.isoformat(),
            "availability_counts": dict(sorted(availability.items())),
            "license_counts": dict(sorted(licenses.items())),
        },
        "rights_gate": {
            "permission_basis": permission_basis,
            "permission_date": permission_date,
            "permission_source_channel": CHANNEL_URL if permission_attested else None,
            "permission_attested": permission_attested,
            "bounded_ten_video_canary_authorized": permission_attested,
            "bulk_wave_operationally_authorized": False,
            "bulk_wave_requires_canary_and_h100_coordination": True,
            "legal_or_creator_permission_required": not permission_attested,
            "license_metadata_null_is_permission": False,
            "public_cc_license_claimed": False,
            "standard_youtube_license_is_default": True,
            "official_license_help": STANDARD_LICENSE_HELP,
            "external_contact_performed": False,
        },
        "deduplication": {
            "youtube_id_duplicates": len(rows) - len(youtube_ids),
            "weak_metadata_candidate_groups": weak_candidate_groups,
            "weak_metadata_fingerprint_is_proof": False,
            "hf": hf,
            "explicit_cross_source_youtube_ids": explicit_cross_source_ids,
            "cross_source_status": (
                "explicit_id_overlap_found"
                if explicit_cross_source_ids
                else "unresolved_requires_bounded_media_fingerprints"
            ),
            "required_media_signature": (
                "SHA256 of normalized frames plus pHash at 10%, 50%, and 90%; "
                "group matches atomically before split assignment"
            ),
        },
        "label_coverage": {
            "certified_enabled_cards_from_titles": [],
            "certified_decks_from_titles_or_thumbnail_metadata": [],
            "uncertified_title_candidate_videos": len(title_candidates),
            "reason": (
                "titles primarily name players and card-like names can be player "
                "handles; thumbnail URLs contain no defensible card/deck labels"
            ),
        },
        "split_contract": {
            "seed": seed,
            "group_key": "weak title-duration-date candidate group",
            "groups_are_atomic": True,
            "chronology_fraction_requested": chronology_fraction,
            "chronology_cutoff": chronology_cutoff.isoformat(),
            "validation_fraction_requested": validation_fraction,
            "counts": dict(sorted(split_counts.items())),
            "recent_patch_weights": {
                "age_0_to_90_days": 4.0,
                "age_91_to_365_days": 2.0,
                "older": 1.0,
                "reference_date": latest.isoformat(),
            },
        },
        "storage": {
            "scenario_gb_decimal": {
                str(bitrate): duration_hours * 3600.0 * bitrate / 8.0 / 1000.0
                for bitrate in BITRATE_SCENARIOS_MBPS
            },
            "known_filesize_samples": len(known_sizes),
            "observed_sample_bitrate_mbps": observed_bitrate,
            "observed_scaled_gb_decimal": (
                duration_hours * 3600.0 * observed_bitrate / 8.0 / 1000.0
                if observed_bitrate is not None
                else None
            ),
            "bulk_download_planned": False,
        },
        "canary": {
            "count": len(canary_ids),
            "video_ids": canary_ids,
            "videos": [
                {
                    "id": video_id,
                    "url": by_id[video_id].get("webpage_url")
                    or f"https://www.youtube.com/watch?v={video_id}",
                    "split": assignments[video_id],
                    "upload_date": _required_date(by_id[video_id]).isoformat(),
                    "duration_seconds": float(by_id[video_id]["duration"]),
                    "width": by_id[video_id].get("width"),
                    "height": by_id[video_id].get("height"),
                    "fps": by_id[video_id].get("fps"),
                }
                for video_id in canary_ids
            ],
            "video_downloaded": False,
        },
        "entries": entries,
    }


def _load_enabled_cards(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    stack: list[Any] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            if value and all(isinstance(item, str) for item in value):
                values.update(str(item) for item in value)
            else:
                stack.extend(value)
    return tuple(sorted(values))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metadata-jsonl", type=Path, required=True)
    parser.add_argument("--hf-run-manifest", type=Path, action="append", default=[])
    parser.add_argument("--enabled-decks-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1_064_201)
    parser.add_argument("--chronology-fraction", type=float, default=0.10)
    parser.add_argument("--validation-fraction", type=float, default=0.10)
    parser.add_argument("--canary-count", type=int, default=10)
    parser.add_argument(
        "--permission-basis", choices=(USER_ATTESTED_PERMISSION,)
    )
    parser.add_argument("--permission-date")
    args = parser.parse_args()
    plan = build_source_plan(
        metadata_path=args.metadata_jsonl,
        hf_run_manifests=args.hf_run_manifest,
        enabled_card_names=_load_enabled_cards(args.enabled_decks_json),
        seed=args.seed,
        chronology_fraction=args.chronology_fraction,
        validation_fraction=args.validation_fraction,
        canary_count=args.canary_count,
        permission_basis=args.permission_basis,
        permission_date=args.permission_date,
    )
    atomic_write_json(args.output, plan)
    print(json.dumps(plan, sort_keys=True))


if __name__ == "__main__":
    main()
