"""Audit TV Royale supervision provenance, coverage, and split leakage.

This gate deliberately distinguishes a played-card/type label from a genuine
deployment-location label.  A type-only action is encoded with tile zero so it
can reuse the imitation corpus schema; that placeholder must never silently
become spatial supervision.
"""

from __future__ import annotations

# mypy: disable-error-code="import-untyped"
import argparse
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from clasher.rl.common import NUM_HAND_SLOTS, NUM_TILES
from clasher.rl.imitation import load_corpus
from clasher.rl.oracle_corpus import atomic_write_json, file_sha256
from clasher.rl.replay_split import STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE

EXPECTED_FOUR_WAY_SPLITS = (
    "train",
    "validation",
    "archetype_test",
    "chronology_test",
)


def recover_future_confirmed_next_card_labels(
    *,
    hand_ids: np.ndarray,
    expert_actions: np.ndarray,
    episode_ids: np.ndarray,
    source_replays: np.ndarray,
    source_frames: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Recover the player's visible pre-play Next card using later evidence.

    The label for row ``i`` is the card that visibly fills the played hand slot
    at row ``i + 1``.  It is accepted only within the same replay and episode,
    with increasing source time and unchanged other visible hand slots.  The
    result is offline hindsight supervision for a HUD value that was public at
    row ``i``; callers must never expose it as an observation before the live
    HUD can show or predict it.
    """
    hands = np.asarray(hand_ids, dtype=np.int64)
    actions = np.asarray(expert_actions, dtype=np.int64)
    episodes = np.asarray(episode_ids, dtype=np.int64)
    replays = np.asarray(source_replays).astype(str)
    frames = np.asarray(source_frames, dtype=np.int64)
    samples = actions.size
    if (
        hands.ndim != 2
        or hands.shape[0] != samples
        or hands.shape[1] < NUM_HAND_SLOTS
        or episodes.shape != (samples,)
        or replays.shape != (samples,)
        or frames.shape != (samples,)
    ):
        raise ValueError("future-confirmed Next-card inputs are misaligned")

    labels = np.zeros(samples, dtype=np.int64)
    mask = np.zeros(samples, dtype=np.bool_)
    placement_limit = NUM_HAND_SLOTS * NUM_TILES
    for index in range(samples - 1):
        action = int(actions[index])
        if not 0 <= action < placement_limit:
            continue
        if (
            episodes[index + 1] != episodes[index]
            or replays[index + 1] != replays[index]
            or frames[index + 1] <= frames[index]
        ):
            continue
        slot = action // NUM_TILES
        other_slots = [value for value in range(NUM_HAND_SLOTS) if value != slot]
        if not np.array_equal(
            hands[index, other_slots], hands[index + 1, other_slots]
        ):
            continue
        played = int(hands[index, slot])
        refill = int(hands[index + 1, slot])
        if played <= 0 or refill <= 0 or refill == played:
            continue
        labels[index] = refill
        mask[index] = True
    return labels, mask


class SupervisionAuditError(ValueError):
    """The corpus is unsafe for the requested supervision contract."""

    def __init__(self, issues: list[str], report: dict[str, Any]) -> None:
        super().__init__("; ".join(issues))
        self.issues = tuple(issues)
        self.report = report


def _resolved_artifact(
    row: dict[str, Any],
    *,
    path_key: str,
    digest_key: str,
    label: str,
) -> Path:
    path = Path(str(row.get(path_key, ""))).resolve()
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    expected = row.get(digest_key)
    if expected is not None and file_sha256(path) != expected:
        raise ValueError(f"{label} digest mismatch: {path}")
    return path


def _source_label_sources(split_row: dict[str, Any]) -> list[str]:
    sources: set[str] = set()
    manifest_value = split_row.get("manifest")
    if not manifest_value:
        return []
    manifest_path = Path(str(manifest_value)).resolve()
    if not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in payload.get("sources", ()):
        source = row.get("label_source")
        if isinstance(source, str) and source:
            sources.add(source)
    return sorted(sources)


def summarize_supervision_corpus(
    corpus_path: Path,
    *,
    source_label_sources: list[str] | None = None,
) -> dict[str, Any]:
    """Summarize labels actually present in one imitation artifact."""
    metadata, arrays = load_corpus(corpus_path)
    actions = np.asarray(arrays["expert_actions"], dtype=np.int64)
    placement_limit = NUM_HAND_SLOTS * NUM_TILES
    placements = actions < placement_limit
    noops = actions == placement_limit
    abilities = actions == placement_limit + 1
    unknown = actions > placement_limit + 1
    placement_actions = actions[placements]
    placement_count = int(placement_actions.size)
    tiles = placement_actions % NUM_TILES
    slots = placement_actions // NUM_TILES

    target_tokens = arrays["hand_ids"][np.flatnonzero(placements), slots]
    target_cards = {
        metadata.token_names[int(token)]
        for token in target_tokens.tolist()
        if 0 <= int(token) < len(metadata.token_names)
        and not metadata.token_names[int(token)].startswith("<")
    }

    globals_ = np.asarray(arrays["global_features"])
    clock = globals_[:, 0] if globals_.ndim == 2 and globals_.shape[1] else None
    with np.load(corpus_path, allow_pickle=False) as payload:
        source_replays = (
            payload["source_replays"].astype(str)
            if "source_replays" in payload.files
            else None
        )
        source_frames = (
            payload["source_frames"].astype(np.int64)
            if "source_frames" in payload.files
            else None
        )

    future_next: dict[str, Any]
    if source_replays is not None and source_frames is not None:
        next_labels, next_mask = recover_future_confirmed_next_card_labels(
            hand_ids=arrays["hand_ids"],
            expert_actions=actions,
            episode_ids=arrays["episode_ids"],
            source_replays=source_replays,
            source_frames=source_frames,
        )
        recoverable = int(np.count_nonzero(next_mask))
        eligible = placement_count
        future_next = {
            "eligible_plays": eligible,
            "recovered_labels": recoverable,
            "coverage": recoverable / max(1, eligible),
            "distinct_cards": int(np.unique(next_labels[next_mask]).size),
            "label_only_future_confirmed": True,
            "live_policy_input_before_observation": False,
            "cross_episode_lookahead": 0,
            "cross_replay_lookahead": 0,
        }
    else:
        future_next = {
            "eligible_plays": placement_count,
            "recovered_labels": 0,
            "coverage": 0.0,
            "distinct_cards": 0,
            "label_only_future_confirmed": True,
            "live_policy_input_before_observation": False,
            "unavailable_reason": "corpus has no source replay/frame provenance",
        }

    tile_zero = int(np.count_nonzero(tiles == 0))
    unique_tiles = int(np.unique(tiles).size) if placement_count else 0
    label_sources = sorted(
        {metadata.label_source, *(source_label_sources or [])}
    )
    type_only = any("type-only" in source.lower() for source in label_sources)
    strict_visual = STRICT_TV_ROYALE_LOCATION_LABEL_SOURCE in label_sources
    placeholder_tile_zero = placement_count > 0 and unique_tiles == 1 and tile_zero > 0
    genuine_spatial = strict_visual and unique_tiles > 1 and not type_only

    return {
        "path": str(corpus_path.resolve()),
        "sha256": file_sha256(corpus_path),
        "samples": int(metadata.samples),
        "label_sources": label_sources,
        "events": {
            "placement_or_play": placement_count,
            "noops": int(np.count_nonzero(noops)),
            "abilities": int(np.count_nonzero(abilities)),
            "unknown_actions": int(np.count_nonzero(unknown)),
            "distinct_target_cards": len(target_cards),
            "target_cards": sorted(target_cards),
            "source_replays": (
                int(np.unique(source_replays).size)
                if source_replays is not None
                else None
            ),
            "source_frames": (
                int(np.unique(source_frames).size)
                if source_frames is not None
                else None
            ),
            "clock_feature_distinct": (
                int(np.unique(clock).size) if clock is not None else None
            ),
            "clock_feature_min": (
                float(np.min(clock)) if clock is not None and clock.size else None
            ),
            "clock_feature_max": (
                float(np.max(clock)) if clock is not None and clock.size else None
            ),
            "future_confirmed_player_next_card": future_next,
        },
        "spatial": {
            "distinct_tiles": unique_tiles,
            "tile_zero_samples": tile_zero,
            "tile_zero_fraction": (
                tile_zero / placement_count if placement_count else None
            ),
            "type_only_provenance": type_only,
            "strict_visual_provenance": strict_visual,
            "placeholder_tile_zero": placeholder_tile_zero,
            "genuine_spatial_supervision": genuine_spatial,
        },
    }


def _pairwise_overlap(
    splits: dict[str, dict[str, Any]], key: str
) -> dict[str, list[str]]:
    overlap: dict[str, list[str]] = {}
    for left, right in combinations(sorted(splits), 2):
        shared = sorted(
            {str(value) for value in splits[left].get(key, ())}.intersection(
                str(value) for value in splits[right].get(key, ())
            )
        )
        if shared:
            overlap[f"{left}:{right}"] = shared
    return overlap


def audit_split_manifest(
    manifest_path: Path,
    *,
    require_spatial: bool = False,
    require_four_way: bool = False,
) -> dict[str, Any]:
    """Audit one split manifest and fail closed on leakage or fake locations."""
    manifest_path = manifest_path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_splits = payload.get("splits")
    if not isinstance(raw_splits, dict) or not raw_splits:
        raise ValueError("split manifest has no splits")
    splits = {str(name): dict(row) for name, row in raw_splits.items()}
    issues: list[str] = []

    missing = sorted(set(EXPECTED_FOUR_WAY_SPLITS).difference(splits))
    if require_four_way and missing:
        issues.append(f"missing required splits: {missing}")

    replay_overlap = _pairwise_overlap(splits, "replay_ids")
    deck_overlap = _pairwise_overlap(splits, "deck_hashes")
    if replay_overlap:
        issues.append(f"replay leakage: {sorted(replay_overlap)}")
    if deck_overlap:
        issues.append(f"deck leakage: {sorted(deck_overlap)}")

    held_out = {str(value) for value in payload.get("held_out_archetypes", ())}
    train_archetypes = {
        str(value) for value in splits.get("train", {}).get("archetypes", {})
    }
    archetype_overlap = sorted(held_out.intersection(train_archetypes))
    if archetype_overlap:
        issues.append(f"held-out archetypes appear in train: {archetype_overlap}")

    chronology_min_arena = payload.get("chronology_min_arena")
    chronology_arenas = splits.get("chronology_test", {}).get("arenas", {})
    chronology_nonanchor_arenas: list[str] = []
    chronology_anchor_present: bool | None = None
    if chronology_min_arena is not None and isinstance(chronology_arenas, dict):
        chronology_anchor_present = False
        for arena in chronology_arenas:
            try:
                arena_number = int(str(arena).removeprefix("arena_"))
            except ValueError:
                chronology_nonanchor_arenas.append(str(arena))
                continue
            if arena_number >= int(chronology_min_arena):
                chronology_anchor_present = True
            else:
                chronology_nonanchor_arenas.append(str(arena))
        # Deck-normalization components are assigned atomically.  A component
        # anchored by a late-arena replay can legitimately include an earlier
        # arena; requiring every member to exceed the threshold would break the
        # stronger deck-disjointness contract.
        if not chronology_anchor_present:
            issues.append("chronology split has no late-arena anchor")

    summaries: dict[str, dict[str, Any]] = {}
    for name, row in splits.items():
        output_path = _resolved_artifact(
            row,
            path_key="output",
            digest_key="output_sha256",
            label=f"split {name}",
        )
        summary = summarize_supervision_corpus(
            output_path,
            source_label_sources=_source_label_sources(row),
        )
        summaries[name] = summary
        if int(row.get("samples", summary["samples"])) != summary["samples"]:
            issues.append(f"split {name} sample accounting mismatch")
        spatial = summary["spatial"]
        if require_spatial and not spatial["genuine_spatial_supervision"]:
            issues.append(
                f"split {name} is not genuine spatial supervision "
                f"(sources={summary['label_sources']}, "
                f"distinct_tiles={spatial['distinct_tiles']}, "
                f"tile_zero_fraction={spatial['tile_zero_fraction']})"
            )

    report: dict[str, Any] = {
        "schema": "tv-royale-supervision-audit-v1",
        "status": "rejected" if issues else "verified",
        "manifest": str(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "requested_contract": {
            "spatial": require_spatial,
            "four_way": require_four_way,
        },
        "split_names": sorted(splits),
        "leakage": {
            "replay_overlap": replay_overlap,
            "deck_hash_overlap": deck_overlap,
            "held_out_archetype_train_overlap": archetype_overlap,
            "chronology_anchor_present": chronology_anchor_present,
            "chronology_nonanchor_component_arenas": sorted(
                chronology_nonanchor_arenas
            ),
        },
        "splits": summaries,
        "issues": issues,
    }
    if issues:
        raise SupervisionAuditError(issues, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-spatial", action="store_true")
    parser.add_argument("--require-four-way", action="store_true")
    args = parser.parse_args()
    try:
        report = audit_split_manifest(
            args.manifest,
            require_spatial=args.require_spatial,
            require_four_way=args.require_four_way,
        )
    except SupervisionAuditError as exc:
        report = exc.report
        if args.output is not None:
            atomic_write_json(args.output, report)
        print(json.dumps(report, sort_keys=True))
        raise SystemExit(3) from exc
    if args.output is not None:
        atomic_write_json(args.output, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
