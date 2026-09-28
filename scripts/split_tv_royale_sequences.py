from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.imitation_mix import split_provenance_corpora


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create globally replay-disjoint TV Royale train and holdout corpora"
        )
    )
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--train-output", required=True)
    parser.add_argument("--holdout-output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--seed", type=int, default=1_043_201)
    parser.add_argument("--holdout-fraction", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = split_provenance_corpora(
        sources=[resolve_path(path, must_exist=True) for path in args.source],
        train_output_path=resolve_path(args.train_output),
        holdout_output_path=resolve_path(args.holdout_output),
        manifest_path=resolve_path(args.manifest_out),
        seed=args.seed,
        holdout_fraction=args.holdout_fraction,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
