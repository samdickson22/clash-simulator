from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DECISIONS_SCHEMA = "clasher.youtube.reviewed_deck_decisions.v1"
SHEET_SCHEMA = "clasher.youtube.eight_card_deck_sheet.v1"
OUTPUT_SCHEMA = "clasher.youtube.reviewed_public_decks.v1"
INDEX_SCHEMA = "clasher.youtube.reviewed_public_deck_index.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _stable_card_keys(vocabulary: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        str(entry["stable_key"])
        for entry in vocabulary["entries"]
        if entry.get("namespace") == "card_action"
        and entry.get("policy_token_eligible") is True
    )


def finalize_reviewed_decks(
    *,
    decisions_path: Path,
    sheets_root: Path,
    vocabulary_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    decisions = _load_json(decisions_path)
    if decisions.get("schema") != DECISIONS_SCHEMA:
        raise ValueError("unsupported reviewed deck decisions schema")
    vocabulary = _load_json(vocabulary_path)
    stable_keys = _stable_card_keys(vocabulary)
    games = decisions.get("games")
    if not isinstance(games, dict) or not games:
        raise ValueError("reviewed deck decisions must contain games")

    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for video_id in sorted(games):
        player_cards = games[video_id]
        sheet_path = sheets_root / video_id / "manifest.json"
        sheet = _load_json(sheet_path)
        if sheet.get("schema") != SHEET_SCHEMA or sheet.get("video_id") != video_id:
            raise ValueError(f"invalid eight-card sheet manifest for {video_id}")
        if any(int(sheet["players"][str(player)]["cards_exposed"]) != 8 for player in (0, 1)):
            raise ValueError(f"sheet does not expose eight cards per player: {video_id}")

        players: dict[str, Any] = {}
        for player in (0, 1):
            identities = player_cards.get(str(player))
            if not isinstance(identities, list) or len(identities) != 8:
                raise ValueError(f"player {player} must have exactly eight cards: {video_id}")
            if len(set(identities)) != 8:
                raise ValueError(f"player {player} deck contains duplicates: {video_id}")
            unknown = sorted(set(map(str, identities)) - stable_keys)
            if unknown:
                raise ValueError(f"unknown current-client identities for {video_id}: {unknown}")
            players[str(player)] = {"card_identities": list(map(str, identities))}

        payload = {
            "schema": OUTPUT_SCHEMA,
            "video_id": video_id,
            "video_sha256": str(sheet["video_sha256"]),
            "players": players,
            "review_contract": {
                **decisions["review_contract"],
                "sheet_manifest_path": str(sheet_path),
                "sheet_manifest_sha256": _sha256(sheet_path),
                "sheet_artifact_sha256": str(sheet["artifact"]["sha256"]),
            },
        }
        output_path = output_dir / f"{video_id}.json"
        output_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        artifacts.append(
            {
                "video_id": video_id,
                "path": str(output_path),
                "sha256": _sha256(output_path),
                "video_sha256": str(sheet["video_sha256"]),
            }
        )

    return {
        "schema": INDEX_SCHEMA,
        "decisions_path": str(decisions_path),
        "decisions_sha256": _sha256(decisions_path),
        "vocabulary_path": str(vocabulary_path),
        "vocabulary_sha256": _sha256(vocabulary_path),
        "reviewed_games": len(artifacts),
        "artifacts": artifacts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--sheets-root", type=Path, required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()

    index = finalize_reviewed_decks(
        decisions_path=args.decisions,
        sheets_root=args.sheets_root,
        vocabulary_path=args.vocabulary,
        output_dir=args.output_dir,
    )
    args.index.parent.mkdir(parents=True, exist_ok=True)
    args.index.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
