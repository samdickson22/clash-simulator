from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import time
from pathlib import Path

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.paths import decks_path as resolve_decks_path
from clasher.paths import latest_checkpoint, resolve_path
from clasher.rl.train_selfplay import resolve_torch_device
from clasher.rl.model import MaskedPolicyValueNet
from clasher.rl.selfplay_env import SelfPlayBattleEnv


class _NullWriter:
    def write(self, _value):
        return 0

    def flush(self):
        return None


_NULL_WRITER = _NullWriter()


@contextmanager
def maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return
    with redirect_stdout(_NULL_WRITER), redirect_stderr(_NULL_WRITER):
        yield


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate self-play checkpoint")
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints/selfplay_run")
    parser.add_argument("--opponent-checkpoint", type=str, default=None)
    parser.add_argument("--opponent-checkpoint-dir", type=str, default="checkpoints/selfplay_async")
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--opponent", type=str, choices=["random", "noop", "policy"], default="random")
    parser.add_argument("--quiet-engine", action="store_true")
    return parser.parse_args()


def load_model(checkpoint_path: Path, device: torch.device) -> tuple[MaskedPolicyValueNet, dict]:
    state = torch.load(checkpoint_path, map_location=device)
    model = MaskedPolicyValueNet(
        board_channels=state["board_channels"],
        hud_size=state["hud_size"],
        num_actions=state["num_actions"],
        hidden_size=state.get("args", {}).get("hidden_size", 256),
        recurrent=False,
    ).to(device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    return model, state


def select_opponent_action(
    env: SelfPlayBattleEnv,
    mode: str,
    rng: np.random.Generator,
    opponent_model: MaskedPolicyValueNet | None,
    device: torch.device,
    deterministic: bool,
) -> int:
    if mode == "noop":
        return env.action_space.no_op_action
    if mode == "policy":
        if opponent_model is None:
            raise ValueError("opponent_model is required when --opponent=policy")
        obs = env.get_observation(1)
        mask = env.get_action_mask(1)
        board = torch.tensor(obs.board, dtype=torch.float32, device=device).unsqueeze(0)
        hud = torch.tensor(obs.hud, dtype=torch.float32, device=device).unsqueeze(0)
        action_mask = torch.tensor(mask, dtype=torch.bool, device=device).unsqueeze(0)
        with torch.no_grad():
            action_t, _, _, _ = opponent_model.act(
                board=board,
                hud=hud,
                action_mask=action_mask,
                deterministic=deterministic,
            )
        return int(action_t.item())
    return env.action_space.random_legal_action(env.battle, 1, rng)


def run_eval(args: argparse.Namespace) -> None:
    device = resolve_torch_device(args.device)
    print(f"device={device}")

    if args.checkpoint:
        checkpoint_path = resolve_path(args.checkpoint, must_exist=True)
    else:
        checkpoint_path = latest_checkpoint(args.checkpoint_dir)
        if checkpoint_path is None:
            raise FileNotFoundError(
                f"no policy checkpoints found in {resolve_path(args.checkpoint_dir, must_exist=False)}"
            )
    resolved_decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    print(f"checkpoint={checkpoint_path}")
    print(f"decks={resolved_decks_path}")

    model, _ = load_model(checkpoint_path, device=device)
    opponent_model: MaskedPolicyValueNet | None = None
    opponent_checkpoint_path: Path | None = None
    if args.opponent == "policy":
        if args.opponent_checkpoint:
            opponent_checkpoint_path = resolve_path(args.opponent_checkpoint, must_exist=True)
        else:
            opponent_checkpoint_path = latest_checkpoint(args.opponent_checkpoint_dir)
            if opponent_checkpoint_path is None:
                raise FileNotFoundError(
                    "no opponent policy checkpoints found in "
                    f"{resolve_path(args.opponent_checkpoint_dir, must_exist=False)}"
                )
        opponent_model, _ = load_model(opponent_checkpoint_path, device=device)
        print(f"opponent_checkpoint={opponent_checkpoint_path}")

    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=str(resolved_decks_path),
        seed=args.seed,
        mirror_match=False,
        canonical_perspective=True,
    )
    rng = np.random.default_rng(args.seed)

    wins = 0
    losses = 0
    draws = 0
    ticks_total = 0

    start = time.time()
    for _ in range(args.games):
        with maybe_silence_stdio(args.quiet_engine):
            env.reset()

            done = False
            while not done:
                obs = env.get_observation(0)
                mask = env.get_action_mask(0)
                board = torch.tensor(obs.board, dtype=torch.float32, device=device).unsqueeze(0)
                hud = torch.tensor(obs.hud, dtype=torch.float32, device=device).unsqueeze(0)
                action_mask = torch.tensor(mask, dtype=torch.bool, device=device).unsqueeze(0)

                with torch.no_grad():
                    action_t, _, _, _ = model.act(
                        board=board,
                        hud=hud,
                        action_mask=action_mask,
                        deterministic=args.deterministic,
                    )
                action0 = int(action_t.item())
                action1 = select_opponent_action(
                    env=env,
                    mode=args.opponent,
                    rng=rng,
                    opponent_model=opponent_model,
                    device=device,
                    deterministic=args.deterministic,
                )

                _, done, _ = env.step({0: action0, 1: action1})

        ticks_total += env.battle.tick
        if env.battle.winner is None:
            draws += 1
        elif env.battle.winner == 0:
            wins += 1
        else:
            losses += 1

    elapsed = time.time() - start
    games_per_min = (args.games / elapsed) * 60.0 if elapsed > 0 else 0.0
    avg_ticks = ticks_total / max(1, args.games)
    win_rate = wins / max(1, args.games)

    print(f"games={args.games}")
    print(f"wins={wins} losses={losses} draws={draws}")
    print(f"win_rate={win_rate:.3f}")
    print(f"avg_ticks={avg_ticks:.1f}")
    print(f"elapsed_sec={elapsed:.3f}")
    print(f"games_per_min={games_per_min:.3f}")


def main() -> None:
    run_eval(parse_args())


if __name__ == "__main__":
    main()
