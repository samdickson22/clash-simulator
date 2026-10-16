from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path

from .eval import evaluate, load_policy_checkpoint
from .reward_model import OBJECTIVE_V1, REWARD_PROFILES
from .strategy_bots import STRATEGY_NAMES, StrategyBot, pfsp_weights
from .train_recurrent import find_latest_checkpoint, resolve_torch_device


def build_benchmark_report(
    *,
    checkpoint: Path,
    checkpoint_update: int,
    seed: int,
    games_per_opponent: int,
    reward_profile: str,
    results: dict[str, dict[str, float]],
    checkpoint_sha256: str | None = None,
    sampling_decks_path: Path | None = None,
    sampling_decks_sha256: str | None = None,
    candidate_sampling_decks_path: Path | None = None,
    candidate_sampling_decks_sha256: str | None = None,
    opponent_sampling_decks_path: Path | None = None,
    opponent_sampling_decks_sha256: str | None = None,
) -> dict[str, Any]:
    score_rates = {
        name: float(metrics["score_rate"]) for name, metrics in results.items()
    }
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": checkpoint_sha256,
            "update": int(checkpoint_update),
        },
        "protocol": {
            "paired_seats": True,
            "seed": int(seed),
            "games_per_opponent": int(games_per_opponent),
            "reward_profile": reward_profile,
            "opponents": list(STRATEGY_NAMES),
            "public_information_only": True,
            "sampling_decks_path": (
                str(sampling_decks_path) if sampling_decks_path is not None else None
            ),
            "sampling_decks_sha256": sampling_decks_sha256,
            "candidate_sampling_decks_path": (
                str(candidate_sampling_decks_path)
                if candidate_sampling_decks_path is not None
                else None
            ),
            "candidate_sampling_decks_sha256": candidate_sampling_decks_sha256,
            "opponent_sampling_decks_path": (
                str(opponent_sampling_decks_path)
                if opponent_sampling_decks_path is not None
                else None
            ),
            "opponent_sampling_decks_sha256": opponent_sampling_decks_sha256,
        },
        "results": results,
        "summary": {
            "mean_score_rate": sum(score_rates.values()) / len(score_rates),
            "worst_score_rate": min(score_rates.values()),
            "worst_opponent": min(score_rates, key=lambda name: score_rates[name]),
        },
        "pfsp": {
            "formula": "max(floor, (1 - score_rate) ** power)",
            "power": 2.0,
            "floor": 0.02,
            "weights": pfsp_weights(score_rates, power=2.0, floor=0.02),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    candidate = report["candidate"]
    protocol = report["protocol"]
    lines = [
        f"# Strategy benchmark: update {candidate['update']}",
        "",
        f"Checkpoint: `{candidate['checkpoint']}`",
        "",
        (
            f"Protocol: {protocol['games_per_opponent']} paired-seat games per "
            f"opponent, seed {protocol['seed']}, reward profile "
            f"`{protocol['reward_profile']}`. Opponents use public information only."
        ),
        "",
        "| Opponent | W-L-D | Score | Crown diff | Incoming danger | Defense action rate | PFSP weight |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    weights = report["pfsp"]["weights"]
    for name in STRATEGY_NAMES:
        metrics = report["results"][name]
        lines.append(
            f"| {name} | {int(metrics['wins'])}-{int(metrics['losses'])}-{int(metrics['draws'])} "
            f"| {metrics['score_rate']:.3f} | {metrics['crown_diff_per_game']:+.3f} "
            f"| {metrics['incoming_tower_danger_mean']:.4f} "
            f"| {metrics['defensive_action_rate_when_threatened']:.3f} "
            f"| {weights[name]:.3f} |"
        )
    summary = report["summary"]
    lines.extend(
        [
            "",
            (
                f"Mean score: **{summary['mean_score_rate']:.3f}**. Worst matchup: "
                f"**{summary['worst_opponent']}** at **{summary['worst_score_rate']:.3f}**."
            ),
            "",
            "The PFSP weights are inputs for a subsequent training phase, not promotion evidence by themselves.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a V2 policy against the public-information strategy roster"
    )
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--checkpoint-dir", default="checkpoints/entity_selfplay")
    parser.add_argument("--decks-path", default="decks.json")
    parser.add_argument(
        "--sampling-decks-path",
        default=None,
        help="optional matchup deck pool while --decks-path retains the vocabulary",
    )
    parser.add_argument("--candidate-sampling-decks-path", default=None)
    parser.add_argument("--opponent-sampling-decks-path", default=None)
    parser.add_argument("--games-per-opponent", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7301)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument(
        "--device", choices=["auto", "cpu", "mps", "cuda"], default="auto"
    )
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=OBJECTIVE_V1
    )
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", default=None)
    parser.add_argument("--stochastic", dest="deterministic", action="store_false")
    parser.add_argument(
        "--quiet-engine", dest="quiet_engine", action="store_true", default=True
    )
    parser.add_argument("--no-quiet-engine", dest="quiet_engine", action="store_false")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.games_per_opponent <= 0 or args.games_per_opponent % 2:
        raise ValueError("--games-per-opponent must be a positive even number")
    device = resolve_torch_device(args.device)
    decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    sampling_decks_path = (
        resolve_decks_path(args.sampling_decks_path, must_exist=True)
        if args.sampling_decks_path
        else None
    )
    candidate_sampling_decks_path = (
        resolve_decks_path(args.candidate_sampling_decks_path, must_exist=True)
        if args.candidate_sampling_decks_path
        else None
    )
    opponent_sampling_decks_path = (
        resolve_decks_path(args.opponent_sampling_decks_path, must_exist=True)
        if args.opponent_sampling_decks_path
        else None
    )
    if args.checkpoint:
        checkpoint = resolve_path(args.checkpoint, must_exist=True)
    else:
        directory = resolve_path(args.checkpoint_dir, must_exist=True)
        latest_checkpoint = find_latest_checkpoint(directory)
        if latest_checkpoint is None:
            raise FileNotFoundError(f"no V2 checkpoints in {directory}")
        checkpoint = latest_checkpoint
    candidate = load_policy_checkpoint(checkpoint, device=device, decks_path=decks_path)
    results: dict[str, dict[str, float]] = {}
    for index, name in enumerate(STRATEGY_NAMES):
        print(f"evaluating_strategy={name}", flush=True)
        results[name] = evaluate(
            candidate=candidate,
            decks_path=decks_path,
            games=args.games_per_opponent,
            seed=args.seed + index * 100_003,
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            opponent_mode="strategy",
            opponent=None,
            deterministic=args.deterministic,
            quiet_engine=args.quiet_engine,
            device=device,
            reward_profile=args.reward_profile,
            sampling_decks_path=sampling_decks_path,
            candidate_sampling_decks_path=candidate_sampling_decks_path,
            opponent_sampling_decks_path=opponent_sampling_decks_path,
            opponent_bot=StrategyBot(name),
        )
    report = build_benchmark_report(
        checkpoint=checkpoint,
        checkpoint_update=int(candidate.checkpoint.get("update", 0)),
        seed=args.seed,
        games_per_opponent=args.games_per_opponent,
        reward_profile=args.reward_profile,
        results=results,
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        sampling_decks_path=sampling_decks_path,
        sampling_decks_sha256=(
            hashlib.sha256(sampling_decks_path.read_bytes()).hexdigest()
            if sampling_decks_path is not None
            else None
        ),
        candidate_sampling_decks_path=candidate_sampling_decks_path,
        candidate_sampling_decks_sha256=(
            hashlib.sha256(candidate_sampling_decks_path.read_bytes()).hexdigest()
            if candidate_sampling_decks_path is not None
            else None
        ),
        opponent_sampling_decks_path=opponent_sampling_decks_path,
        opponent_sampling_decks_sha256=(
            hashlib.sha256(opponent_sampling_decks_path.read_bytes()).hexdigest()
            if opponent_sampling_decks_path is not None
            else None
        ),
    )
    json_path = Path(args.json_out).expanduser().resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"json_out={json_path}")
    if args.markdown_out:
        markdown_path = Path(args.markdown_out).expanduser().resolve()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"markdown_out={markdown_path}")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
