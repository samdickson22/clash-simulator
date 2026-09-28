from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.replay_split import build_raw_cascade_location_splits


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Apply an existing replay-disjoint TV Royale split to sparse "
            "deployment-clock labels"
        )
    )
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--split-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=1_045_801)
    parser.add_argument("--target-games", type=int, default=None)
    parser.add_argument("--required-label-source", default=None)
    args = parser.parse_args()

    manifest = build_raw_cascade_location_splits(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        split_manifest_path=resolve_path(args.split_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
        seed=args.seed,
        target_games=args.target_games,
        required_label_source=args.required_label_source,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
