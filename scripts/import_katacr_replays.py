from __future__ import annotations

import argparse
import json

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.katacr_replay import default_external_paths, import_katacr_replays


def parse_args() -> argparse.Namespace:
    dataset_root, source_root, classifier = default_external_paths()
    parser = argparse.ArgumentParser(
        description="Convert KataCR expert Hog 2.6 replays into a Clasher imitation corpus"
    )
    parser.add_argument("--dataset-root", default=str(dataset_root))
    parser.add_argument("--katacr-source-root", default=str(source_root))
    parser.add_argument("--classifier-metadata", default=str(classifier))
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--max-entities", type=int, default=128)
    parser.add_argument("--max-episodes", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata, stats = import_katacr_replays(
        dataset_root=resolve_path(args.dataset_root, must_exist=True),
        katacr_source_root=resolve_path(args.katacr_source_root, must_exist=True),
        classifier_metadata=resolve_path(args.classifier_metadata, must_exist=True),
        decks_path=resolve_decks_path(args.decks_path, must_exist=True),
        output_path=resolve_path(args.output),
        manifest_path=resolve_path(args.manifest_out),
        max_entities=args.max_entities,
        max_episodes=args.max_episodes,
        progress=True,
    )
    print(json.dumps({"metadata": metadata.__dict__, "stats": stats.__dict__}, default=list))


if __name__ == "__main__":
    main()
