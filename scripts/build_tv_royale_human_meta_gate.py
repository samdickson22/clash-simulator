"""Build a strict final-evaluation deck pool from recurring TV Royale decks."""

from __future__ import annotations

import argparse
import json

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.human_meta_decks import publish_human_meta_deck_gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--target-games", type=int, default=None)
    parser.add_argument("--min-replays", type=int, default=2)
    args = parser.parse_args()

    manifest = publish_human_meta_deck_gate(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
        decks_path=resolve_decks_path(args.decks_path, must_exist=True),
        target_games=args.target_games,
        min_replays=args.min_replays,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
