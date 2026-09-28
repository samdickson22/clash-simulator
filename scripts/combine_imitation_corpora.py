from __future__ import annotations

import argparse
import json

from clasher.paths import resolve_path
from clasher.rl.imitation_mix import combine_imitation_corpora


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine compatible imitation corpora by complete episode"
    )
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument(
        "--target-samples",
        action="append",
        type=int,
        help="per-source approximate target; omit to retain every source row",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--seed", type=int, default=19_001)
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="retain exact repeated observation/action rows across sources",
    )
    parser.add_argument(
        "--allow-mixed-decision-intervals",
        action="store_true",
        help=(
            "allow whole episodes captured at different decision intervals; "
            "the combined metadata records interval 0"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = args.target_samples
    if targets is not None and len(targets) != len(args.source):
        raise SystemExit("--target-samples must be supplied once per --source")
    manifest = combine_imitation_corpora(
        sources=[resolve_path(path, must_exist=True) for path in args.source],
        output_path=resolve_path(args.output),
        manifest_path=resolve_path(args.manifest_out),
        seed=args.seed,
        target_samples=targets,
        deduplicate=not args.allow_duplicates,
        allow_mixed_decision_intervals=args.allow_mixed_decision_intervals,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
