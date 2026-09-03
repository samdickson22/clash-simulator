#!/usr/bin/env python3
"""Run one exact training shard from the frozen procedural outcome protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, cast

from scripts.collect_hog26_complete_outcomes import collect

SCHEMA = "clasher.hog26.procedural-outcome-protocol.v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_protocol(path: Path, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if payload.get("schema") != SCHEMA:
        raise ValueError("unknown procedural outcome protocol")
    for key in ("base_policy", "procedural_decks", "original_decks"):
        row = payload.get(key)
        if not isinstance(row, dict):
            raise TypeError("protocol authority row is malformed")
        authority = root / str(row["path"])
        if _sha256(authority) != row.get("sha256"):
            raise ValueError(f"protocol authority drifted: {key}")
    return cast(dict[str, Any], payload)


def collection_args(
    protocol: dict[str, Any], row: dict[str, Any], *, root: Path, device: str
) -> argparse.Namespace:
    return argparse.Namespace(
        checkpoint=root / protocol["base_policy"]["path"],
        output=root / row["output_corpus"],
        report=root / row["output_report"],
        seed=int(row["seed"]),
        episodes_per_seat=int(row["episodes_per_seat"]),
        chunk_steps=64,
        device=device,
        opponents=",".join(row["opponents"]),
        opponent_decks="",
        opponent_deck_split=row["split"],
        opponent_family_id=tuple(row["family_ids"]),
        supported_decks_path=root / protocol["procedural_decks"]["path"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--training-shard", type=int, choices=(0, 1, 2), required=True)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="mps")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol = load_protocol(args.protocol, root)
    rows = protocol.get("training")
    if not isinstance(rows, list) or len(rows) != 3:
        raise TypeError("protocol training rows are malformed")
    row = rows[args.training_shard]
    if not isinstance(row, dict):
        raise TypeError("protocol training shard is malformed")
    result = collect(collection_args(protocol, row, root=root, device=args.device))
    if int(result["episode_count"]) != int(row["expected_games"]):
        raise RuntimeError("training shard did not produce its frozen game budget")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
