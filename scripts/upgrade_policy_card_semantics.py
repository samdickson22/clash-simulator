from __future__ import annotations

import argparse
import json
from pathlib import Path

from clasher.rl.checkpoint_upgrade import upgrade_v1_checkpoint_to_semantic_v3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upgrade a semantic-v1 Clasher policy to zero-preserving v3"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--seed", type=int, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = upgrade_v1_checkpoint_to_semantic_v3(
        source_path=args.source,
        output_path=args.output,
        decks_path=args.decks_path,
        seed=args.seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
