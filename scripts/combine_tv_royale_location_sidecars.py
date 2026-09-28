from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.replay_split import combine_raw_cascade_location_corpora


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Combine verified TV Royale deployment-clock sidecars as "
            "independent one-step samples"
        )
    )
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--seed", type=int, default=1_045_801)
    parser.add_argument("--target-games", type=int, default=None)
    parser.add_argument("--required-label-source", default=None)
    args = parser.parse_args()

    manifest = combine_raw_cascade_location_corpora(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        output_path=resolve_path(args.output),
        manifest_path=resolve_path(args.manifest_out),
        seed=args.seed,
        target_games=args.target_games,
        required_label_source=args.required_label_source,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
