from __future__ import annotations

import argparse
import json

from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.deck_curriculum import HELD_OUT_ARCHETYPES
from clasher.rl.replay_split import (
    build_raw_cascade_splits,
    first_completed_replay_ids,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create replay-, deck-, archetype-, and chronology-disjoint splits "
            "from a completed TV Royale raw-cascade run"
        )
    )
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument("--seed", type=int, default=1_044_301)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--target-games", type=int, default=None)
    parser.add_argument("--chronology-min-arena", type=int, default=31)
    parser.add_argument(
        "--reserve-manifest",
        default=None,
        help=(
            "human-meta gate manifest whose replay IDs are excluded from every "
            "imitation split"
        ),
    )
    parser.add_argument(
        "--reserve-first-completed",
        type=int,
        default=0,
        help=(
            "exclude the first N completed replays before assigning splits; "
            "use this for a replay-disjoint incremental training wave"
        ),
    )
    held_out_group = parser.add_mutually_exclusive_group()
    held_out_group.add_argument(
        "--held-out-archetype",
        action="append",
        default=[],
        help="repeat to replace the standard whole-archetype test set",
    )
    held_out_group.add_argument(
        "--no-held-out-archetypes",
        action="store_true",
        help=(
            "disable whole-archetype exclusion so every archetype is split "
            "by deck signature between train and validation"
        ),
    )
    return parser.parse_args()


def resolve_held_out_archetypes(
    selected: list[str], *, disabled: bool
) -> frozenset[str]:
    if disabled:
        return frozenset()
    return frozenset(selected) or HELD_OUT_ARCHETYPES


def main() -> None:
    args = parse_args()
    held_out = resolve_held_out_archetypes(
        args.held_out_archetype,
        disabled=args.no_held_out_archetypes,
    )
    reserved_replays: frozenset[str] = frozenset()
    if args.reserve_manifest is not None:
        reserve_path = resolve_path(args.reserve_manifest, must_exist=True)
        reserve = json.loads(reserve_path.read_text(encoding="utf-8"))
        reserved_replays = frozenset(
            str(replay)
            for deck in reserve.get("decks", ())
            for replay in deck.get("replays", ())
        )
        if not reserved_replays:
            raise ValueError("reserve manifest contains no replay IDs")
    reserved_replays = reserved_replays.union(
        first_completed_replay_ids(
            resolve_path(args.run_manifest, must_exist=True),
            args.reserve_first_completed,
        )
    )
    manifest = build_raw_cascade_splits(
        run_manifest_path=resolve_path(args.run_manifest, must_exist=True),
        output_dir=resolve_path(args.output_dir),
        decks_path=resolve_decks_path(args.decks_path, must_exist=True),
        seed=args.seed,
        validation_fraction=args.validation_fraction,
        held_out_archetypes=held_out,
        chronology_min_arena=args.chronology_min_arena,
        target_games=args.target_games,
        reserved_replays=reserved_replays,
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
