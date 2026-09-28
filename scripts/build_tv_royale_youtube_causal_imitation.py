from __future__ import annotations

import argparse
import json
from pathlib import Path

from clasher.paths import resolve_path
from clasher.rl.youtube_causal_corpus import (
    CausalCorpusBuildConfig,
    build_causal_imitation_corpus,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build recurrent current-frame imitation tensors from a verified "
            "deck-closed YouTube causal-corpus audit"
        )
    )
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--schema-checkpoint", type=Path, required=True)
    parser.add_argument("--decks-path", type=Path, default=Path("decks.json"))
    parser.add_argument("--output-corpus", type=Path, required=True)
    parser.add_argument("--output-sidecar", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1_067_001)
    parser.add_argument("--maximum-replays", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_causal_imitation_corpus(
        CausalCorpusBuildConfig(
            audit_path=resolve_path(args.audit, must_exist=True),
            schema_checkpoint=resolve_path(
                args.schema_checkpoint, must_exist=True
            ),
            decks_path=resolve_path(args.decks_path, must_exist=True),
            output_corpus=resolve_path(args.output_corpus),
            output_sidecar=resolve_path(args.output_sidecar),
            output_manifest=resolve_path(args.manifest_out),
            seed=args.seed,
            maximum_replays=args.maximum_replays,
        )
    )
    print(
        json.dumps(
            {
                "manifest": str(args.manifest_out),
                "counts": payload["counts"],
                "artifacts": payload["artifacts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

