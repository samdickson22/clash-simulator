from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
import multiprocessing as mp
from pathlib import Path
import queue
import time
import traceback
from typing import Dict, Optional, Any, List

import numpy as np
import torch
from torch import nn

from clasher.paths import checkpoints_dir, decks_path as resolve_decks_path, resolve_path
from clasher.rl.benchmark import run_async_queue_benchmark
from clasher.rl.inference_server import InferenceServer
from clasher.rl.model import MaskedPolicyValueNet
from clasher.rl.shared_rollout_ipc import (
    SlotHandles,
    SharedRolloutPoolOwner,
    SharedRolloutWriter,
    build_rollout_field_specs,
)
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.train_selfplay import resolve_torch_device


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
    engine_fast_path: str
    inference_mode: str


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


def _fill_next_values_from_bootstrap(
    batch: Dict[str, np.ndarray],
    bootstrap: Dict[int, float],
) -> None:
    player_ids = batch["player_ids"]
    rollout_values = batch["values"]
    dones = batch["dones"]
    next_values = np.zeros_like(rollout_values, dtype=np.float32)

    for pid in (0, 1):
        idx = np.flatnonzero(player_ids == pid)
        for i, index in enumerate(idx):
            if dones[index]:
                next_values[index] = 0.0
            elif i + 1 < len(idx):
                next_values[index] = rollout_values[idx[i + 1]]
            else:
                next_values[index] = float(bootstrap.get(pid, 0.0))

    batch["next_values"] = next_values


def _collect_rollout_numpy(
    env: SelfPlayBattleEnv,
    model: MaskedPolicyValueNet,
    rollout_steps: int,
    compress_obs_to_fp16: bool,
) -> Dict[str, np.ndarray]:
    model.eval()
    if env.battle is None:
        env.reset()
    obs0_init = env.get_observation(0)
    board_shape = obs0_init.board.shape
    hud_size = obs0_init.hud.shape[0]
    transitions = rollout_steps * 2
    obs_dtype = np.float16 if compress_obs_to_fp16 else np.float32
    boards = np.empty((transitions, *board_shape), dtype=obs_dtype)
    huds = np.empty((transitions, hud_size), dtype=obs_dtype)
    masks = np.empty((transitions, env.action_space.num_actions), dtype=np.bool_)
    actions = np.empty((transitions,), dtype=np.int64)
    old_log_probs = np.empty((transitions,), dtype=np.float32)
    values = np.empty((transitions,), dtype=np.float32)
    rewards = np.empty((transitions,), dtype=np.float32)
    dones = np.empty((transitions,), dtype=np.bool_)
    player_ids = np.empty((transitions,), dtype=np.int8)
    write_idx = 0

    for _ in range(rollout_steps):
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

        reward_by_player, done, _ = env.step(action_by_player)

        boards[write_idx] = obs0.board
        huds[write_idx] = obs0.hud
        masks[write_idx] = mask0
        actions[write_idx] = action_by_player[0]
        old_log_probs[write_idx] = float(log_prob_arr[0])
        values[write_idx] = float(value_arr[0])
        rewards[write_idx] = float(reward_by_player[0])
        dones[write_idx] = done
        player_ids[write_idx] = 0
        write_idx += 1

        boards[write_idx] = obs1.board
        huds[write_idx] = obs1.hud
        masks[write_idx] = mask1
        actions[write_idx] = action_by_player[1]
        old_log_probs[write_idx] = float(log_prob_arr[1])
        values[write_idx] = float(value_arr[1])
        rewards[write_idx] = float(reward_by_player[1])
        dones[write_idx] = done
        player_ids[write_idx] = 1
        write_idx += 1

        if done:
            env.reset()

    batch: Dict[str, np.ndarray] = {
        "boards": boards,
        "huds": huds,
        "masks": masks,
        "actions": actions,
        "old_log_probs": old_log_probs,
        "values": values,
        "rewards": rewards,
        "dones": dones,
        "player_ids": player_ids,
        "next_values": np.zeros(transitions, dtype=np.float32),
    }
    _fill_next_values_numpy(batch, env=env, model=model)
    env_metrics = env.pop_fast_path_metrics()
    batch["mask_shadow_checks"] = np.asarray([env_metrics["mask_shadow_checks"]], dtype=np.float32)
    batch["mask_shadow_mismatches"] = np.asarray([env_metrics["mask_shadow_mismatches"]], dtype=np.float32)
    return batch


def _collect_rollout_numpy_centralized(
    env: SelfPlayBattleEnv,
    rollout_steps: int,
    compress_obs_to_fp16: bool,
    actor_id: int,
    request_counter: int,
    inference_request_queue: mp.Queue,
    inference_response_queue: mp.Queue,
) -> tuple[Dict[str, np.ndarray], int]:
    if env.battle is None:
        env.reset()
    obs0_init = env.get_observation(0)
    board_shape = obs0_init.board.shape
    hud_size = obs0_init.hud.shape[0]
    transitions = rollout_steps * 2
    board_dtype = np.float16 if compress_obs_to_fp16 else np.float32
    boards = np.empty((transitions, *board_shape), dtype=board_dtype)
    huds = np.empty((transitions, hud_size), dtype=board_dtype)
    masks = np.empty((transitions, env.action_space.num_actions), dtype=np.bool_)
    actions = np.empty((transitions,), dtype=np.int64)
    old_log_probs = np.empty((transitions,), dtype=np.float32)
    values = np.empty((transitions,), dtype=np.float32)
    rewards = np.empty((transitions,), dtype=np.float32)
    dones = np.empty((transitions,), dtype=np.bool_)
    player_ids = np.empty((transitions,), dtype=np.int8)
    write_idx = 0

    pending_by_id: Dict[int, Dict[str, Any]] = {}

    def _infer(board_np: np.ndarray, hud_np: np.ndarray, mask_np: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        nonlocal request_counter
        req_id = request_counter
        request_counter += 1
        inference_request_queue.put(
            {
                "actor_id": actor_id,
                "request_id": req_id,
                "boards": board_np.astype(board_dtype, copy=False),
                "huds": hud_np.astype(board_dtype, copy=False),
                "masks": mask_np.astype(np.bool_, copy=False),
            }
        )
        while True:
            if req_id in pending_by_id:
                response = pending_by_id.pop(req_id)
                break
            response = inference_response_queue.get()
            other_id = int(response["request_id"])
            if other_id == req_id:
                break
            pending_by_id[other_id] = response
        return (
            np.asarray(response["actions"], dtype=np.int64),
            np.asarray(response["log_probs"], dtype=np.float32),
            np.asarray(response["values"], dtype=np.float32),
        )

    for _ in range(rollout_steps):
        action_by_player: Dict[int, int] = {}
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)
        board_np = np.stack([obs0.board, obs1.board], axis=0).astype(np.float32, copy=False)
        hud_np = np.stack([obs0.hud, obs1.hud], axis=0).astype(np.float32, copy=False)
        mask_np = np.stack([mask0, mask1], axis=0).astype(np.bool_, copy=False)

        action_arr, log_prob_arr, value_arr = _infer(board_np, hud_np, mask_np)

        action_by_player[0] = int(action_arr[0])
        action_by_player[1] = int(action_arr[1])

        reward_by_player, done, _ = env.step(action_by_player)

        boards[write_idx] = obs0.board
        huds[write_idx] = obs0.hud
        masks[write_idx] = mask0
        actions[write_idx] = action_by_player[0]
        old_log_probs[write_idx] = float(log_prob_arr[0])
        values[write_idx] = float(value_arr[0])
        rewards[write_idx] = float(reward_by_player[0])
        dones[write_idx] = done
        player_ids[write_idx] = 0
        write_idx += 1

        boards[write_idx] = obs1.board
        huds[write_idx] = obs1.hud
        masks[write_idx] = mask1
        actions[write_idx] = action_by_player[1]
        old_log_probs[write_idx] = float(log_prob_arr[1])
        values[write_idx] = float(value_arr[1])
        rewards[write_idx] = float(reward_by_player[1])
        dones[write_idx] = done
        player_ids[write_idx] = 1
        write_idx += 1

        if done:
            env.reset()

    bootstrap = {0: 0.0, 1: 0.0}
    if env.battle is not None and not env.battle.game_over:
        obs0 = env.get_observation(0)
        obs1 = env.get_observation(1)
        mask0 = env.get_action_mask(0)
        mask1 = env.get_action_mask(1)
        board_np = np.stack([obs0.board, obs1.board], axis=0).astype(np.float32, copy=False)
        hud_np = np.stack([obs0.hud, obs1.hud], axis=0).astype(np.float32, copy=False)
        mask_np = np.stack([mask0, mask1], axis=0).astype(np.bool_, copy=False)
        _, _, bootstrap_values = _infer(board_np, hud_np, mask_np)
        bootstrap = {0: float(bootstrap_values[0]), 1: float(bootstrap_values[1])}

    batch: Dict[str, np.ndarray] = {
        "boards": boards,
        "huds": huds,
        "masks": masks,
        "actions": actions,
        "old_log_probs": old_log_probs,
        "values": values,
        "rewards": rewards,
        "dones": dones,
        "player_ids": player_ids,
        "next_values": np.zeros(transitions, dtype=np.float32),
    }
    _fill_next_values_from_bootstrap(batch, bootstrap=bootstrap)
    env_metrics = env.pop_fast_path_metrics()
    batch["mask_shadow_checks"] = np.asarray([env_metrics["mask_shadow_checks"]], dtype=np.float32)
    batch["mask_shadow_mismatches"] = np.asarray([env_metrics["mask_shadow_mismatches"]], dtype=np.float32)
    return batch, request_counter


def _actor_loop(
    actor_cfg: ActorConfig,
    data_queue: mp.Queue,
    weight_queue: Optional[mp.Queue],
    error_queue: mp.Queue,
    stop_event: mp.Event,
    initial_state_dict: Dict[str, torch.Tensor],
    compress_obs_to_fp16: bool,
    inference_request_queue: Optional[mp.Queue] = None,
    inference_response_queue: Optional[mp.Queue] = None,
    rollout_slot_handles: Optional[List[SlotHandles]] = None,
    rollout_free_slot_queue: Optional[mp.Queue] = None,
) -> None:
    rollout_writer: Optional[SharedRolloutWriter] = None
    try:
        torch.set_num_threads(1)
        np.random.seed(actor_cfg.seed)
        torch.manual_seed(actor_cfg.seed)
        if rollout_slot_handles is not None:
            rollout_writer = SharedRolloutWriter(rollout_slot_handles)

        model: Optional[MaskedPolicyValueNet] = None
        if actor_cfg.inference_mode == "actor_local":
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
            engine_fast_path=actor_cfg.engine_fast_path,
        )
        with maybe_silence_stdio(actor_cfg.quiet_engine):
            env.reset()
        request_counter = 0

        while not stop_event.is_set():
            if actor_cfg.inference_mode == "actor_local":
                assert model is not None
                if weight_queue is not None:
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
            else:
                if inference_request_queue is None or inference_response_queue is None:
                    raise RuntimeError("centralized inference mode requires request/response queues")
                with maybe_silence_stdio(actor_cfg.quiet_engine):
                    batch, request_counter = _collect_rollout_numpy_centralized(
                        env=env,
                        rollout_steps=actor_cfg.actor_rollout_steps,
                        compress_obs_to_fp16=compress_obs_to_fp16,
                        actor_id=actor_cfg.actor_id,
                        request_counter=request_counter,
                        inference_request_queue=inference_request_queue,
                        inference_response_queue=inference_response_queue,
                    )

            if stop_event.is_set():
                break

            if rollout_writer is not None:
                if rollout_free_slot_queue is None:
                    raise RuntimeError("shared rollout writer requires free-slot queue")
                slot_id = int(rollout_free_slot_queue.get())
                rollout_writer.write_batch(slot_id, batch)
                data_queue.put(
                    {
                        "shared_rollout": True,
                        "actor_id": actor_cfg.actor_id,
                        "slot_id": slot_id,
                        "transitions": int(batch["actions"].shape[0]),
                    }
                )
            else:
                # Backpressure: block when queue is full.
                data_queue.put(batch)
    except Exception:
        error_queue.put(
            {
                "actor_id": actor_cfg.actor_id,
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        if rollout_writer is not None:
            rollout_writer.close()


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


def _init_rollout_accumulator(
    capacity: int,
    batch: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    acc: Dict[str, np.ndarray] = {}
    for key, value in batch.items():
        if key in {"mask_shadow_checks", "mask_shadow_mismatches"}:
            continue
        shape = value.shape
        acc[key] = np.empty((capacity, *shape[1:]), dtype=value.dtype)
    return acc


def _append_batch_to_accumulator(
    acc: Dict[str, np.ndarray],
    batch: Dict[str, np.ndarray],
    start: int,
) -> int:
    count = int(batch["actions"].shape[0])
    end = start + count
    for key, value in batch.items():
        if key in {"mask_shadow_checks", "mask_shadow_mismatches"}:
            continue
        acc[key][start:end] = value
    return end


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
    p.add_argument("--actors-auto", action="store_true")
    p.add_argument("--actor-rollout-steps", type=int, default=128)
    p.add_argument("--transitions-per-update", type=int, default=4096)
    p.add_argument("--queue-size", type=int, default=16)
    p.add_argument("--rollout-transport", choices=["queue", "shm"], default="queue")
    p.add_argument("--shared-slots-per-actor", type=int, default=2)
    p.add_argument("--policy-sync-every", type=int, default=2)
    p.add_argument("--perf-log-every", type=int, default=10)
    p.add_argument("--resume-latest", action="store_true")
    p.add_argument("--resume-from", type=str, default=None)
    p.add_argument("--compress-obs-fp16", action="store_true")
    p.add_argument("--engine-fast-path", choices=["off", "shadow", "on"], default="off")
    p.add_argument("--inference-mode", choices=["actor_local", "centralized"], default="actor_local")
    p.add_argument("--inference-max-batch", type=int, default=2048)
    p.add_argument("--inference-max-wait-ms", type=float, default=2.0)
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
    inference_request_queue: Optional[mp.Queue] = None,
    inference_response_queues: Optional[List[mp.Queue]] = None,
    rollout_slot_handles_by_actor: Optional[List[List[SlotHandles]]] = None,
    rollout_free_slot_queues: Optional[List[mp.Queue]] = None,
) -> tuple[List[mp.Process], List[Optional[mp.Queue]]]:
    processes: List[mp.Process] = []
    weight_queues: List[Optional[mp.Queue]] = []
    for actor_id in range(num_actors):
        weight_q: Optional[mp.Queue] = None
        if actor_cfg_base["inference_mode"] == "actor_local":
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
            engine_fast_path=actor_cfg_base["engine_fast_path"],
            inference_mode=actor_cfg_base["inference_mode"],
        )
        response_q = None
        if inference_response_queues is not None:
            response_q = inference_response_queues[actor_id]
        actor_rollout_handles = None
        if rollout_slot_handles_by_actor is not None:
            actor_rollout_handles = rollout_slot_handles_by_actor[actor_id]
        free_slot_q = None
        if rollout_free_slot_queues is not None:
            free_slot_q = rollout_free_slot_queues[actor_id]
        proc = ctx.Process(
            target=_actor_loop,
            args=(
                cfg,
                data_queue,
                weight_q,
                error_queue,
                stop_event,
                initial_state_dict,
                compress_obs_to_fp16,
                inference_request_queue,
                response_q,
                actor_rollout_handles,
                free_slot_q,
            ),
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


def _auto_pick_actor_count(
    *,
    seed: int,
    transitions: int,
    actor_rollout_steps: int,
    queue_size: int,
    decks_path: str,
    decision_interval: int,
    max_ticks: int,
    mirror_match: bool,
    quiet_engine: bool,
    engine_fast_path: str,
) -> int:
    cpu_cap = max(2, min(10, mp.cpu_count()))
    candidates = [n for n in (4, 6, 8, 10) if n <= cpu_cap]
    best = candidates[0]
    best_dps = -1.0
    print(f"actors_auto_candidates={candidates}")
    for n in candidates:
        metrics = run_async_queue_benchmark(
            seed=seed + n * 101,
            num_actors=n,
            transitions_target=transitions,
            actor_rollout_steps=actor_rollout_steps,
            queue_size=queue_size,
            decks_path=decks_path,
            decision_interval=decision_interval,
            max_ticks=max_ticks,
            mirror_match=mirror_match,
            quiet_engine=quiet_engine,
            engine_fast_path=engine_fast_path,
            inference_mode="actor_local",
        )
        dps = float(metrics["decisions_per_sec"])
        print(f"actors_auto_probe actors={n} dps={dps:.1f}")
        if dps > best_dps:
            best_dps = dps
            best = n
    print(f"actors_auto_selected={best}")
    return best


def main() -> None:
    args = _parse_args()
    if args.resume_latest and args.resume_from:
        raise ValueError("Use only one of --resume-latest or --resume-from")

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

    # Build learner/env metadata.
    meta_env = SelfPlayBattleEnv(
        decision_interval_ticks=args.decision_interval,
        max_ticks=args.max_ticks,
        decks_path=str(resolved_decks_path),
        seed=args.seed,
        mirror_match=args.mirror_match,
        canonical_perspective=True,
        engine_fast_path=args.engine_fast_path,
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

    start_update = 1
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
        saved_update = int(state.get("update", 0))
        start_update = saved_update + 1
        print(f"resumed_from={resume_ckpt} saved_update={saved_update} start_update={start_update}")

    if start_update > args.updates:
        print(f"nothing_to_do start_update={start_update} > updates={args.updates}")
        return

    if args.actors_auto:
        args.num_actors = _auto_pick_actor_count(
            seed=args.seed,
            transitions=min(8192, args.transitions_per_update),
            actor_rollout_steps=args.actor_rollout_steps,
            queue_size=args.queue_size,
            decks_path=str(resolved_decks_path),
            decision_interval=args.decision_interval,
            max_ticks=args.max_ticks,
            mirror_match=args.mirror_match,
            quiet_engine=args.quiet_engine,
            engine_fast_path=args.engine_fast_path,
        )

    ctx = mp.get_context("spawn")
    data_queue = ctx.Queue(maxsize=args.queue_size)
    error_queue = ctx.Queue()
    stop_event = ctx.Event()
    inference_request_queue: Optional[mp.Queue] = None
    inference_response_queues: Optional[List[mp.Queue]] = None
    inference_server: Optional[InferenceServer] = None
    shared_rollout_pool: Optional[SharedRolloutPoolOwner] = None
    rollout_slot_handles_by_actor: Optional[List[List[SlotHandles]]] = None
    rollout_free_slot_queues: Optional[List[mp.Queue]] = None

    actor_cfg_base = {
        "seed": args.seed,
        "decks_path": str(resolved_decks_path),
        "decision_interval": args.decision_interval,
        "max_ticks": args.max_ticks,
        "mirror_match": args.mirror_match,
        "quiet_engine": args.quiet_engine,
        "actor_rollout_steps": args.actor_rollout_steps,
        "board_channels": obs0.board.shape[0],
        "hud_size": obs0.hud.shape[0],
        "num_actions": num_actions,
        "hidden_size": args.hidden_size,
        "engine_fast_path": args.engine_fast_path,
        "inference_mode": args.inference_mode,
    }

    if args.inference_mode == "centralized":
        inference_request_queue = ctx.Queue(maxsize=max(args.queue_size, args.num_actors * 2))
        inference_response_queues = [ctx.Queue(maxsize=4) for _ in range(args.num_actors)]
        inference_model = MaskedPolicyValueNet(
            board_channels=obs0.board.shape[0],
            hud_size=obs0.hud.shape[0],
            num_actions=num_actions,
            hidden_size=args.hidden_size,
            recurrent=False,
        ).to(device)
        inference_model.load_state_dict(model.state_dict())
        inference_model.eval()
        inference_server = InferenceServer(
            model=inference_model,
            device=device,
            request_queue=inference_request_queue,
            response_queues={idx: q for idx, q in enumerate(inference_response_queues)},
            max_batch=args.inference_max_batch,
            max_wait_ms=args.inference_max_wait_ms,
        )
        inference_server.start()

    if args.rollout_transport == "shm":
        transitions_per_batch = args.actor_rollout_steps * 2
        obs_dtype = "float16" if args.compress_obs_fp16 else "float32"
        field_specs = build_rollout_field_specs(
            transitions_per_batch=transitions_per_batch,
            board_shape=tuple(obs0.board.shape),
            hud_size=int(obs0.hud.shape[0]),
            num_actions=num_actions,
            obs_dtype=obs_dtype,
        )
        shared_rollout_pool = SharedRolloutPoolOwner(
            num_actors=args.num_actors,
            slots_per_actor=max(1, args.shared_slots_per_actor),
            field_specs=field_specs,
        )
        rollout_slot_handles_by_actor = [
            shared_rollout_pool.actor_slot_handles(actor_id)
            for actor_id in range(args.num_actors)
        ]
        rollout_free_slot_queues = [ctx.Queue(maxsize=max(1, args.shared_slots_per_actor)) for _ in range(args.num_actors)]
        for q in rollout_free_slot_queues:
            for slot_id in range(max(1, args.shared_slots_per_actor)):
                q.put(slot_id)

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
        inference_request_queue=inference_request_queue,
        inference_response_queues=inference_response_queues,
        rollout_slot_handles_by_actor=rollout_slot_handles_by_actor,
        rollout_free_slot_queues=rollout_free_slot_queues,
    )
    print(
        f"actors={len(actors)} transitions_per_update={args.transitions_per_update} "
        f"inference_mode={args.inference_mode} engine_fast_path={args.engine_fast_path} "
        f"rollout_transport={args.rollout_transport}"
    )

    try:
        for update in range(start_update, args.updates + 1):
            _raise_actor_errors(error_queue)

            collect_start = time.perf_counter()
            accumulated: Optional[Dict[str, np.ndarray]] = None
            transitions_count = 0
            shadow_checks = 0.0
            shadow_mismatches = 0.0
            max_capacity = (
                args.transitions_per_update
                + (args.actor_rollout_steps * 2 * max(1, args.num_actors))
            )
            while transitions_count < args.transitions_per_update:
                try:
                    item = data_queue.get(timeout=1)
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
                batch: Dict[str, np.ndarray]
                if (
                    isinstance(item, dict)
                    and item.get("shared_rollout", False)
                ):
                    if shared_rollout_pool is None or rollout_free_slot_queues is None:
                        raise RuntimeError("received shared rollout metadata without shared pool")
                    actor_id = int(item["actor_id"])
                    slot_id = int(item["slot_id"])
                    batch = shared_rollout_pool.read_batch_copy(actor_id, slot_id)
                    rollout_free_slot_queues[actor_id].put(slot_id)
                else:
                    batch = item
                if accumulated is None:
                    accumulated = _init_rollout_accumulator(max_capacity, batch)
                next_count = _append_batch_to_accumulator(accumulated, batch, transitions_count)
                transitions_count = next_count
                shadow_checks += float(np.asarray(batch.get("mask_shadow_checks", 0.0)).reshape(-1)[0])
                shadow_mismatches += float(np.asarray(batch.get("mask_shadow_mismatches", 0.0)).reshape(-1)[0])
                _raise_actor_errors(error_queue)

            collect_elapsed = time.perf_counter() - collect_start
            if accumulated is None:
                raise RuntimeError("no rollout data collected")
            batch_np = {k: v[:transitions_count] for k, v in accumulated.items()}
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
                if args.inference_mode == "actor_local":
                    for wq in weight_queues:
                        if wq is None:
                            continue
                        # keep only latest to avoid stale backlog
                        while True:
                            try:
                                _ = wq.get_nowait()
                            except queue.Empty:
                                break
                        wq.put(weights)
                elif inference_server is not None:
                    inference_server.sync_weights_from(model)

            mean_reward = float(np.mean(batch_np["rewards"]))
            decisions_per_sec = (transitions_count / 2.0) / max(1e-6, collect_elapsed)
            effective_decisions_per_sec = (transitions_count / 2.0) / max(
                1e-6, collect_elapsed + update_elapsed
            )
            approx_games_per_min = decisions_per_sec / (9090.0 / args.decision_interval) * 60.0
            effective_games_per_min = (
                effective_decisions_per_sec / (9090.0 / args.decision_interval) * 60.0
            )
            should_log_perf = (
                update == start_update
                or update == args.updates
                or update % max(1, args.perf_log_every) == 0
            )
            if should_log_perf:
                shadow_div = shadow_mismatches / max(1.0, shadow_checks)
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
                    f"gpm~={approx_games_per_min:.1f} "
                    f"eff_dps={effective_decisions_per_sec:.1f} "
                    f"eff_gpm~={effective_games_per_min:.1f} "
                    f"mask_div={shadow_div:.4f}"
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
        if inference_server is not None:
            inference_server.stop()
        _terminate_actors(actors, stop_event)
        if shared_rollout_pool is not None:
            shared_rollout_pool.close()


if __name__ == "__main__":
    main()
