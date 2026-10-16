from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence

from .paths import (
    checkpoints_dir,
    decks_path,
    gamedata_path,
    latest_checkpoint,
    project_root,
)


def _dispatch(module_name: str, module_args: Sequence[str]) -> None:
    normalized_args = list(module_args)
    if normalized_args and normalized_args[0] == "--":
        normalized_args = normalized_args[1:]
    module = importlib.import_module(module_name)
    if not hasattr(module, "main"):
        raise RuntimeError(f"{module_name} has no main()")
    prev_argv = sys.argv[:]
    try:
        sys.argv = [module_name, *normalized_args]
        module.main()
    finally:
        sys.argv = prev_argv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clasher",
        description="Unified CLI for training, watching, and evaluating policies",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train", help="Train the recurrent entity-spatial policy")
    train.add_argument("args", nargs=argparse.REMAINDER)

    train_legacy = sub.add_parser(
        "train-legacy", help="Run the deprecated raster PPO trainer"
    )
    train_legacy.add_argument("args", nargs=argparse.REMAINDER)

    train_async = sub.add_parser("train-async", help="Run async self-play trainer")
    train_async.add_argument("args", nargs=argparse.REMAINDER)

    train_dagger = sub.add_parser(
        "train-dagger", help="Train with FDTS oracle + DAgger"
    )
    train_dagger.add_argument("args", nargs=argparse.REMAINDER)

    imitation = sub.add_parser(
        "imitation",
        help="Collect fixed oracle demonstrations or fit a matched V2 warm start",
    )
    imitation.add_argument("args", nargs=argparse.REMAINDER)

    watch = sub.add_parser("watch", help="Watch policy battles in pygame")
    watch.add_argument("args", nargs=argparse.REMAINDER)

    evaluate = sub.add_parser("eval", help="Evaluate policy checkpoint")
    evaluate.add_argument("args", nargs=argparse.REMAINDER)

    gym_smoke = sub.add_parser("gym-smoke", help="Run Gymnasium env smoke rollout")
    gym_smoke.add_argument("args", nargs=argparse.REMAINDER)

    determinism = sub.add_parser(
        "determinism-check", help="Run seeded rollout hash determinism check"
    )
    determinism.add_argument("args", nargs=argparse.REMAINDER)

    benchmark = sub.add_parser("benchmark", help="Run RL benchmark suite")
    benchmark.add_argument("args", nargs=argparse.REMAINDER)

    strategy_benchmark = sub.add_parser(
        "strategy-benchmark",
        help="Evaluate a policy against deterministic public-information strategies",
    )
    strategy_benchmark.add_argument("args", nargs=argparse.REMAINDER)

    replay_validate = sub.add_parser(
        "replay-validate",
        help="Compare normalized real-match public frames with a simulator trace",
    )
    replay_validate.add_argument("args", nargs=argparse.REMAINDER)

    latest = sub.add_parser("latest-checkpoint", help="Print latest checkpoint path")
    latest.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    latest.add_argument("--pattern", default="policy_v2_update_*.pt")

    paths = sub.add_parser("paths", help="Print resolved project/data paths")
    paths.add_argument("--decks-path", default="decks.json")
    paths.add_argument("--gamedata-path", default="gamedata.json")
    paths.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "train":
        _dispatch("clasher.rl.train_recurrent", args.args)
        return
    if args.command == "train-legacy":
        _dispatch("clasher.rl.train_selfplay", args.args)
        return
    if args.command == "train-async":
        _dispatch("clasher.rl.train_selfplay_async", args.args)
        return
    if args.command == "train-dagger":
        _dispatch("clasher.rl.train_dagger_oracle", args.args)
        return
    if args.command == "imitation":
        _dispatch("clasher.rl.imitation", args.args)
        return
    if args.command == "watch":
        _dispatch("clasher.rl.watch_policy_battle", args.args)
        return
    if args.command == "eval":
        _dispatch("clasher.rl.eval", args.args)
        return
    if args.command == "gym-smoke":
        _dispatch("clasher.rl.gym_env", args.args)
        return
    if args.command == "determinism-check":
        _dispatch("clasher.rl.determinism_check", args.args)
        return
    if args.command == "benchmark":
        _dispatch("clasher.rl.benchmark", args.args)
        return
    if args.command == "strategy-benchmark":
        _dispatch("clasher.rl.strategy_benchmark", args.args)
        return
    if args.command == "replay-validate":
        _dispatch("clasher.rl.replay_validation", args.args)
        return
    if args.command == "latest-checkpoint":
        checkpoint = latest_checkpoint(args.checkpoint_dir, pattern=args.pattern)
        if checkpoint is None:
            raise FileNotFoundError(
                f"no checkpoints matching {args.pattern!r} in {checkpoints_dir(args.checkpoint_dir)}"
            )
        print(checkpoint)
        return
    if args.command == "paths":
        print(f"project_root={project_root()}")
        print(f"gamedata={gamedata_path(args.gamedata_path)}")
        print(f"decks={decks_path(args.decks_path)}")
        print(f"checkpoint_dir={checkpoints_dir(args.checkpoint_dir)}")
        return

    raise RuntimeError(f"unknown command: {args.command}")


if __name__ == "__main__":
    main()
