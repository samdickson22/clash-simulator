from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import io
from pathlib import Path
import time
from typing import Dict, Optional

import numpy as np
import torch
from torch import nn

from clasher.paths import checkpoints_dir, decks_path as resolve_decks_path, resolve_path
from clasher.rl.model import MaskedPolicyValueNet
from clasher.rl.oracle_planner import FixedDepthThompsonOracle
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_selfplay import resolve_torch_device


@contextmanager
def maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return
    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


@dataclass
class DaggerReplayBuffer:
    capacity: int
    boards: list[np.ndarray] = field(default_factory=list)
    huds: list[np.ndarray] = field(default_factory=list)
    masks: list[np.ndarray] = field(default_factory=list)
    actions: list[int] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.actions)

    def add(self, board: np.ndarray, hud: np.ndarray, mask: np.ndarray, action: int) -> None:
        self.boards.append(board.astype(np.float32, copy=True))
        self.huds.append(hud.astype(np.float32, copy=True))
        self.masks.append(mask.astype(np.bool_, copy=True))
        self.actions.append(int(action))
        over = len(self.actions) - self.capacity
        if over > 0:
            del self.boards[:over]
            del self.huds[:over]
            del self.masks[:over]
            del self.actions[:over]

    def sample_batch(self, rng: np.random.Generator, batch_size: int) -> Dict[str, np.ndarray]:
        n = len(self.actions)
        if n == 0:
            raise ValueError("replay buffer is empty")
        idx = rng.integers(0, n, size=min(batch_size, n))
        return {
            "boards": np.stack([self.boards[i] for i in idx], axis=0),
            "huds": np.stack([self.huds[i] for i in idx], axis=0),
            "masks": np.stack([self.masks[i] for i in idx], axis=0),
            "actions": np.asarray([self.actions[i] for i in idx], dtype=np.int64),
        }


def _find_latest_checkpoint(checkpoint_dir: Path) -> Optional[Path]:
    candidates = sorted(checkpoint_dir.glob("policy_dagger_iter_*.pt"))
    if not candidates:
        return None
    return candidates[-1]


def _supervised_update(
    model: MaskedPolicyValueNet,
    optimizer: torch.optim.Optimizer,
    replay: DaggerReplayBuffer,
    rng: np.random.Generator,
    device: torch.device,
    *,
    epochs: int,
    batch_size: int,
    steps_per_epoch: int,
) -> Dict[str, float]:
    model.train()
    loss_sum = 0.0
    acc_sum = 0.0
    entropy_sum = 0.0
    steps = 0
    for _ in range(epochs):
        for _ in range(steps_per_epoch):
            batch = replay.sample_batch(rng, batch_size=batch_size)
            boards = torch.as_tensor(batch["boards"], dtype=torch.float32, device=device)
            huds = torch.as_tensor(batch["huds"], dtype=torch.float32, device=device)
            masks = torch.as_tensor(batch["masks"], dtype=torch.bool, device=device)
            actions = torch.as_tensor(batch["actions"], dtype=torch.long, device=device)

            logits, _, _ = model(boards, huds)
            masked_logits = logits.masked_fill(~masks, -1e9)
            loss = nn.functional.cross_entropy(masked_logits, actions)

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.5)
            optimizer.step()

            with torch.no_grad():
                pred = torch.argmax(masked_logits, dim=-1)
                acc = (pred == actions).float().mean().item()
                dist = torch.distributions.Categorical(logits=masked_logits)
                entropy = dist.entropy().mean().item()

            loss_sum += float(loss.item())
            acc_sum += float(acc)
            entropy_sum += float(entropy)
            steps += 1

    if steps == 0:
        return {"loss": 0.0, "acc": 0.0, "entropy": 0.0}
    return {
        "loss": loss_sum / steps,
        "acc": acc_sum / steps,
        "entropy": entropy_sum / steps,
    }


def _collect_dagger_data(
    env: SelfPlayBattleEnv,
    planner: FixedDepthThompsonOracle,
    model: MaskedPolicyValueNet,
    replay: DaggerReplayBuffer,
    rng: np.random.Generator,
    device: torch.device,
    *,
    decisions: int,
    beta: float,
    quiet_engine: bool,
) -> Dict[str, float]:
    if env.battle is None:
        with maybe_silence_stdio(quiet_engine):
            env.reset()

    model.eval()
    done_count = 0
    oracle_exec = 0
    student_exec = 0

    for _ in range(decisions):
        assert env.battle is not None
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)

        with maybe_silence_stdio(quiet_engine):
            oracle_actions = planner.select_actions(env.battle)
        replay.add(obs0.board, obs0.hud, mask0, int(oracle_actions[0]))
        replay.add(obs1.board, obs1.hud, mask1, int(oracle_actions[1]))

        board_t = torch.as_tensor(np.stack([obs0.board, obs1.board]), dtype=torch.float32, device=device)
        hud_t = torch.as_tensor(np.stack([obs0.hud, obs1.hud]), dtype=torch.float32, device=device)
        mask_t = torch.as_tensor(np.stack([mask0, mask1]), dtype=torch.bool, device=device)
        with torch.no_grad():
            student_actions_t, _, _, _ = model.act(
                board=board_t,
                hud=hud_t,
                action_mask=mask_t,
                deterministic=False,
            )
        student_actions = student_actions_t.detach().cpu().numpy().astype(np.int64)

        executed: Dict[int, int] = {}
        for player_id in (0, 1):
            if float(rng.random()) < beta:
                executed[player_id] = int(oracle_actions[player_id])
                oracle_exec += 1
            else:
                executed[player_id] = int(student_actions[player_id])
                student_exec += 1

        with maybe_silence_stdio(quiet_engine):
            _, done, _ = env.step(executed)
            if done:
                done_count += 1
                env.reset()

    total_exec = max(1, oracle_exec + student_exec)
    return {
        "episodes_finished": float(done_count),
        "oracle_exec_ratio": float(oracle_exec) / total_exec,
        "student_exec_ratio": float(student_exec) / total_exec,
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train policy with DAgger from an FDTS oracle planner")
    p.add_argument("--decks-path", type=str, default="decks.json")
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--iterations", type=int, default=300)
    p.add_argument("--decisions-per-iter", type=int, default=1024)
    p.add_argument("--decision-interval", type=int, default=8)
    p.add_argument("--max-ticks", type=int, default=9090)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--batch-size", type=int, default=1024)
    p.add_argument("--steps-per-epoch", type=int, default=4)
    p.add_argument("--hidden-size", type=int, default=256)
    p.add_argument("--replay-capacity", type=int, default=200_000)
    p.add_argument("--checkpoint-dir", type=str, default="checkpoints/dagger_oracle")
    p.add_argument("--save-every", type=int, default=20)
    p.add_argument("--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto")
    p.add_argument("--quiet-engine", action="store_true")
    p.add_argument("--mirror-match", action="store_true")
    p.add_argument("--resume-latest", action="store_true")
    p.add_argument("--resume-from", type=str, default=None)
    p.add_argument("--planner-depth", type=int, default=10)
    p.add_argument("--planner-sims", type=int, default=48)
    p.add_argument("--planner-action-samples", type=int, default=96)
    p.add_argument("--beta-start", type=float, default=1.0)
    p.add_argument("--beta-end", type=float, default=0.05)
    return p.parse_args()


def _beta_for_iter(iteration: int, total_iters: int, beta_start: float, beta_end: float) -> float:
    if total_iters <= 1:
        return float(beta_start)
    frac = float(iteration - 1) / float(total_iters - 1)
    return float(beta_start + frac * (beta_end - beta_start))


def main() -> None:
    args = _parse_args()
    if args.resume_latest and args.resume_from:
        raise ValueError("Use only one of --resume-latest or --resume-from")

    rng = np.random.default_rng(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = resolve_torch_device(args.device)
    print(f"device={device}")
    resolved_decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint_dir = checkpoints_dir(args.checkpoint_dir, create=True)
    args.decks_path = str(resolved_decks_path)
    args.checkpoint_dir = str(checkpoint_dir)
    print(f"decks_path={resolved_decks_path}")
    print(f"checkpoint_dir={checkpoint_dir}")

    env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=str(resolved_decks_path),
        seed=args.seed,
        mirror_match=args.mirror_match,
        canonical_perspective=True,
    )
    with maybe_silence_stdio(args.quiet_engine):
        env.reset()
    obs0 = env.get_observation(0)
    action_space = env.action_space

    model = MaskedPolicyValueNet(
        board_channels=obs0.board.shape[0],
        hud_size=obs0.hud.shape[0],
        num_actions=action_space.num_actions,
        hidden_size=args.hidden_size,
        recurrent=False,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    start_iter = 1
    resume_ckpt: Optional[Path] = None
    if args.resume_from:
        resume_ckpt = resolve_path(args.resume_from, must_exist=True)
    elif args.resume_latest:
        resume_ckpt = _find_latest_checkpoint(checkpoint_dir)
    if resume_ckpt is not None:
        state = torch.load(resume_ckpt, map_location=device)
        model.load_state_dict(state["model_state_dict"])
        if "optimizer_state_dict" in state:
            optimizer.load_state_dict(state["optimizer_state_dict"])
        saved_iter = int(state.get("iteration", 0))
        start_iter = saved_iter + 1
        print(f"resumed_from={resume_ckpt} saved_iter={saved_iter} start_iter={start_iter}")

    if start_iter > args.iterations:
        print(f"nothing_to_do start_iter={start_iter} > iterations={args.iterations}")
        return

    planner = FixedDepthThompsonOracle(
        action_space=action_space,
        decision_interval_ticks=args.decision_interval,
        plan_depth=args.planner_depth,
        num_simulations=args.planner_sims,
        rollout_action_samples=args.planner_action_samples,
        seed=args.seed + 1009,
    )
    replay = DaggerReplayBuffer(capacity=args.replay_capacity)

    for iteration in range(start_iter, args.iterations + 1):
        beta = _beta_for_iter(
            iteration=iteration,
            total_iters=args.iterations,
            beta_start=args.beta_start,
            beta_end=args.beta_end,
        )
        collect_start = time.perf_counter()
        collect_stats = _collect_dagger_data(
            env=env,
            planner=planner,
            model=model,
            replay=replay,
            rng=rng,
            device=device,
            decisions=args.decisions_per_iter,
            beta=beta,
            quiet_engine=args.quiet_engine,
        )
        collect_s = time.perf_counter() - collect_start

        update_start = time.perf_counter()
        update_stats = _supervised_update(
            model=model,
            optimizer=optimizer,
            replay=replay,
            rng=rng,
            device=device,
            epochs=args.epochs,
            batch_size=args.batch_size,
            steps_per_epoch=args.steps_per_epoch,
        )
        update_s = time.perf_counter() - update_start

        print(
            f"iter={iteration:04d} "
            f"beta={beta:.3f} "
            f"replay={len(replay)} "
            f"loss={update_stats['loss']:.4f} "
            f"acc={update_stats['acc']:.4f} "
            f"entropy={update_stats['entropy']:.4f} "
            f"collect_s={collect_s:.2f} "
            f"update_s={update_s:.2f} "
            f"episodes={collect_stats['episodes_finished']:.0f} "
            f"oracle_exec={collect_stats['oracle_exec_ratio']:.3f} "
            f"student_exec={collect_stats['student_exec_ratio']:.3f}"
        )

        if iteration % args.save_every == 0 or iteration == args.iterations:
            ckpt_path = checkpoint_dir / f"policy_dagger_iter_{iteration:04d}.pt"
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "args": vars(args),
                    "iteration": iteration,
                    "board_channels": obs0.board.shape[0],
                    "hud_size": obs0.hud.shape[0],
                    "num_actions": action_space.num_actions,
                },
                ckpt_path,
            )
            print(f"saved_checkpoint={ckpt_path}")


if __name__ == "__main__":
    main()
