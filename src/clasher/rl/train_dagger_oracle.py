from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import io
import multiprocessing as mp
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

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
        self._trim_to_capacity()

    def add_batch(self, batch: Dict[str, np.ndarray]) -> None:
        boards = batch["boards"]
        huds = batch["huds"]
        masks = batch["masks"]
        actions = batch["actions"]
        for idx in range(actions.shape[0]):
            self.boards.append(boards[idx].astype(np.float32, copy=True))
            self.huds.append(huds[idx].astype(np.float32, copy=True))
            self.masks.append(masks[idx].astype(np.bool_, copy=True))
            self.actions.append(int(actions[idx]))
        self._trim_to_capacity()

    def _trim_to_capacity(self) -> None:
        over = len(self.actions) - self.capacity
        if over <= 0:
            return
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


@dataclass(frozen=True)
class DaggerWorkerTask:
    model_state_dict: Dict[str, torch.Tensor]
    board_channels: int
    hud_size: int
    num_actions: int
    hidden_size: int
    decision_interval_ticks: int
    max_ticks: int
    decks_path: str
    mirror_match: bool
    quiet_engine: bool
    planner_depth: int
    planner_sims: int
    planner_action_samples: int
    decisions: int
    beta: float
    seed: int
    compress_obs_fp16: bool


_WORKER_MODEL: Optional[MaskedPolicyValueNet] = None
_WORKER_ENV: Optional[SelfPlayBattleEnv] = None
_WORKER_PLANNER: Optional[FixedDepthThompsonOracle] = None
_WORKER_CONFIG: Optional[Tuple[Any, ...]] = None
_WORKER_THREADS_SET: bool = False


def _find_latest_checkpoint(checkpoint_dir: Path) -> Optional[Path]:
    candidates = sorted(checkpoint_dir.glob("policy_dagger_iter_*.pt"))
    if not candidates:
        return None
    return candidates[-1]


def _state_dict_to_cpu(model: MaskedPolicyValueNet) -> Dict[str, torch.Tensor]:
    return {k: v.detach().cpu() for k, v in model.state_dict().items()}


def _split_decisions(total_decisions: int, num_workers: int) -> List[int]:
    workers = max(1, num_workers)
    base = total_decisions // workers
    remainder = total_decisions % workers
    chunks: List[int] = []
    for idx in range(workers):
        chunk = base + (1 if idx < remainder else 0)
        if chunk > 0:
            chunks.append(chunk)
    return chunks


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


def _empty_dagger_batch(env: SelfPlayBattleEnv, compress_obs_to_fp16: bool) -> Dict[str, np.ndarray]:
    obs0 = env.get_observation(0)
    board_dtype = np.float16 if compress_obs_to_fp16 else np.float32
    return {
        "boards": np.empty((0, *obs0.board.shape), dtype=board_dtype),
        "huds": np.empty((0, *obs0.hud.shape), dtype=board_dtype),
        "masks": np.empty((0, env.action_space.num_actions), dtype=np.bool_),
        "actions": np.empty((0,), dtype=np.int64),
    }


def _collect_dagger_batch(
    env: SelfPlayBattleEnv,
    planner: FixedDepthThompsonOracle,
    model: MaskedPolicyValueNet,
    rng: np.random.Generator,
    device: torch.device,
    *,
    decisions: int,
    beta: float,
    quiet_engine: bool,
    compress_obs_to_fp16: bool,
) -> tuple[Dict[str, np.ndarray], Dict[str, float]]:
    if env.battle is None:
        with maybe_silence_stdio(quiet_engine):
            env.reset()

    if decisions <= 0:
        return _empty_dagger_batch(env, compress_obs_to_fp16), {
            "episodes_finished": 0.0,
            "oracle_exec": 0.0,
            "student_exec": 0.0,
            "samples": 0.0,
        }

    model.eval()
    done_count = 0
    oracle_exec = 0
    student_exec = 0
    board_dtype = np.float16 if compress_obs_to_fp16 else np.float32

    boards: list[np.ndarray] = []
    huds: list[np.ndarray] = []
    masks: list[np.ndarray] = []
    actions: list[int] = []

    for _ in range(decisions):
        assert env.battle is not None
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)

        with maybe_silence_stdio(quiet_engine):
            oracle_actions = planner.select_actions(env.battle)

        boards.append(obs0.board.astype(board_dtype, copy=True))
        huds.append(obs0.hud.astype(board_dtype, copy=True))
        masks.append(mask0.astype(np.bool_, copy=True))
        actions.append(int(oracle_actions[0]))

        boards.append(obs1.board.astype(board_dtype, copy=True))
        huds.append(obs1.hud.astype(board_dtype, copy=True))
        masks.append(mask1.astype(np.bool_, copy=True))
        actions.append(int(oracle_actions[1]))

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

    batch = {
        "boards": np.stack(boards, axis=0),
        "huds": np.stack(huds, axis=0),
        "masks": np.stack(masks, axis=0),
        "actions": np.asarray(actions, dtype=np.int64),
    }
    stats = {
        "episodes_finished": float(done_count),
        "oracle_exec": float(oracle_exec),
        "student_exec": float(student_exec),
        "samples": float(len(actions)),
    }
    return batch, stats


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
    batch, stats = _collect_dagger_batch(
        env=env,
        planner=planner,
        model=model,
        rng=rng,
        device=device,
        decisions=decisions,
        beta=beta,
        quiet_engine=quiet_engine,
        compress_obs_to_fp16=False,
    )
    replay.add_batch(batch)
    total_exec = max(1.0, stats["oracle_exec"] + stats["student_exec"])
    return {
        "episodes_finished": stats["episodes_finished"],
        "oracle_exec_ratio": stats["oracle_exec"] / total_exec,
        "student_exec_ratio": stats["student_exec"] / total_exec,
    }


def _collect_dagger_worker(task: DaggerWorkerTask) -> Dict[str, object]:
    global _WORKER_MODEL, _WORKER_ENV, _WORKER_PLANNER, _WORKER_CONFIG, _WORKER_THREADS_SET

    if not _WORKER_THREADS_SET:
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
        task.planner_depth,
        task.planner_sims,
        task.planner_action_samples,
    )
    if _WORKER_MODEL is None or _WORKER_ENV is None or _WORKER_PLANNER is None or _WORKER_CONFIG != config:
        np.random.seed(task.seed)
        torch.manual_seed(task.seed)
        _WORKER_MODEL = MaskedPolicyValueNet(
            board_channels=task.board_channels,
            hud_size=task.hud_size,
            num_actions=task.num_actions,
            hidden_size=task.hidden_size,
            recurrent=False,
        ).to(torch.device("cpu"))
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
        _WORKER_PLANNER = FixedDepthThompsonOracle(
            action_space=_WORKER_ENV.action_space,
            decision_interval_ticks=task.decision_interval_ticks,
            plan_depth=task.planner_depth,
            num_simulations=task.planner_sims,
            rollout_action_samples=task.planner_action_samples,
            seed=task.seed + 1009,
        )
        _WORKER_CONFIG = config

    model = _WORKER_MODEL
    env = _WORKER_ENV
    planner = _WORKER_PLANNER
    assert model is not None
    assert env is not None
    assert planner is not None

    model.load_state_dict(task.model_state_dict)
    model.eval()
    rng = np.random.default_rng(task.seed + 1337)
    batch, stats = _collect_dagger_batch(
        env=env,
        planner=planner,
        model=model,
        rng=rng,
        device=torch.device("cpu"),
        decisions=task.decisions,
        beta=task.beta,
        quiet_engine=task.quiet_engine,
        compress_obs_to_fp16=task.compress_obs_fp16,
    )
    return {"batch": batch, "stats": stats}


def _collect_dagger_parallel(
    executor: ProcessPoolExecutor,
    model: MaskedPolicyValueNet,
    *,
    decisions_per_iter: int,
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
    planner_depth: int,
    planner_sims: int,
    planner_action_samples: int,
    beta: float,
    seed: int,
    compress_obs_fp16: bool,
    worker_retries: int,
) -> tuple[List[Dict[str, np.ndarray]], Dict[str, float]]:
    chunks = _split_decisions(decisions_per_iter, num_workers)
    if not chunks:
        return [], {"episodes_finished": 0.0, "oracle_exec": 0.0, "student_exec": 0.0, "samples": 0.0}

    model_state_dict = _state_dict_to_cpu(model)
    tasks = [
        DaggerWorkerTask(
            model_state_dict=model_state_dict,
            board_channels=board_channels,
            hud_size=hud_size,
            num_actions=num_actions,
            hidden_size=hidden_size,
            decision_interval_ticks=decision_interval_ticks,
            max_ticks=max_ticks,
            decks_path=decks_path,
            mirror_match=mirror_match,
            quiet_engine=quiet_engine,
            planner_depth=planner_depth,
            planner_sims=planner_sims,
            planner_action_samples=planner_action_samples,
            decisions=chunk_decisions,
            beta=beta,
            seed=seed + (worker_idx + 1) * 1009,
            compress_obs_fp16=compress_obs_fp16,
        )
        for worker_idx, chunk_decisions in enumerate(chunks)
    ]

    attempts: Dict[int, int] = {idx: 0 for idx in range(len(tasks))}
    pending: List[tuple[int, DaggerWorkerTask]] = list(enumerate(tasks))
    parts_by_idx: Dict[int, Dict[str, object]] = {}

    while pending:
        submitted = {
            executor.submit(_collect_dagger_worker, task): (idx, task)
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
                        f"dagger worker {idx} failed after {worker_retries + 1} attempts"
                    ) from exc
                pending.append((idx, task))

    batches: List[Dict[str, np.ndarray]] = []
    stats_total = {"episodes_finished": 0.0, "oracle_exec": 0.0, "student_exec": 0.0, "samples": 0.0}
    for idx in range(len(tasks)):
        result = parts_by_idx[idx]
        batch = result["batch"]
        stats = result["stats"]
        assert isinstance(batch, dict)
        assert isinstance(stats, dict)
        batches.append(batch)
        stats_total["episodes_finished"] += float(stats["episodes_finished"])
        stats_total["oracle_exec"] += float(stats["oracle_exec"])
        stats_total["student_exec"] += float(stats["student_exec"])
        stats_total["samples"] += float(stats["samples"])
    return batches, stats_total


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
    p.add_argument("--num-workers", type=int, default=1)
    p.add_argument("--worker-retries", type=int, default=1)
    p.add_argument("--compress-obs-fp16", action="store_true")
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
    print(f"device={device}", flush=True)
    resolved_decks_path = resolve_decks_path(args.decks_path, must_exist=True)
    checkpoint_dir = checkpoints_dir(args.checkpoint_dir, create=True)
    args.decks_path = str(resolved_decks_path)
    args.checkpoint_dir = str(checkpoint_dir)
    print(f"decks_path={resolved_decks_path}", flush=True)
    print(f"checkpoint_dir={checkpoint_dir}", flush=True)

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
        print(
            f"resumed_from={resume_ckpt} saved_iter={saved_iter} start_iter={start_iter}",
            flush=True,
        )

    if start_iter > args.iterations:
        print(f"nothing_to_do start_iter={start_iter} > iterations={args.iterations}", flush=True)
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

    executor: Optional[ProcessPoolExecutor] = None
    workers = max(1, int(args.num_workers))
    if workers > 1:
        ctx = mp.get_context("spawn")
        executor = ProcessPoolExecutor(max_workers=workers, mp_context=ctx)
    print(f"workers={workers} decisions_per_iter={args.decisions_per_iter}", flush=True)

    try:
        for iteration in range(start_iter, args.iterations + 1):
            beta = _beta_for_iter(
                iteration=iteration,
                total_iters=args.iterations,
                beta_start=args.beta_start,
                beta_end=args.beta_end,
            )
            collect_start = time.perf_counter()
            if executor is None:
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
                decisions_collected = args.decisions_per_iter
            else:
                batches, raw_stats = _collect_dagger_parallel(
                    executor=executor,
                    model=model,
                    decisions_per_iter=args.decisions_per_iter,
                    num_workers=workers,
                    board_channels=obs0.board.shape[0],
                    hud_size=obs0.hud.shape[0],
                    num_actions=action_space.num_actions,
                    hidden_size=args.hidden_size,
                    decision_interval_ticks=args.decision_interval,
                    max_ticks=args.max_ticks,
                    decks_path=str(resolved_decks_path),
                    mirror_match=args.mirror_match,
                    quiet_engine=args.quiet_engine,
                    planner_depth=args.planner_depth,
                    planner_sims=args.planner_sims,
                    planner_action_samples=args.planner_action_samples,
                    beta=beta,
                    seed=args.seed + iteration * 100_003,
                    compress_obs_fp16=args.compress_obs_fp16,
                    worker_retries=args.worker_retries,
                )
                for batch in batches:
                    replay.add_batch(batch)
                total_exec = max(1.0, raw_stats["oracle_exec"] + raw_stats["student_exec"])
                collect_stats = {
                    "episodes_finished": raw_stats["episodes_finished"],
                    "oracle_exec_ratio": raw_stats["oracle_exec"] / total_exec,
                    "student_exec_ratio": raw_stats["student_exec"] / total_exec,
                }
                decisions_collected = int(raw_stats["samples"] // 2)
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

            dps = decisions_collected / max(1e-6, collect_s)
            effective_dps = decisions_collected / max(1e-6, collect_s + update_s)
            approx_gpm = dps / (9090.0 / args.decision_interval) * 60.0
            effective_gpm = effective_dps / (9090.0 / args.decision_interval) * 60.0

            print(
                f"update={iteration:04d} "
                f"beta={beta:.3f} "
                f"replay={len(replay)} "
                f"loss={update_stats['loss']:.4f} "
                f"acc={update_stats['acc']:.4f} "
                f"entropy={update_stats['entropy']:.4f} "
                f"collect_s={collect_s:.2f} "
                f"update_s={update_s:.2f} "
                f"dps={dps:.1f} "
                f"gpm~={approx_gpm:.1f} "
                f"eff_dps={effective_dps:.1f} "
                f"eff_gpm~={effective_gpm:.1f} "
                f"episodes={collect_stats['episodes_finished']:.0f} "
                f"oracle_exec={collect_stats['oracle_exec_ratio']:.3f} "
                f"student_exec={collect_stats['student_exec_ratio']:.3f}",
                flush=True,
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
                print(f"saved_checkpoint={ckpt_path}", flush=True)
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
