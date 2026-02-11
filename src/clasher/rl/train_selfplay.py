from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
from pathlib import Path
import time
from typing import Dict, List, Optional, Any, Tuple

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


@dataclass(frozen=True)
class RolloutWorkerTask:
    model_state_dict: Dict[str, torch.Tensor]
    board_channels: int
    hud_size: int
    num_actions: int
    hidden_size: int
    rollout_steps: int
    decision_interval_ticks: int
    max_ticks: int
    decks_path: str
    mirror_match: bool
    quiet_engine: bool
    seed: int


_WORKER_MODEL: Optional[MaskedPolicyValueNet] = None
_WORKER_ENV: Optional[SelfPlayBattleEnv] = None
_WORKER_CONFIG: Optional[Tuple[Any, ...]] = None
_WORKER_THREADS_SET: bool = False


@contextmanager
def maybe_silence_stdio(enabled: bool):
    if not enabled:
        yield
        return

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def tensorize_obs(obs, device: torch.device):
    board = torch.as_tensor(obs.board, dtype=torch.float32, device=device).unsqueeze(0)
    hud = torch.as_tensor(obs.hud, dtype=torch.float32, device=device).unsqueeze(0)
    return board, hud


def tensorize_mask(mask: np.ndarray, device: torch.device) -> torch.Tensor:
    return torch.as_tensor(mask, dtype=torch.bool, device=device).unsqueeze(0)


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
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)
        board_t = torch.as_tensor(
            np.stack([obs0.board, obs1.board]),
            dtype=torch.float32,
            device=device,
        )
        hud_t = torch.as_tensor(
            np.stack([obs0.hud, obs1.hud]),
            dtype=torch.float32,
            device=device,
        )
        mask_t = torch.as_tensor(
            np.stack([mask0, mask1]),
            dtype=torch.bool,
            device=device,
        )

        action_t, log_prob_t, value_t, _ = model.act(
            board_t,
            hud_t,
            mask_t,
            deterministic=False,
        )
        action_arr = action_t.detach().cpu().numpy()
        log_prob_arr = log_prob_t.detach().cpu().numpy()
        value_arr = value_t.detach().cpu().numpy()

        actions[0] = int(action_arr[0])
        actions[1] = int(action_arr[1])
        step_data[0] = {
            "board": obs0.board,
            "hud": obs0.hud,
            "mask": mask0,
            "action": actions[0],
            "old_log_prob": float(log_prob_arr[0]),
            "value": float(value_arr[0]),
        }
        step_data[1] = {
            "board": obs1.board,
            "hud": obs1.hud,
            "mask": mask1,
            "action": actions[1],
            "old_log_prob": float(log_prob_arr[1]),
            "value": float(value_arr[1]),
        }

        with maybe_silence_stdio(quiet_engine):
            rewards, done, _ = env.step(actions)

        for player_id in (0, 1):
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
                    next_value=0.0,
                )
            )

        if done:
            with maybe_silence_stdio(quiet_engine):
                env.reset()

    _fill_next_values(transitions, env=env, model=model, device=device)
    return transitions


def split_rollout_steps(total_steps: int, num_workers: int) -> List[int]:
    workers = max(1, num_workers)
    base = total_steps // workers
    remainder = total_steps % workers
    chunks: List[int] = []
    for idx in range(workers):
        chunk = base + (1 if idx < remainder else 0)
        if chunk > 0:
            chunks.append(chunk)
    return chunks


def _collect_rollout_worker(task: RolloutWorkerTask) -> List[Transition]:
    global _WORKER_MODEL, _WORKER_ENV, _WORKER_CONFIG, _WORKER_THREADS_SET
    # Rollout workers are intentionally CPU-only because env stepping and action
    # masking are CPU-bound in the current pipeline.
    torch_device = torch.device("cpu")
    if not _WORKER_THREADS_SET:
        # Avoid CPU thread oversubscription with many actor processes.
        torch.set_num_threads(1)
        _WORKER_THREADS_SET = True
    config = (
        task.board_channels,
        task.hud_size,
        task.num_actions,
        task.hidden_size,
        task.decision_interval_ticks,
        task.max_ticks,
        task.decks_path,
        task.mirror_match,
    )
    if _WORKER_MODEL is None or _WORKER_ENV is None or _WORKER_CONFIG != config:
        torch.manual_seed(task.seed)
        np.random.seed(task.seed)
        _WORKER_MODEL = MaskedPolicyValueNet(
            board_channels=task.board_channels,
            hud_size=task.hud_size,
            num_actions=task.num_actions,
            hidden_size=task.hidden_size,
            recurrent=False,
        ).to(torch_device)
        _WORKER_ENV = SelfPlayBattleEnv(
            decision_interval_ticks=task.decision_interval_ticks,
            max_ticks=task.max_ticks,
            decks_path=task.decks_path,
            seed=task.seed,
            mirror_match=task.mirror_match,
            canonical_perspective=True,
        )
        with maybe_silence_stdio(task.quiet_engine):
            _WORKER_ENV.reset()
        _WORKER_CONFIG = config

    model = _WORKER_MODEL
    env = _WORKER_ENV
    assert model is not None
    assert env is not None
    model.load_state_dict(task.model_state_dict)
    model.eval()
    return collect_rollout(
        env=env,
        model=model,
        device=torch_device,
        rollout_steps=task.rollout_steps,
        quiet_engine=task.quiet_engine,
    )


def collect_rollout_parallel(
    executor: ProcessPoolExecutor,
    model: MaskedPolicyValueNet,
    rollout_steps: int,
    num_workers: int,
    board_channels: int,
    hud_size: int,
    num_actions: int,
    hidden_size: int,
    decision_interval_ticks: int,
    max_ticks: int,
    decks_path: str,
    mirror_match: bool,
    quiet_engine: bool,
    seed: int,
    worker_retries: int,
) -> List[Transition]:
    chunks = split_rollout_steps(rollout_steps, num_workers)
    if not chunks:
        return []

    # Copy to CPU tensors for process transport.
    model_state_dict = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    tasks = [
        RolloutWorkerTask(
            model_state_dict=model_state_dict,
            board_channels=board_channels,
            hud_size=hud_size,
            num_actions=num_actions,
            hidden_size=hidden_size,
            rollout_steps=chunk_steps,
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=max_ticks,
            decks_path=decks_path,
            mirror_match=mirror_match,
            quiet_engine=quiet_engine,
            seed=seed + (worker_idx + 1) * 1009,
        )
        for worker_idx, chunk_steps in enumerate(chunks)
    ]

    attempts: Dict[int, int] = {idx: 0 for idx in range(len(tasks))}
    pending: List[tuple[int, RolloutWorkerTask]] = list(enumerate(tasks))
    parts_by_idx: Dict[int, List[Transition]] = {}

    while pending:
        submitted = {
            executor.submit(_collect_rollout_worker, task): (idx, task)
            for idx, task in pending
        }
        pending = []

        for future in as_completed(submitted):
            idx, task = submitted[future]
            try:
                parts_by_idx[idx] = future.result()
            except BrokenProcessPool:
                raise
            except Exception as exc:
                attempts[idx] += 1
                print(
                    f"worker_failure idx={idx} attempt={attempts[idx]} "
                    f"error={type(exc).__name__}: {exc}"
                )
                if attempts[idx] > worker_retries:
                    raise RuntimeError(
                        f"worker {idx} failed after {worker_retries + 1} attempts"
                    ) from exc
                pending.append((idx, task))

    transitions: List[Transition] = []
    for idx in range(len(tasks)):
        part = parts_by_idx[idx]
        transitions.extend(part)
    return transitions


def _fill_next_values(
    transitions: List[Transition],
    env: SelfPlayBattleEnv,
    model: MaskedPolicyValueNet,
    device: torch.device,
) -> None:
    idx_by_player: Dict[int, List[int]] = {0: [], 1: []}
    for idx, tr in enumerate(transitions):
        idx_by_player[tr.player_id].append(idx)

    bootstrap_value: Dict[int, float] = {0: 0.0, 1: 0.0}
    if env.battle is not None and not env.battle.game_over:
        next_obs0 = env.get_observation(0)
        next_obs1 = env.get_observation(1)
        next_mask0 = env.get_action_mask(0)
        next_mask1 = env.get_action_mask(1)
        with torch.no_grad():
            next_board_t = torch.as_tensor(
                np.stack([next_obs0.board, next_obs1.board]),
                dtype=torch.float32,
                device=device,
            )
            next_hud_t = torch.as_tensor(
                np.stack([next_obs0.hud, next_obs1.hud]),
                dtype=torch.float32,
                device=device,
            )
            next_mask_t = torch.as_tensor(
                np.stack([next_mask0, next_mask1]),
                dtype=torch.bool,
                device=device,
            )
            logits, value, _ = model(next_board_t, next_hud_t)
            dist = model.distribution(logits, next_mask_t)
            _ = dist.entropy()  # sanity-check masks in debug scenarios
            values = value.detach().cpu().numpy()
            bootstrap_value[0] = float(values[0])
            bootstrap_value[1] = float(values[1])

    for player_id in (0, 1):
        indices = idx_by_player[player_id]
        for offset, idx in enumerate(indices):
            tr = transitions[idx]
            if tr.done:
                tr.next_value = 0.0
            elif offset + 1 < len(indices):
                tr.next_value = transitions[indices[offset + 1]].value
            else:
                tr.next_value = bootstrap_value[player_id]


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

    boards_np = np.stack([t.board for t in transitions])
    hud_np = np.stack([t.hud for t in transitions])
    action_masks_np = np.stack([t.action_mask for t in transitions])
    actions_np = np.asarray([t.action for t in transitions], dtype=np.int64)
    old_log_probs_np = np.asarray([t.old_log_prob for t in transitions], dtype=np.float32)
    boards = torch.as_tensor(boards_np, dtype=torch.float32, device=device)
    hud = torch.as_tensor(hud_np, dtype=torch.float32, device=device)
    action_masks = torch.as_tensor(action_masks_np, dtype=torch.bool, device=device)
    actions = torch.as_tensor(actions_np, dtype=torch.long, device=device)
    old_log_probs = torch.as_tensor(old_log_probs_np, dtype=torch.float32, device=device)
    advantages_t = torch.as_tensor(advantages, dtype=torch.float32, device=device)
    returns_t = torch.as_tensor(returns, dtype=torch.float32, device=device)

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
    parser.add_argument("--num-workers", type=int, default=1)
    parser.add_argument("--worker-retries", type=int, default=2)
    parser.add_argument("--max-update-restarts", type=int, default=5)
    parser.add_argument("--resume-latest", action="store_true")
    parser.add_argument("--resume-from", type=str, default=None)
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


def find_latest_checkpoint(checkpoint_dir: Path) -> Optional[Path]:
    candidates = sorted(checkpoint_dir.glob("policy_update_*.pt"))
    if not candidates:
        return None
    return candidates[-1]


def main() -> None:
    args = parse_args()
    if args.resume_latest and args.resume_from:
        raise ValueError("Use only one of --resume-latest or --resume-from")

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
    start_update = 1

    resume_checkpoint: Optional[Path] = None
    if args.resume_from:
        resume_checkpoint = Path(args.resume_from)
        if not resume_checkpoint.exists():
            raise FileNotFoundError(f"resume checkpoint not found: {resume_checkpoint}")
    elif args.resume_latest:
        resume_checkpoint = find_latest_checkpoint(checkpoint_dir)

    if resume_checkpoint is not None:
        state = torch.load(resume_checkpoint, map_location=device)
        model.load_state_dict(state["model_state_dict"])
        if "optimizer_state_dict" in state:
            optimizer.load_state_dict(state["optimizer_state_dict"])
        saved_update = int(state.get("update", 0))
        start_update = saved_update + 1
        print(f"resumed_from={resume_checkpoint} saved_update={saved_update} start_update={start_update}")

    if args.num_workers > 1:
        print(f"rollout_workers={args.num_workers}")

    executor_ctx = ProcessPoolExecutor(max_workers=args.num_workers) if args.num_workers > 1 else None

    try:
        if start_update > args.updates:
            print(
                f"nothing_to_do start_update={start_update} is greater than target updates={args.updates}"
            )
            return
        for update in range(start_update, args.updates + 1):
            restarts = 0
            while True:
                try:
                    rollout_start = time.perf_counter()
                    if args.num_workers > 1:
                        assert executor_ctx is not None
                        transitions = collect_rollout_parallel(
                            executor=executor_ctx,
                            model=model,
                            rollout_steps=args.rollout_steps,
                            num_workers=args.num_workers,
                            board_channels=obs0.board.shape[0],
                            hud_size=obs0.hud.shape[0],
                            num_actions=env.action_space.num_actions,
                            hidden_size=args.hidden_size,
                            decision_interval_ticks=args.decision_interval,
                            max_ticks=args.max_ticks,
                            decks_path=args.decks_path,
                            mirror_match=args.mirror_match,
                            quiet_engine=args.quiet_engine,
                            seed=args.seed + update * 100_003,
                            worker_retries=args.worker_retries,
                        )
                    else:
                        transitions = collect_rollout(
                            env=env,
                            model=model,
                            device=device,
                            rollout_steps=args.rollout_steps,
                            quiet_engine=args.quiet_engine,
                        )
                    rollout_elapsed = time.perf_counter() - rollout_start
                    break
                except BrokenProcessPool as exc:
                    restarts += 1
                    print(f"pool_restart update={update:04d} attempt={restarts} error={exc}")
                    if executor_ctx is not None:
                        executor_ctx.shutdown(wait=False, cancel_futures=True)
                    if restarts > args.max_update_restarts:
                        raise RuntimeError(
                            f"Exceeded max_update_restarts={args.max_update_restarts} at update={update}"
                        ) from exc
                    executor_ctx = ProcessPoolExecutor(max_workers=args.num_workers)
                except Exception as exc:
                    restarts += 1
                    print(
                        f"rollout_restart update={update:04d} attempt={restarts} "
                        f"error={type(exc).__name__}: {exc}"
                    )
                    if restarts > args.max_update_restarts:
                        raise RuntimeError(
                            f"Exceeded max_update_restarts={args.max_update_restarts} at update={update}"
                        ) from exc

            update_start = time.perf_counter()
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
            update_elapsed = time.perf_counter() - update_start

            mean_reward = float(np.mean([t.reward for t in transitions]))
            decisions_per_sec = (len(transitions) / 2.0) / max(1e-6, rollout_elapsed)
            approx_games_per_min = (
                decisions_per_sec / (args.max_ticks / args.decision_interval) * 60.0
            )
            print(
                f"update={update:04d} "
                f"mean_reward={mean_reward:+.4f} "
                f"loss={stats['loss']:.4f} "
                f"policy={stats['policy_loss']:.4f} "
                f"value={stats['value_loss']:.4f} "
                f"entropy={stats['entropy']:.4f} "
                f"rollout_s={rollout_elapsed:.2f} "
                f"update_s={update_elapsed:.2f} "
                f"dps={decisions_per_sec:.1f} "
                f"gpm~={approx_games_per_min:.1f}"
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
    finally:
        if executor_ctx is not None:
            executor_ctx.shutdown(wait=True, cancel_futures=False)


if __name__ == "__main__":
    main()
