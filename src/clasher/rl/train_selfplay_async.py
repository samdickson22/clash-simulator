from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import io
import multiprocessing as mp
from pathlib import Path
import queue
import time
import traceback
from typing import Dict, Optional, Any, List

import numpy as np
import torch
from torch import nn

from clasher.rl.model import MaskedPolicyValueNet
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


@dataclass(frozen=True)
class ActorConfig:
    actor_id: int
    seed: int
    decks_path: str
    decision_interval: int
    max_ticks: int
    mirror_match: bool
    quiet_engine: bool
    actor_rollout_steps: int
    board_channels: int
    hud_size: int
    num_actions: int
    hidden_size: int


def _tensorize_obs(obs):
    board = torch.as_tensor(obs.board, dtype=torch.float32).unsqueeze(0)
    hud = torch.as_tensor(obs.hud, dtype=torch.float32).unsqueeze(0)
    return board, hud


def _tensorize_mask(mask: np.ndarray) -> torch.Tensor:
    return torch.as_tensor(mask, dtype=torch.bool).unsqueeze(0)


def _fill_next_values_numpy(batch: Dict[str, np.ndarray], env: SelfPlayBattleEnv, model: MaskedPolicyValueNet) -> None:
    player_ids = batch["player_ids"]
    rollout_values = batch["values"]
    dones = batch["dones"]
    next_values = np.zeros_like(rollout_values, dtype=np.float32)

    bootstrap = {0: 0.0, 1: 0.0}
    if env.battle is not None and not env.battle.game_over:
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)
        with torch.no_grad():
            board_t = torch.as_tensor(np.stack([obs0.board, obs1.board]), dtype=torch.float32)
            hud_t = torch.as_tensor(np.stack([obs0.hud, obs1.hud]), dtype=torch.float32)
            mask_t = torch.as_tensor(np.stack([mask0, mask1]), dtype=torch.bool)
            logits, value_t, _ = model(board_t, hud_t)
            _ = model.distribution(logits, mask_t).entropy()
            bootstrap_values = value_t.detach().cpu().numpy()
            bootstrap[0] = float(bootstrap_values[0])
            bootstrap[1] = float(bootstrap_values[1])

    for pid in (0, 1):
        idx = np.flatnonzero(player_ids == pid)
        for i, index in enumerate(idx):
            if dones[index]:
                next_values[index] = 0.0
            elif i + 1 < len(idx):
                next_values[index] = rollout_values[idx[i + 1]]
            else:
                next_values[index] = bootstrap[pid]

    batch["next_values"] = next_values


def _collect_rollout_numpy(
    env: SelfPlayBattleEnv,
    model: MaskedPolicyValueNet,
    rollout_steps: int,
    compress_obs_to_fp16: bool,
) -> Dict[str, np.ndarray]:
    boards: List[np.ndarray] = []
    huds: List[np.ndarray] = []
    masks: List[np.ndarray] = []
    actions: List[int] = []
    old_log_probs: List[float] = []
    values: List[float] = []
    rewards: List[float] = []
    dones: List[bool] = []
    player_ids: List[int] = []

    model.eval()
    if env.battle is None:
        env.reset()

    for _ in range(rollout_steps):
        decisions: Dict[int, Dict[str, Any]] = {}
        action_by_player: Dict[int, int] = {}
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)
        board_t = torch.as_tensor(np.stack([obs0.board, obs1.board]), dtype=torch.float32)
        hud_t = torch.as_tensor(np.stack([obs0.hud, obs1.hud]), dtype=torch.float32)
        mask_t = torch.as_tensor(np.stack([mask0, mask1]), dtype=torch.bool)

        with torch.no_grad():
            action_t, log_prob_t, value_t, _ = model.act(
                board=board_t,
                hud=hud_t,
                action_mask=mask_t,
                deterministic=False,
            )

        action_arr = action_t.detach().cpu().numpy()
        log_prob_arr = log_prob_t.detach().cpu().numpy()
        value_arr = value_t.detach().cpu().numpy()

        action_by_player[0] = int(action_arr[0])
        action_by_player[1] = int(action_arr[1])
        decisions[0] = {
            "obs_board": obs0.board.astype(np.float16 if compress_obs_to_fp16 else np.float32, copy=True),
            "obs_hud": obs0.hud.astype(np.float16 if compress_obs_to_fp16 else np.float32, copy=True),
            "mask": mask0.astype(np.bool_, copy=True),
            "action": action_by_player[0],
            "log_prob": float(log_prob_arr[0]),
            "value": float(value_arr[0]),
        }
        decisions[1] = {
            "obs_board": obs1.board.astype(np.float16 if compress_obs_to_fp16 else np.float32, copy=True),
            "obs_hud": obs1.hud.astype(np.float16 if compress_obs_to_fp16 else np.float32, copy=True),
            "mask": mask1.astype(np.bool_, copy=True),
            "action": action_by_player[1],
            "log_prob": float(log_prob_arr[1]),
            "value": float(value_arr[1]),
        }

        reward_by_player, done, _ = env.step(action_by_player)

        for pid in (0, 1):
            d = decisions[pid]
            boards.append(d["obs_board"])
            huds.append(d["obs_hud"])
            masks.append(d["mask"])
            actions.append(d["action"])
            old_log_probs.append(d["log_prob"])
            values.append(d["value"])
            rewards.append(float(reward_by_player[pid]))
            dones.append(done)
            player_ids.append(pid)

        if done:
            env.reset()

    batch: Dict[str, np.ndarray] = {
        "boards": np.stack(boards),
        "huds": np.stack(huds),
        "masks": np.stack(masks),
        "actions": np.asarray(actions, dtype=np.int64),
        "old_log_probs": np.asarray(old_log_probs, dtype=np.float32),
        "values": np.asarray(values, dtype=np.float32),
        "rewards": np.asarray(rewards, dtype=np.float32),
        "dones": np.asarray(dones, dtype=np.bool_),
        "player_ids": np.asarray(player_ids, dtype=np.int8),
        "next_values": np.zeros(len(values), dtype=np.float32),
    }
    _fill_next_values_numpy(batch, env=env, model=model)
    return batch


def _actor_loop(
    actor_cfg: ActorConfig,
    data_queue: mp.Queue,
    weight_queue: mp.Queue,
    error_queue: mp.Queue,
    stop_event: mp.Event,
    initial_state_dict: Dict[str, torch.Tensor],
    compress_obs_to_fp16: bool,
) -> None:
    try:
        torch.set_num_threads(1)
        np.random.seed(actor_cfg.seed)
        torch.manual_seed(actor_cfg.seed)

        model = MaskedPolicyValueNet(
            board_channels=actor_cfg.board_channels,
            hud_size=actor_cfg.hud_size,
            num_actions=actor_cfg.num_actions,
            hidden_size=actor_cfg.hidden_size,
            recurrent=False,
        ).to(torch.device("cpu"))
        model.load_state_dict(initial_state_dict)
        model.eval()

        env = SelfPlayBattleEnv(
            decision_interval_ticks=actor_cfg.decision_interval,
            max_ticks=actor_cfg.max_ticks,
            decks_path=actor_cfg.decks_path,
            seed=actor_cfg.seed,
            mirror_match=actor_cfg.mirror_match,
            canonical_perspective=True,
        )
        with maybe_silence_stdio(actor_cfg.quiet_engine):
            env.reset()

        while not stop_event.is_set():
            # Apply latest weights if provided.
            latest_state = None
            while True:
                try:
                    latest_state = weight_queue.get_nowait()
                except queue.Empty:
                    break
            if latest_state is not None:
                model.load_state_dict(latest_state)
                model.eval()

            with maybe_silence_stdio(actor_cfg.quiet_engine):
                batch = _collect_rollout_numpy(
                    env=env,
                    model=model,
                    rollout_steps=actor_cfg.actor_rollout_steps,
                    compress_obs_to_fp16=compress_obs_to_fp16,
                )

            if stop_event.is_set():
                break

            # Backpressure: block when queue is full.
            data_queue.put(batch)
    except Exception:
        error_queue.put(
            {
                "actor_id": actor_cfg.actor_id,
                "traceback": traceback.format_exc(),
            }
        )


def _compute_gae_numpy(
    rewards: np.ndarray,
    values: np.ndarray,
    next_values: np.ndarray,
    dones: np.ndarray,
    player_ids: np.ndarray,
    gamma: float,
    gae_lambda: float,
) -> tuple[np.ndarray, np.ndarray]:
    n = rewards.shape[0]
    advantages = np.zeros(n, dtype=np.float32)
    returns = np.zeros(n, dtype=np.float32)

    for pid in (0, 1):
        idx = np.flatnonzero(player_ids == pid)
        gae = 0.0
        for index in idx[::-1]:
            non_terminal = 0.0 if dones[index] else 1.0
            delta = rewards[index] + gamma * non_terminal * next_values[index] - values[index]
            gae = delta + gamma * gae_lambda * non_terminal * gae
            advantages[index] = gae
            returns[index] = gae + values[index]

    return advantages, returns


def _ppo_update_from_batch(
    model: MaskedPolicyValueNet,
    optimizer: torch.optim.Optimizer,
    batch: Dict[str, np.ndarray],
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

    boards = torch.as_tensor(batch["boards"], dtype=torch.float32, device=device)
    huds = torch.as_tensor(batch["huds"], dtype=torch.float32, device=device)
    masks = torch.as_tensor(batch["masks"], dtype=torch.bool, device=device)
    actions = torch.as_tensor(batch["actions"], dtype=torch.long, device=device)
    old_log_probs = torch.as_tensor(batch["old_log_probs"], dtype=torch.float32, device=device)
    adv_t = torch.as_tensor(advantages, dtype=torch.float32, device=device)
    ret_t = torch.as_tensor(returns, dtype=torch.float32, device=device)
    adv_t = (adv_t - adv_t.mean()) / (adv_t.std(unbiased=False) + 1e-8)

    stats = {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}
    steps = 0

    n = boards.shape[0]
    for _ in range(epochs):
        perm = torch.randperm(n, device=device)
        for start in range(0, n, batch_size):
            mb = perm[start : start + batch_size]
            logits, values_t, _ = model(boards[mb], huds[mb])
            dist = model.distribution(logits, masks[mb])

            new_log_probs = dist.log_prob(actions[mb])
            entropy = dist.entropy().mean()

            ratio = torch.exp(new_log_probs - old_log_probs[mb])
            unclipped = ratio * adv_t[mb]
            clipped = torch.clamp(ratio, 1.0 - clip_ratio, 1.0 + clip_ratio) * adv_t[mb]
            policy_loss = -torch.min(unclipped, clipped).mean()
            value_loss = 0.5 * torch.mean((ret_t[mb] - values_t) ** 2)
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
        for k in stats:
            stats[k] /= steps
    return stats


def _concat_batches(batches: List[Dict[str, np.ndarray]]) -> Dict[str, np.ndarray]:
    keys = batches[0].keys()
    out: Dict[str, np.ndarray] = {}
    for key in keys:
        out[key] = np.concatenate([b[key] for b in batches], axis=0)
    return out


def _state_dict_to_cpu(model: MaskedPolicyValueNet) -> Dict[str, torch.Tensor]:
    return {k: v.detach().cpu() for k, v in model.state_dict().items()}


def _find_latest_checkpoint(checkpoint_dir: Path) -> Optional[Path]:
    candidates = sorted(checkpoint_dir.glob("policy_update_*.pt"))
    if not candidates:
        return None
    return candidates[-1]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Async self-play trainer (CPU actors + MPS learner)")
    p.add_argument("--decks-path", type=str, default="decks.json")
    p.add_argument("--seed", type=int, default=13)
    p.add_argument("--updates", type=int, default=2000)
    p.add_argument("--decision-interval", type=int, default=8)
    p.add_argument("--max-ticks", type=int, default=9090)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--gamma", type=float, default=0.995)
    p.add_argument("--gae-lambda", type=float, default=0.95)
    p.add_argument("--clip-ratio", type=float, default=0.2)
    p.add_argument("--entropy-coef", type=float, default=0.01)
    p.add_argument("--value-coef", type=float, default=0.5)
    p.add_argument("--epochs", type=int, default=2)
    p.add_argument("--batch-size", type=int, default=1024)
    p.add_argument("--hidden-size", type=int, default=256)
    p.add_argument("--save-every", type=int, default=20)
    p.add_argument("--checkpoint-dir", type=str, default="checkpoints/selfplay_async")
    p.add_argument("--mirror-match", action="store_true")
    p.add_argument("--quiet-engine", action="store_true")
    p.add_argument("--device", type=str, choices=["auto", "cpu", "mps", "cuda"], default="auto")
    p.add_argument("--num-actors", type=int, default=8)
    p.add_argument("--actor-rollout-steps", type=int, default=128)
    p.add_argument("--transitions-per-update", type=int, default=4096)
    p.add_argument("--queue-size", type=int, default=16)
    p.add_argument("--policy-sync-every", type=int, default=2)
    p.add_argument("--resume-latest", action="store_true")
    p.add_argument("--resume-from", type=str, default=None)
    p.add_argument("--compress-obs-fp16", action="store_true")
    return p.parse_args()


def _launch_actors(
    ctx,
    num_actors: int,
    actor_cfg_base: Dict[str, Any],
    initial_state_dict: Dict[str, torch.Tensor],
    data_queue: mp.Queue,
    error_queue: mp.Queue,
    stop_event: mp.Event,
    compress_obs_to_fp16: bool,
) -> tuple[List[mp.Process], List[mp.Queue]]:
    processes: List[mp.Process] = []
    weight_queues: List[mp.Queue] = []
    for actor_id in range(num_actors):
        weight_q = ctx.Queue(maxsize=2)
        weight_queues.append(weight_q)
        cfg = ActorConfig(
            actor_id=actor_id,
            seed=actor_cfg_base["seed"] + actor_id * 9973,
            decks_path=actor_cfg_base["decks_path"],
            decision_interval=actor_cfg_base["decision_interval"],
            max_ticks=actor_cfg_base["max_ticks"],
            mirror_match=actor_cfg_base["mirror_match"],
            quiet_engine=actor_cfg_base["quiet_engine"],
            actor_rollout_steps=actor_cfg_base["actor_rollout_steps"],
            board_channels=actor_cfg_base["board_channels"],
            hud_size=actor_cfg_base["hud_size"],
            num_actions=actor_cfg_base["num_actions"],
            hidden_size=actor_cfg_base["hidden_size"],
        )
        proc = ctx.Process(
            target=_actor_loop,
            args=(cfg, data_queue, weight_q, error_queue, stop_event, initial_state_dict, compress_obs_to_fp16),
            daemon=True,
        )
        proc.start()
        processes.append(proc)
    return processes, weight_queues


def _terminate_actors(processes: List[mp.Process], stop_event: mp.Event) -> None:
    stop_event.set()
    for p in processes:
        p.join(timeout=3)
    for p in processes:
        if p.is_alive():
            p.terminate()
    for p in processes:
        p.join(timeout=2)


def _raise_actor_errors(error_queue: mp.Queue) -> None:
    errors = []
    while not error_queue.empty():
        errors.append(error_queue.get_nowait())
    if not errors:
        return
    msg = "\n\n".join(
        f"actor_crash actor_id={err['actor_id']}\n{err['traceback']}" for err in errors
    )
    raise RuntimeError(msg)


def main() -> None:
    args = _parse_args()
    if args.resume_latest and args.resume_from:
        raise ValueError("Use only one of --resume-latest or --resume-from")

    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = resolve_torch_device(args.device)
    print(f"device={device}")

    # Build learner/env metadata.
    meta_env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=args.decks_path,
        seed=args.seed,
        mirror_match=args.mirror_match,
        canonical_perspective=True,
    )
    with maybe_silence_stdio(args.quiet_engine):
        meta_env.reset()
    obs0 = meta_env.get_observation(0)
    num_actions = meta_env.action_space.num_actions

    model = MaskedPolicyValueNet(
        board_channels=obs0.board.shape[0],
        hud_size=obs0.hud.shape[0],
        num_actions=num_actions,
        hidden_size=args.hidden_size,
        recurrent=False,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)

    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    start_update = 1
    resume_ckpt: Optional[Path] = None
    if args.resume_from:
        resume_ckpt = Path(args.resume_from)
        if not resume_ckpt.exists():
            raise FileNotFoundError(f"resume checkpoint not found: {resume_ckpt}")
    elif args.resume_latest:
        resume_ckpt = _find_latest_checkpoint(checkpoint_dir)

    if resume_ckpt is not None:
        state = torch.load(resume_ckpt, map_location=device)
        model.load_state_dict(state["model_state_dict"])
        if "optimizer_state_dict" in state:
            optimizer.load_state_dict(state["optimizer_state_dict"])
        saved_update = int(state.get("update", 0))
        start_update = saved_update + 1
        print(f"resumed_from={resume_ckpt} saved_update={saved_update} start_update={start_update}")

    if start_update > args.updates:
        print(f"nothing_to_do start_update={start_update} > updates={args.updates}")
        return

    ctx = mp.get_context("spawn")
    data_queue = ctx.Queue(maxsize=args.queue_size)
    error_queue = ctx.Queue()
    stop_event = ctx.Event()

    actor_cfg_base = {
        "seed": args.seed,
        "decks_path": args.decks_path,
        "decision_interval": args.decision_interval,
        "max_ticks": args.max_ticks,
        "mirror_match": args.mirror_match,
        "quiet_engine": args.quiet_engine,
        "actor_rollout_steps": args.actor_rollout_steps,
        "board_channels": obs0.board.shape[0],
        "hud_size": obs0.hud.shape[0],
        "num_actions": num_actions,
        "hidden_size": args.hidden_size,
    }

    initial_state = _state_dict_to_cpu(model)
    actors, weight_queues = _launch_actors(
        ctx=ctx,
        num_actors=args.num_actors,
        actor_cfg_base=actor_cfg_base,
        initial_state_dict=initial_state,
        data_queue=data_queue,
        error_queue=error_queue,
        stop_event=stop_event,
        compress_obs_to_fp16=args.compress_obs_fp16,
    )
    print(f"actors={len(actors)} transitions_per_update={args.transitions_per_update}")

    try:
        for update in range(start_update, args.updates + 1):
            _raise_actor_errors(error_queue)

            collect_start = time.perf_counter()
            gathered: List[Dict[str, np.ndarray]] = []
            transitions_count = 0
            while transitions_count < args.transitions_per_update:
                try:
                    batch = data_queue.get(timeout=1)
                except queue.Empty as exc:
                    _raise_actor_errors(error_queue)
                    dead = [(idx, p.exitcode) for idx, p in enumerate(actors) if not p.is_alive()]
                    if dead:
                        raise RuntimeError(f"actors_exited_without_error_queue={dead}") from exc
                    waited = time.perf_counter() - collect_start
                    if waited > 30:
                        raise RuntimeError(
                            f"Timed out waiting for actor rollouts after {waited:.1f}s"
                        ) from exc
                    continue
                gathered.append(batch)
                transitions_count += int(batch["actions"].shape[0])
                _raise_actor_errors(error_queue)

            collect_elapsed = time.perf_counter() - collect_start
            batch_np = _concat_batches(gathered)
            advantages, returns = _compute_gae_numpy(
                rewards=batch_np["rewards"],
                values=batch_np["values"],
                next_values=batch_np["next_values"],
                dones=batch_np["dones"],
                player_ids=batch_np["player_ids"],
                gamma=args.gamma,
                gae_lambda=args.gae_lambda,
            )

            update_start = time.perf_counter()
            stats = _ppo_update_from_batch(
                model=model,
                optimizer=optimizer,
                batch=batch_np,
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

            if update % args.policy_sync_every == 0:
                weights = _state_dict_to_cpu(model)
                for wq in weight_queues:
                    # keep only latest to avoid stale backlog
                    while True:
                        try:
                            _ = wq.get_nowait()
                        except queue.Empty:
                            break
                    wq.put(weights)

            mean_reward = float(np.mean(batch_np["rewards"]))
            decisions_per_sec = (transitions_count / 2.0) / max(1e-6, collect_elapsed)
            approx_games_per_min = decisions_per_sec / (9090.0 / args.decision_interval) * 60.0
            print(
                f"update={update:04d} "
                f"mean_reward={mean_reward:+.4f} "
                f"loss={stats['loss']:.4f} "
                f"policy={stats['policy_loss']:.4f} "
                f"value={stats['value_loss']:.4f} "
                f"entropy={stats['entropy']:.4f} "
                f"collect_s={collect_elapsed:.2f} "
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
                        "num_actions": num_actions,
                    },
                    ckpt_path,
                )
                print(f"saved_checkpoint={ckpt_path}")

    finally:
        _terminate_actors(actors, stop_event)


if __name__ == "__main__":
    main()
