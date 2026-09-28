from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.imitation_mix import merge_provenance_corpora


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge TV Royale deployment and explicit-wait corpora into true "
            "replay/frame chronological sequences"
        )
    )
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--seed", type=int, default=1_035_003)
    parser.add_argument(
        "--allow-single-label-episodes",
        action="store_true",
        help="retain replays that do not contain both wait and deployment labels",
    )
    parser.add_argument(
        "--prefer-first-source-on-conflict",
        action="store_true",
        help=(
            "retain the first source's label when later sources disagree at "
            "the same replay/frame; conflicts remain counted in the manifest"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = merge_provenance_corpora(
        sources=[resolve_path(path, must_exist=True) for path in args.source],
        output_path=resolve_path(args.output),
        manifest_path=resolve_path(args.manifest_out),
        seed=args.seed,
        require_mixed_actions=not args.allow_single_label_episodes,
        conflict_policy=(
            "prefer-first" if args.prefer_first_source_on_conflict else "drop"
        ),
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
