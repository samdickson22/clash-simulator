from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.rl.reward_model import OBJECTIVE_V1, REWARD_PROFILES
from clasher.rl.selfplay_env import SelfPlayBattleEnv


@contextmanager
def _maybe_silence_stdio(enabled: bool) -> Iterator[None]:
    if not enabled:
        yield
        return
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


@dataclass(frozen=True)
class RolloutDigest:
    seed: int
    decisions: int
    episodes_finished: int
    sha256: str
    mask_shadow_checks: int
    mask_shadow_mismatches: int


def _hash_array(hasher: hashlib._Hash, arr: np.ndarray) -> None:
    contiguous = np.ascontiguousarray(arr)
    hasher.update(str(contiguous.dtype).encode("utf-8"))
    hasher.update(np.asarray(contiguous.shape, dtype=np.int64).tobytes())
    hasher.update(contiguous.tobytes())


def compute_rollout_digest(
    *,
    seed: int,
    decisions: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
    engine_fast_path: str = "off",
    reward_profile: str = OBJECTIVE_V1,
) -> RolloutDigest:
    random.seed(seed)
    np.random.seed(seed)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=decision_interval,
        max_ticks=max_ticks,
        decks_path=decks_path,
        seed=seed,
        mirror_match=mirror_match,
        canonical_perspective=True,
        engine_fast_path=engine_fast_path,
        reward_profile=reward_profile,
    )
    action_rng = np.random.default_rng(seed + 1_000_003)
    hasher = hashlib.sha256()
    episodes = 0

    with _maybe_silence_stdio(quiet_engine):
        env.reset()

    for _ in range(decisions):
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)

        legal0 = np.flatnonzero(mask0)
        legal1 = np.flatnonzero(mask1)
        action0 = (
            int(action_rng.choice(legal0))
            if legal0.size > 0
            else env.action_space.no_op_action
        )
        action1 = (
            int(action_rng.choice(legal1))
            if legal1.size > 0
            else env.action_space.no_op_action
        )

        with _maybe_silence_stdio(quiet_engine):
            rewards, done, info = env.step({0: action0, 1: action1})

        _hash_array(hasher, obs0.board)
        _hash_array(hasher, obs0.hud)
        _hash_array(hasher, obs1.board)
        _hash_array(hasher, obs1.hud)
        _hash_array(hasher, mask0)
        _hash_array(hasher, mask1)
        hasher.update(np.asarray([action0, action1], dtype=np.int64).tobytes())
        hasher.update(np.asarray([rewards[0], rewards[1]], dtype=np.float64).tobytes())
        hasher.update(np.asarray([done, info.ticks_advanced], dtype=np.int64).tobytes())
        winner = (
            -1
            if env.battle is None or env.battle.winner is None
            else int(env.battle.winner)
        )
        tick = 0 if env.battle is None else int(env.battle.tick)
        hasher.update(np.asarray([winner, tick], dtype=np.int64).tobytes())

        if done:
            episodes += 1
            with _maybe_silence_stdio(quiet_engine):
                env.reset()

    fast_metrics = env.fast_path_metrics()
    return RolloutDigest(
        seed=seed,
        decisions=decisions,
        episodes_finished=episodes,
        sha256=hasher.hexdigest(),
        mask_shadow_checks=int(fast_metrics["mask_shadow_checks"]),
        mask_shadow_mismatches=int(fast_metrics["mask_shadow_mismatches"]),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check deterministic simulator rollouts by hash"
    )
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--decisions", type=int, default=512)
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument("--quiet-engine", action="store_true")
    parser.add_argument(
        "--engine-fast-path", choices=["off", "shadow", "on"], default="off"
    )
    parser.add_argument(
        "--reward-profile", choices=REWARD_PROFILES, default=OBJECTIVE_V1
    )
    parser.add_argument(
        "--trials", type=int, default=2, help="number of repeated runs with same seed"
    )
    parser.add_argument("--json-out", type=str, default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    resolved_decks = resolve_decks_path(args.decks_path, must_exist=True)
    digests = [
        compute_rollout_digest(
            seed=args.seed,
            decisions=args.decisions,
            decks_path=str(resolved_decks),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            mirror_match=args.mirror_match,
            quiet_engine=args.quiet_engine,
            engine_fast_path=args.engine_fast_path,
            reward_profile=args.reward_profile,
        )
        for _ in range(max(1, args.trials))
    ]
    hashes = {d.sha256 for d in digests}
    deterministic = len(hashes) == 1
    print(
        f"deterministic={deterministic} seed={args.seed} decisions={args.decisions} "
        f"trials={len(digests)} hash={digests[0].sha256}"
    )
    for idx, d in enumerate(digests, start=1):
        print(
            f"trial={idx:02d} hash={d.sha256} "
            f"episodes_finished={d.episodes_finished} "
            f"mask_shadow_checks={d.mask_shadow_checks} "
            f"mask_shadow_mismatches={d.mask_shadow_mismatches}"
        )

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, object] = {
            "deterministic": deterministic,
            "seed": args.seed,
            "decisions": args.decisions,
            "engine_fast_path": args.engine_fast_path,
            "reward_profile": args.reward_profile,
            "trials": [d.__dict__ for d in digests],
        }
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote={out_path}")

    if not deterministic:
        raise RuntimeError(
            "Determinism check failed: repeated runs with same seed produced different hashes"
        )
    if any(d.mask_shadow_mismatches for d in digests):
        raise RuntimeError("Fast-path shadow action masks diverged")


if __name__ == "__main__":
    main()
