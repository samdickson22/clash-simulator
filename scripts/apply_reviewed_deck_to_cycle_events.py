#!/usr/bin/env python3
"""Fail-closed deck closure for already extracted public HUD cycle events."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

EVENT_SCHEMA = "clasher.youtube.hud_cycle_events.v3"
DECK_SCHEMA = "clasher.youtube.reviewed_public_decks.v1"


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def apply_reviewed_deck(
    events_path: Path, reviewed_deck_path: Path, output: Path
) -> dict[str, Any]:
    events = _object(events_path)
    decks = _object(reviewed_deck_path)
    if events.get("schema") != EVENT_SCHEMA:
        raise ValueError("unsupported cycle-event schema")
    if decks.get("schema") != DECK_SCHEMA:
        raise ValueError("unsupported reviewed-deck schema")
    if events.get("video_sha256") != decks.get("video_sha256"):
        raise ValueError("cycle events and reviewed decks identify different videos")
    raw_players = decks.get("players")
    if not isinstance(raw_players, dict) or set(raw_players) != {"0", "1"}:
        raise ValueError("reviewed deck must contain players 0 and 1")
    allowed: dict[int, set[str]] = {}
    for player_id in (0, 1):
        player = raw_players[str(player_id)]
        if not isinstance(player, dict):
            raise TypeError("reviewed player entry must be an object")
        identities = player.get("card_identities")
        if not isinstance(identities, list) or len(identities) != 8:
            raise ValueError("each reviewed player deck must contain eight identities")
        if any(not isinstance(identity, str) for identity in identities):
            raise TypeError("reviewed deck identities must be strings")
        if len(set(identities)) != 8:
            raise ValueError("reviewed deck identities must be unique")
        allowed[player_id] = set(identities)

    result = copy.deepcopy(events)
    rows = result.get("events")
    if not isinstance(rows, list):
        raise TypeError("cycle events must be an array")
    filtered = 0
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("cycle-event rows must be objects")
        player_id = int(row.get("player_id", -1))
        if player_id not in allowed:
            raise ValueError("cycle-event player_id must be 0 or 1")
        identity = row.get("card_identity")
        if identity is not None and identity not in allowed[player_id]:
            row["card_identity"] = None
            row["identity_valid"] = False
            row["identity_reason"] = "outside_reviewed_public_deck"
            filtered += 1
    contract = result.get("contract")
    if not isinstance(contract, dict):
        raise TypeError("cycle-event contract must be an object")
    contract["deck_closure"] = "exactly_eight_reviewed_public_identities_per_player"
    contract["deck_closure_operation"] = "removal_only_postfilter"
    result["reviewed_deck_manifest_sha256"] = _sha256(reviewed_deck_path)
    result["source_events_sha256"] = _sha256(events_path)
    counts = result.get("counts")
    if not isinstance(counts, dict):
        raise TypeError("cycle-event counts must be an object")
    counts["identity_valid"] = sum(bool(row.get("identity_valid")) for row in rows)
    counts["complete_identity_and_placement"] = sum(
        bool(row.get("identity_valid")) and bool(row.get("placement_valid"))
        for row in rows
    )
    counts["outside_reviewed_deck_filtered"] = filtered
    _atomic_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--reviewed-deck-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = apply_reviewed_deck(args.events, args.reviewed_deck_manifest, args.output)
    print(json.dumps({"output": str(args.output), "counts": payload["counts"]}))


if __name__ == "__main__":
    main()
