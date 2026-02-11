from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch
from torch import nn

from clasher.rl.model import MaskedPolicyValueNet
from clasher.rl.selfplay_env import SelfPlayBattleEnv


@dataclass
class Transition:
    player_id: int
    board: np.ndarray
    hud: np.ndarray
    action_mask: np.ndarray
    action: int
    old_log_prob: float
    value: float
    reward: float
    done: bool
    next_value: float


@contextmanager
def maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def tensorize_obs(obs, device: torch.device):
    board = torch.tensor(obs.board, dtype=torch.float32, device=device).unsqueeze(0)
    hud = torch.tensor(obs.hud, dtype=torch.float32, device=device).unsqueeze(0)
    return board, hud


def tensorize_mask(mask: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.tensor(mask, dtype=torch.bool, device=device).unsqueeze(0)


def collect_rollout(
    env: SelfPlayBattleEnv,
    model: MaskedPolicyValueNet,
    device: torch.device,
    rollout_steps: int,
    quiet_engine: bool,
) -> List[Transition]:
    model.eval()
    transitions: List[Transition] = []

    if env.battle is None:
        with maybe_silence_stdio(quiet_engine):
            env.reset()

    for _ in range(rollout_steps):
        step_data: Dict[int, Dict[str, object]] = {}
        actions: Dict[int, int] = {}

        for player_id in (0, 1):
            obs = env.get_observation(player_id)
            mask = env.get_action_mask(player_id)

            board_t, hud_t = tensorize_obs(obs, device)
            mask_t = tensorize_mask(mask, device)

            action_t, log_prob_t, value_t, _ = model.act(
                board_t,
                hud_t,
                mask_t,
                deterministic=False,
            )

            action = int(action_t.item())
            actions[player_id] = action
            step_data[player_id] = {
                "board": obs.board,
                "hud": obs.hud,
                "mask": mask,
                "action": action,
                "old_log_prob": float(log_prob_t.item()),
                "value": float(value_t.item()),
            }

        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(actions)

        for player_id in (0, 1):
            if done:
                next_value = 0.0
            else:
                next_obs = env.get_observation(player_id)
                next_mask = env.get_action_mask(player_id)
                with torch.no_grad():
                    next_board_t, next_hud_t = tensorize_obs(next_obs, device)
                    next_mask_t = tensorize_mask(next_mask, device)
                    logits, value, _ = model(next_board_t, next_hud_t)
                    dist = model.distribution(logits, next_mask_t)
                    _ = dist.entropy()  # force mask validation in debug scenarios
                    next_value = float(value.item())

            pdata = step_data[player_id]
            transitions.append(
                Transition(
                    player_id=player_id,
                    board=pdata["board"],
                    hud=pdata["hud"],
                    action_mask=pdata["mask"],
                    action=pdata["action"],
                    old_log_prob=pdata["old_log_prob"],
                    value=pdata["value"],
                    reward=float(rewards[player_id]),
                    done=done,
                    next_value=next_value,
                )
            )

        if done:
            with maybe_silence_stdio(quiet_engine):
                env.reset()

    return transitions


def compute_gae(
    transitions: List[Transition],
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    n = len(transitions)
    advantages = np.zeros(n, dtype=np.float32)
    returns = np.zeros(n, dtype=np.float32)

    for player_id in (0, 1):
        player_indices = [idx for idx, tr in enumerate(transitions) if tr.player_id == player_id]
        gae = 0.0
        for idx in reversed(player_indices):
            tr = transitions[idx]
            non_terminal = 0.0 if tr.done else 1.0
            delta = tr.reward + gamma * non_terminal * tr.next_value - tr.value
            gae = delta + gamma * gae_lambda * non_terminal * gae
            advantages[idx] = gae
            returns[idx] = gae + tr.value

    return advantages, returns


def ppo_update(
    model: MaskedPolicyValueNet,
    optimizer: torch.optim.Optimizer,
    transitions: List[Transition],
    advantages: np.ndarray,
    returns: np.ndarray,
    clip_ratio: float,
    value_coef: float,
    entropy_coef: float,
    epochs: int,
    batch_size: int,
    device: torch.device,
) -> Dict[str, float]:
    model.train()

    boards = torch.tensor(np.stack([t.board for t in transitions]), dtype=torch.float32, device=device)
    hud = torch.tensor(np.stack([t.hud for t in transitions]), dtype=torch.float32, device=device)
    action_masks = torch.tensor(np.stack([t.action_mask for t in transitions]), dtype=torch.bool, device=device)
    actions = torch.tensor([t.action for t in transitions], dtype=torch.long, device=device)
    old_log_probs = torch.tensor([t.old_log_prob for t in transitions], dtype=torch.float32, device=device)
    advantages_t = torch.tensor(advantages, dtype=torch.float32, device=device)
    returns_t = torch.tensor(returns, dtype=torch.float32, device=device)

    advantages_t = (advantages_t - advantages_t.mean()) / (advantages_t.std(unbiased=False) + 1e-8)

    stats = {
        "loss": 0.0,
        "policy_loss": 0.0,
        "value_loss": 0.0,
        "entropy": 0.0,
    }
    steps = 0

    n = boards.shape[0]
    for _ in range(epochs):
        perm = torch.randperm(n, device=device)
        for start in range(0, n, batch_size):
            mb = perm[start : start + batch_size]

            logits, values, _ = model(boards[mb], hud[mb])
            dist = model.distribution(logits, action_masks[mb])
            new_log_probs = dist.log_prob(actions[mb])
            entropy = dist.entropy().mean()

            ratio = torch.exp(new_log_probs - old_log_probs[mb])
            unclipped = ratio * advantages_t[mb]
            clipped = torch.clamp(ratio, 1.0 - clip_ratio, 1.0 + clip_ratio) * advantages_t[mb]
            policy_loss = -torch.min(unclipped, clipped).mean()

            value_loss = 0.5 * torch.mean((returns_t[mb] - values) ** 2)
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            optimizer.step()

            stats["loss"] += float(loss.item())
            stats["policy_loss"] += float(policy_loss.item())
            stats["value_loss"] += float(value_loss.item())
            stats["entropy"] += float(entropy.item())
            steps += 1

    if steps > 0:
        for key in stats:
            stats[key] /= steps
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a CV-equivalent self-play policy")
    parser.add_argument("--decks-path", type=str, default="decks.json")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--updates", type=int, default=200)
    parser.add_argument("--rollout-steps", type=int, default=256)
    parser.add_argument("--decision-interval", type=int, default=8)
    parser.add_argument("--max-ticks", type=int, default=9090)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--gamma", type=float, default=0.995)
    parser.add_argument("--gae-lambda", type=float, default=0.95)
    parser.add_argument("--clip-ratio", type=float, default=0.2)
    parser.add_argument("--entropy-coef", type=float, default=0.01)
    parser.add_argument("--value-coef", type=float, default=0.5)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--hidden-size", type=int, default=256)
    parser.add_argument("--save-every", type=int, default=20)
    parser.add_argument("--checkpoint-dir", type=str, default="checkpoints/selfplay")
    parser.add_argument("--mirror-match", action="store_true")
    parser.add_argument("--quiet-engine", action="store_true")
    parser.add_argument("--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto")
    return parser.parse_args()


def resolve_torch_device(device_arg: str) -> torch.device:
    if device_arg == "cpu":
        return torch.device("cpu")
    if device_arg == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")
        return torch.device("cuda")
    if device_arg == "mps":
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS requested but not available")
        return torch.device("mps")

    # auto: prefer MPS on Apple Silicon, then CUDA, then CPU.
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def main() -> None:
    args = parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = resolve_torch_device(args.device)
    print(f"device={device}")

    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=args.decks_path,
        seed=args.seed,
        mirror_match=args.mirror_match,
        canonical_perspective=True,
    )

    with maybe_silence_stdio(args.quiet_engine):
        env.reset()

    obs0 = env.get_observation(0)
    model = MaskedPolicyValueNet(
        board_channels=obs0.board.shape[0],
        hud_size=obs0.hud.shape[0],
        num_actions=env.action_space.num_actions,
        hidden_size=args.hidden_size,
        recurrent=False,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    for update in range(1, args.updates + 1):
        transitions = collect_rollout(
            env=env,
            model=model,
            device=device,
            rollout_steps=args.rollout_steps,
            quiet_engine=args.quiet_engine,
        )

        advantages, returns = compute_gae(
            transitions=transitions,
            gamma=args.gamma,
            gae_lambda=args.gae_lambda,
        )

        stats = ppo_update(
            model=model,
            optimizer=optimizer,
            transitions=transitions,
            advantages=advantages,
            returns=returns,
            clip_ratio=args.clip_ratio,
            value_coef=args.value_coef,
            entropy_coef=args.entropy_coef,
            epochs=args.epochs,
            batch_size=args.batch_size,
            device=device,
        )

        mean_reward = float(np.mean([t.reward for t in transitions]))
        print(
            f"update={update:04d} "
            f"mean_reward={mean_reward:+.4f} "
            f"loss={stats['loss']:.4f} "
            f"policy={stats['policy_loss']:.4f} "
            f"value={stats['value_loss']:.4f} "
            f"entropy={stats['entropy']:.4f}"
        )

        if update % args.save_every == 0 or update == args.updates:
            ckpt_path = checkpoint_dir / f"policy_update_{update:04d}.pt"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "args": vars(args),
                    "update": update,
                    "board_channels": obs0.board.shape[0],
                    "hud_size": obs0.hud.shape[0],
                    "num_actions": env.action_space.num_actions,
                },
                ckpt_path,
            )
            print(f"saved_checkpoint={ckpt_path}")


if __name__ == "__main__":
    main()
