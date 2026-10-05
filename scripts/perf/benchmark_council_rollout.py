#!/usr/bin/env python3
"""Measure the unfitted council scalar/public-v4 path without optimizer updates."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time

import numpy as np
import torch

from clasher.battle import STANDARD_MATCH_TICKS
from clasher.rl.model import ClasherPolicy, PolicyConfig
from clasher.rl import council_recurrence
from clasher.rl.public_observation import project_council_public_observation
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent, SUPPORTED_CARDS
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.rl.structured_obs import StructuredObservationBuilder
from clasher.rl.train_recurrent import _sequence_inputs, collect_rollout_stationary_opponents

ROOT = Path(__file__).resolve().parents[2]
COUNCIL = ROOT / "reports/strategy_council_20260928"
TRAINING = COUNCIL / "m0/data/roles_v2/training.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_receipt() -> dict:
    paths = sorted((ROOT / "src/clasher").rglob("*.py"))
    paths += [Path(__file__), ROOT / "decks.json", ROOT / "gamedata.json", TRAINING,
              TRAINING.parent / "roles-manifest.json",
              COUNCIL / "strategy.md", COUNCIL / "consensus.json"]
    files = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    return {
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "files": files,
        "combined_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def weight_digest(model: ClasherPolicy) -> str:
    result = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        result.update(name.encode())
        result.update(str((tuple(tensor.shape), tensor.dtype)).encode())
        result.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return result.hexdigest()


def synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


class PublicOpponentAdapter:
    """Transport only public observations to the fixed reacting opponent."""

    def __init__(self, builder: StructuredObservationBuilder):
        self.controller = PublicScriptedOpponent(builder, style="balanced")

    def select_action(self, env, player_id, *, action_mask):
        packet = project_council_public_observation(env.get_structured_observation(player_id))
        action = self.controller.select_action(packet)
        if not action_mask[action]:
            raise ValueError("public opponent and collector disagree on legal support")
        return action


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"), default="cpu")
    parser.add_argument("--num-envs", type=int, default=2)
    parser.add_argument("--rollout-steps", type=int, default=128)
    parser.add_argument("--chunks", type=int, default=2)
    parser.add_argument("--max-seconds", type=float, default=None, help="Soft time limit, checked after each complete chunk")
    parser.add_argument("--warmup-steps", type=int, default=2)
    parser.add_argument("--torch-threads", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260928)
    parser.add_argument("--max-ticks", type=int, default=STANDARD_MATCH_TICKS + 1)
    parser.add_argument("--synthetic-backward", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if min(args.num_envs, args.rollout_steps, args.chunks, args.torch_threads, args.max_ticks) < 1:
        parser.error("counts must be positive")
    if args.max_seconds is not None and args.max_seconds <= 0:
        parser.error("max seconds must be positive")
    if args.warmup_steps < 0:
        parser.error("warmup steps must be nonnegative")
    if args.output.exists():
        parser.error("output already exists; use a new evidence file")
    return args


def main():
    args = parse_args()
    device = torch.device(args.device)
    if device.type == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    consensus = json.loads((COUNCIL / "consensus.json").read_text())
    if digest(COUNCIL / "strategy.md") != consensus["sha256"]:
        raise ValueError("strategy bytes differ from the jointly approved hash")
    roles = json.loads((TRAINING.parent / "roles-manifest.json").read_text())
    if digest(TRAINING) != roles["files"]["training"]["sha256"]:
        raise ValueError("training deck role differs from its frozen manifest")
    if json.loads(TRAINING.read_text())["role"] != "training":
        raise ValueError("benchmark requires the training role")

    load_before = os.getloadavg()
    before_source = source_receipt()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.set_num_threads(args.torch_threads)
    builder = StructuredObservationBuilder(
        decks_path=ROOT / "decks.json", card_vocab=sorted(SUPPORTED_CARDS),
        max_entities=128, canonical_perspective=True, canonical_lane_globals=True,
        public_history_slots=4, public_seen_card_slots=8, card_semantics_version=4,
        public_entity_levels=True, public_hand_levels=True,
    )
    config = PolicyConfig(
        num_tokens=builder.spec.num_tokens, max_entities=128, public_contract_version=4,
        public_token_names=builder.token_names, public_observation_confidence=True,
        canonical_lane_globals=True, card_semantics_version=4,
        public_history_slots=4, public_seen_card_slots=8,
        d_model=128, num_heads=4, actor_layers=4, critic_layers=2, memory_size=256,
        memory_kind="lstm", deterministic_hierarchy="slot",
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(device).eval()
    before_weights = weight_digest(model)
    forward_times: list[dict] = []
    recurrence_times: list[dict] = []
    act_times: list[float] = []
    original_reconstruction = council_recurrence.reconstruct_recurrent_state

    def timed_reconstruction(model, prefixes, **kwargs):
        synchronize(device)
        begin = time.perf_counter()
        result = original_reconstruction(model, prefixes, **kwargs)
        synchronize(device)
        recurrence_times.append({"seconds": time.perf_counter() - begin,
                                 "prefix_decisions": sum(p.sequence_length for p in prefixes if p is not None)})
        return result

    council_recurrence.reconstruct_recurrent_state = timed_reconstruction
    phase = "other"
    original_forward, original_act = model.forward, model.act

    def timed_forward(inputs, state=None):
        synchronize(device)
        start = time.perf_counter()
        result = original_forward(inputs, state)
        synchronize(device)
        forward_times.append({"phase": phase, "seconds": time.perf_counter() - start,
                              "batch": inputs.batch_size, "steps": inputs.sequence_length})
        return result

    def timed_act(*call_args, **kwargs):
        nonlocal phase
        previous, phase = phase, "action"
        synchronize(device)
        begin = time.perf_counter()
        try:
            return original_act(*call_args, **kwargs)
        finally:
            synchronize(device)
            act_times.append(time.perf_counter() - begin)
            phase = previous

    model.forward, model.act = timed_forward, timed_act
    episode_counts = Counter()
    command_counts = Counter()
    envs = []
    for index in range(args.num_envs):
        env = SelfPlayBattleEnv(
            decks_path=ROOT / "decks.json", sampling_decks_path=TRAINING,
            seed=args.seed + index, decision_interval_ticks=5, max_ticks=args.max_ticks,
            canonical_perspective=True, canonical_lane_globals=True,
            public_contract_version=4, engine_fast_path="off",
        )
        env._structured_obs_builder = builder
        env.reset()
        step = env.step

        def counted_step(actions, *, pre_action_masks=None, step=step):
            rewards, done, info = step(actions, pre_action_masks=pre_action_masks)
            episode_counts["true_completed_games"] += int(info.terminated)
            episode_counts["truncated_games"] += int(info.truncated)
            command_counts["submitted_commands_both_seats"] += len(actions)
            command_counts["rejected_commands_both_seats"] += sum(not accepted for accepted in info.action_success.values())
            return rewards, done, info

        env.step = counted_step
        envs.append(env)
    opponent = PublicOpponentAdapter(builder)
    no_op = envs[0].action_space.no_op_action
    state = model.initial_state(args.num_envs, device=device)
    previous_actions = np.full(args.num_envs, no_op, dtype=np.int64)
    previous_rewards = np.zeros(args.num_envs, dtype=np.float32)
    starts = np.ones(args.num_envs, dtype=np.bool_)
    opponent_state = None
    opponent_actions, opponent_rewards, opponent_starts = previous_actions.copy(), previous_rewards.copy(), starts.copy()

    def collect(steps):
        nonlocal state, previous_actions, previous_rewards, starts
        nonlocal opponent_state, opponent_actions, opponent_rewards, opponent_starts
        result = collect_rollout_stationary_opponents(
            envs=envs, learner_players=tuple(index % 2 for index in range(args.num_envs)),
            builder=builder, model=model, device=device, rollout_steps=steps,
            recurrent_state=state, previous_actions=previous_actions,
            previous_rewards=previous_rewards, episode_starts=starts,
            opponent_model=None, opponent_recurrent_state=opponent_state,
            opponent_previous_actions=opponent_actions, opponent_previous_rewards=opponent_rewards,
            opponent_episode_starts=opponent_starts, opponent_bot=opponent, quiet_engine=True,
        )
        (rollout, state, previous_actions, previous_rewards, starts, opponent_state,
         opponent_actions, opponent_rewards, opponent_starts) = result
        return rollout

    if args.warmup_steps:
        collect(args.warmup_steps)
    forward_times.clear()
    recurrence_times.clear()
    act_times.clear()
    episode_counts.clear()
    command_counts.clear()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    chunk_results = []
    retained_decisions = 0
    started = time.perf_counter()
    for chunk in range(args.chunks):
        chunk_start = time.perf_counter()
        rollout = collect(args.rollout_steps)
        elapsed = time.perf_counter() - chunk_start
        retained_decisions += rollout.transitions
        chunk_results.append({"chunk": chunk, "seconds": elapsed, "learner_decisions": rollout.transitions,
                              "decisions_per_second": rollout.transitions / elapsed,
                              "completed_or_truncated": rollout.episodes_finished})
        print(json.dumps(chunk_results[-1]), flush=True)
        if args.max_seconds is not None and time.perf_counter() - started >= args.max_seconds:
            break
    synchronize(device)
    elapsed = time.perf_counter() - started
    synthetic_backward = None
    if args.synthetic_backward:
        # Retain real input shapes/public features but discard every gameplay
        # reward, return, label and behavior action. One artificial PPO-shaped
        # loss exercises autograd. No optimizer is created and no step occurs.
        phase = "synthetic"
        inputs = _sequence_inputs(rollout, slice(None), device)
        model.zero_grad(set_to_none=True)
        synchronize(device)
        backward_start = time.perf_counter()
        output = model(inputs, model.initial_state(args.num_envs, device=device))
        distribution = output.distribution()
        synthetic_actions = distribution.sample()
        log_prob = distribution.log_prob(synthetic_actions)
        advantages = torch.arange(log_prob.numel(), device=device).reshape_as(log_prob) % 2 * 2 - 1
        ratio = torch.exp(log_prob - log_prob.detach())
        loss = -(torch.minimum(ratio * advantages, ratio.clamp(.8, 1.2) * advantages)).mean()
        loss = loss + .5 * output.values.square().mean() - .01 * distribution.entropy().mean()
        loss.backward()
        synchronize(device)
        synthetic_backward = {
            "seconds": time.perf_counter() - backward_start,
            "sequences": args.num_envs, "steps": args.rollout_steps,
            "all_gradients_finite": all(torch.isfinite(p.grad).all().item()
                                        for p in model.parameters() if p.grad is not None),
            "optimizer_steps": 0,
            "meaning": "One synthetic PPO-shaped forward/backward on real observation shapes; alternating artificial advantages, zero value targets, fresh synthetic sampled actions. Excludes prefix reconstruction, optimizer step and PPO epochs; not PPO update throughput.",
        }
        model.zero_grad(set_to_none=True)
    after_weights = weight_digest(model)
    after_source = source_receipt()
    changed = sorted(path for path in before_source["files"].keys() | after_source["files"].keys()
                     if before_source["files"].get(path) != after_source["files"].get(path))
    imported_paths = {
        str(Path(module.__file__).resolve().relative_to(ROOT))
        for module in tuple(sys.modules.values())
        if getattr(module, "__file__", None)
        and Path(module.__file__).resolve().is_relative_to(ROOT / "src/clasher")
        and str(module.__file__).endswith(".py")
    }
    runtime_paths = imported_paths | {
        str(Path(__file__).relative_to(ROOT)), "decks.json", "gamedata.json",
        str(TRAINING.relative_to(ROOT)), str((TRAINING.parent / "roles-manifest.json").relative_to(ROOT)),
        str((COUNCIL / "strategy.md").relative_to(ROOT)), str((COUNCIL / "consensus.json").relative_to(ROOT)),
    }
    runtime_changed = sorted(path for path in runtime_paths
                             if before_source["files"].get(path) != after_source["files"].get(path))
    action_latencies = [sample["seconds"] for sample in forward_times if sample["phase"] == "action"]
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() != "Darwin":
        peak_rss *= 1024
    accelerator_memory = {}
    if device.type == "cuda":
        accelerator_memory = {"peak_allocated_bytes": torch.cuda.max_memory_allocated(device),
                              "peak_reserved_bytes": torch.cuda.max_memory_reserved(device)}
    elif device.type == "mps":
        accelerator_memory = {"current_allocated_bytes": torch.mps.current_allocated_memory(),
                              "driver_allocated_bytes": torch.mps.driver_allocated_memory()}
    completed = episode_counts["true_completed_games"]
    report = {
        "schema": "clasher.council-untrained-rollout-benchmark.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed", "strategy_sha256": consensus["sha256"],
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "processor": platform.processor(), "torch": torch.__version__, "device": str(device)},
        "arguments": {**vars(args), "output": str(args.output)}, "policy_config": config.to_dict(),
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "host_load_average_before": list(load_before), "host_load_average_after": list(os.getloadavg()),
        "completed_chunks": len(chunk_results),
        "opponent": "public scripted balanced; frozen; reacting",
        "recurrent_reconstruction": "exact full episode prefix; no finite suffix approximation",
        "decision_interval_ticks": 5, "levels": {"cards": 11, "towers": [11, 11]},
        "learner_decisions": retained_decisions, "opponent_decisions_excluded": retained_decisions,
        "elapsed_seconds": elapsed, "learner_decisions_per_second": retained_decisions / elapsed,
        "action_forward_p95_ms": float(np.quantile(action_latencies, .95) * 1000),
        "action_total_p95_ms": float(np.quantile(act_times, .95) * 1000),
        "recurrence": {"seconds": sum(item["seconds"] for item in recurrence_times),
                       "fraction_of_rollout_time": sum(item["seconds"] for item in recurrence_times) / elapsed,
                       "prefix_decisions_replayed": sum(item["prefix_decisions"] for item in recurrence_times),
                       "reconstructions": len(recurrence_times)},
        "action_forward_calls": len(action_latencies), "all_rollout_forward_seconds": sum(s["seconds"] for s in forward_times if s["phase"] != "synthetic"),
        "forward_timing_includes_device_synchronization": True,
        "episodes": {"true_completed_games": completed, "truncated_games": episode_counts["truncated_games"]},
        "observed_completed_games_per_hour": completed * 3600 / elapsed if completed else None,
        "game_rate_qualification": "Observed completed count only; short runs are not steady-state throughput evidence.",
        "memory": {"process_peak_rss_bytes": peak_rss, "accelerator": accelerator_memory},
        "commands": dict(command_counts), "chunks": chunk_results,
        "source_before": before_source, "source_after": after_source,
        "changed_source_files": changed, "source_stable": before_source == after_source,
        "runtime_source_files": sorted(runtime_paths), "runtime_changed_source_files": runtime_changed,
        "runtime_source_stable": not runtime_changed,
        "runtime_source_scope": "Conservative imported Python module closure plus script/config/gamedata pins. Whole-tree drift remains separately recorded.",
        "weights_before_sha256": before_weights, "weights_after_sha256": after_weights,
        "weights_unchanged": before_weights == after_weights,
        "optimizer_steps": 0, "fitted_checkpoints_written": 0,
        "synthetic_forward_backward": synthetic_backward,
        "update_cost": "Actual PPO update throughput is unmeasured; optional synthetic autograd timing is separate.",
        "limits": "Local untrained scalar workload only. No playing-strength, transfer, native, paid-machine or remote 64-worker acceptance claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.output), "decisions_per_second": report["learner_decisions_per_second"],
                      "p95_ms": report["action_forward_p95_ms"], "episodes": report["episodes"],
                      "source_stable": report["source_stable"], "runtime_source_stable": report["runtime_source_stable"], "weights_unchanged": report["weights_unchanged"]}), flush=True)
    if not report["weights_unchanged"]:
        raise RuntimeError("untrained benchmark changed policy weights")


if __name__ == "__main__":
    main()
