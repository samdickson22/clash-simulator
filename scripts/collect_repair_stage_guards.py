from __future__ import annotations

import argparse
import glob
import hashlib
import re
from pathlib import Path
from typing import cast

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import resolve_path
from clasher.rl.eval import LoadedPolicy, load_policy_checkpoint
from clasher.rl.model import PrototypeRepairAdapter
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_recurrent import _stack_step_inputs, maybe_silence_stdio

_TARGET_PATTERN = re.compile(r"seed(?P<seed>\d+)_p(?P<seat>[01])")


@torch.no_grad()
def _policy_step(
    policy: LoadedPolicy,
    env: SelfPlayBattleEnv,
    player_id: int,
    *,
    state: tuple[torch.Tensor, torch.Tensor],
    previous_action: int,
    previous_reward: float,
    episode_start: bool,
) -> tuple[
    int,
    tuple[torch.Tensor, torch.Tensor],
    np.ndarray,
    torch.Tensor,
]:
    assert env.battle is not None
    observation = policy.builder.build(env.battle, player_id)
    mask = env.get_action_mask(player_id)[None, :]
    inputs = _stack_step_inputs(
        [observation],
        mask,
        np.asarray([previous_action], dtype=np.int64),
        np.asarray([previous_reward], dtype=np.float32),
        np.asarray([episode_start], dtype=np.bool_),
        torch.device("cpu"),
    )
    action, _, _, next_state, output = policy.model.act(
        inputs,
        state,
        deterministic=True,
    )
    assert output.repair_features is not None
    return (
        int(action[0, 0].item()),
        next_state,
        mask[0],
        output.repair_features[0, 0].detach().cpu(),
    )


def _target_pairs(
    patterns: list[str],
    explicit_pairs: list[str],
) -> list[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for pattern in patterns:
        for raw_path in glob.glob(pattern):
            match = _TARGET_PATTERN.search(Path(raw_path).name)
            if match is None:
                continue
            pairs.add((int(match.group("seed")), int(match.group("seat"))))
    for raw_pair in explicit_pairs:
        seed_text, separator, seat_text = raw_pair.partition(":")
        if not separator or seat_text not in {"0", "1"}:
            raise ValueError(f"invalid target pair {raw_pair!r}; expected SEED:SEAT")
        pairs.add((int(seed_text), int(seat_text)))
    if not pairs:
        raise ValueError("target globs matched no seed/player pairs")
    return sorted(pairs)


def _capture_ticks(raw_points: list[str]) -> dict[tuple[int, int], set[int]]:
    points: dict[tuple[int, int], set[int]] = {}
    for raw_point in raw_points:
        parts = raw_point.split(":")
        if len(parts) != 3 or parts[1] not in {"0", "1"}:
            raise ValueError(
                f"invalid capture point {raw_point!r}; expected SEED:SEAT:TICK"
            )
        seed, seat, tick = (int(part) for part in parts)
        points.setdefault((seed, seat), set()).add(tick)
    return points


def _feature_digest(features: torch.Tensor) -> str:
    return hashlib.sha256(features.numpy().tobytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Collect exact guard states where a broad donor repair stage would "
            "activate along retained-policy target trajectories."
        )
    )
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--targets-glob", action="append", default=[])
    parser.add_argument("--target-pair", action="append", default=[])
    parser.add_argument("--existing-guards", type=Path, action="append", default=[])
    parser.add_argument(
        "--capture-point",
        action="append",
        default=[],
        help=(
            "capture only an exact retained-policy state as SEED:SEAT:TICK; "
            "repeatable"
        ),
    )
    parser.add_argument("--donor-stage-index", type=int, default=None)
    parser.add_argument("--require-wins", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decks", type=Path, default=Path("decks.json"))
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    args = parser.parse_args()

    torch.set_num_threads(2)
    target_path = resolve_path(args.target, must_exist=True)
    donor_path = resolve_path(args.donor, must_exist=True)
    decks_path = resolve_decks_path(args.decks, must_exist=True)
    target = load_policy_checkpoint(
        target_path,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    donor = load_policy_checkpoint(
        donor_path,
        device=torch.device("cpu"),
        decks_path=decks_path,
    )
    donor_stage_count = len(donor.model.repair_stages)
    donor_stage_index = args.donor_stage_index
    if donor_stage_index is None:
        if donor_stage_count != 1:
            raise ValueError(
                "donor checkpoint contains multiple repair stages; "
                "select one with --donor-stage-index"
            )
        donor_stage_index = 0
    if not 0 <= donor_stage_index < donor_stage_count:
        raise ValueError("donor stage index is out of range")
    broad_adapter = cast(
        PrototypeRepairAdapter,
        donor.model.repair_stage_prototype_adapters[str(donor_stage_index)],
    )
    capture_ticks = _capture_ticks(args.capture_point)
    explicit_pairs = [*args.target_pair]
    explicit_pairs.extend(f"{seed}:{seat}" for seed, seat in capture_ticks)
    pairs = _target_pairs(args.targets_glob, explicit_pairs)
    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=decks_path,
        seed=pairs[0][0],
        mirror_match=False,
        canonical_perspective=True,
        reward_profile="defense-v2",
    )
    guards: list[torch.Tensor] = []
    seen: set[str] = set()
    existing_guard_count = 0
    for existing_path in args.existing_guards:
        existing_payload = torch.load(
            resolve_path(existing_path, must_exist=True),
            map_location="cpu",
            weights_only=False,
        )
        for repair_features in torch.as_tensor(
            existing_payload["repair_features"]
        ).float():
            digest = _feature_digest(repair_features)
            if digest not in seen:
                seen.add(digest)
                guards.append(repair_features)
                existing_guard_count += 1
    active_decisions = total_decisions = wins = 0

    for seed, candidate_player in pairs:
        with maybe_silence_stdio(True):
            env.reset(seed=seed)
        rng = np.random.default_rng(seed + 91_117)
        torch.manual_seed(seed + 271_828)
        other_player = 1 - candidate_player
        state = target.model.initial_state(1, device=torch.device("cpu"))
        previous_action = env.action_space.no_op_action
        previous_reward = 0.0
        episode_start = True
        done = False
        while not done:
            action, state, mask, repair_features = _policy_step(
                target,
                env,
                candidate_player,
                state=state,
                previous_action=previous_action,
                previous_reward=previous_reward,
                episode_start=episode_start,
            )
            weights = broad_adapter.activation_weights(repair_features[None, :])
            total_decisions += 1
            assert env.battle is not None
            tick = env.battle.tick
            capture_this_state = (
                not capture_ticks or tick in capture_ticks.get((seed, candidate_player), ())
            )
            if bool(weights.amax().item() > 0.0):
                active_decisions += 1
                if capture_this_state:
                    digest = _feature_digest(repair_features)
                    if digest not in seen:
                        seen.add(digest)
                        guards.append(repair_features)
            other_mask = env.get_action_mask(other_player)
            legal = np.flatnonzero(other_mask)
            other_action = (
                int(rng.choice(legal))
                if legal.size
                else env.action_space.no_op_action
            )
            with maybe_silence_stdio(True):
                rewards, done, _ = env.step(
                    {candidate_player: action, other_player: other_action},
                    pre_action_masks={
                        candidate_player: mask,
                        other_player: other_mask,
                    },
                )
            previous_action = action
            previous_reward = float(rewards[candidate_player])
            episode_start = False
        assert env.battle is not None
        wins += int(env.battle.winner == candidate_player)

    if args.require_wins and wins != len(pairs):
        raise RuntimeError(
            f"target checkpoint won only {wins}/{len(pairs)} guarded trajectories"
        )
    if not guards:
        raise RuntimeError("broad donor never activated on target trajectories")
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    torch.save(
        {
            "repair_features": torch.stack(guards),
            "target_checkpoint": str(target_path),
            "donor_checkpoint": str(donor_path),
            "target_pairs": pairs,
            "total_decisions": total_decisions,
            "active_decisions": active_decisions,
            "existing_guard_count": existing_guard_count,
            "capture_ticks": capture_ticks,
            "donor_stage_index": donor_stage_index,
        },
        temporary_path,
    )
    temporary_path.replace(output_path)
    print(f"saved={output_path}")
    print(f"targets={len(pairs)} wins={wins}")
    print(
        f"decisions={total_decisions} active={active_decisions} "
        f"existing_guards={existing_guard_count} unique_guards={len(guards)}"
    )


if __name__ == "__main__":
    main()
