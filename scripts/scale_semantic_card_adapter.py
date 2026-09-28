from __future__ import annotations

import argparse
import json
from pathlib import Path

from clasher.rl.checkpoint_upgrade import scale_semantic_v3_adapter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scale a trained semantic-v3 residual contribution"
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alpha", type=float, required=True)
    args = parser.parse_args()
    report = scale_semantic_v3_adapter(
        source_path=args.source,
        output_path=args.output,
        alpha=args.alpha,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
