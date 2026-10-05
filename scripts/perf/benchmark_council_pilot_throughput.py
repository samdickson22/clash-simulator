#!/usr/bin/env python3
"""Pilot throughput: real council rollouts plus real PPO updates, all in a temp dir.

Post-admission benchmark for the admission-scope decision v1 throughput path.
It builds the exact council actor (public contract 4, d128, 4+2 layers, LSTM 256)
with fresh weights, publishes two fresh initial policies to a temporary council
opponent pool (initial phase: 50% public scripts, 50% initial policies, fixed
per match), collects 128-step rollouts with the requested collector and runs the
signed PPO update (2 epochs, sequence minibatch 2, clip 0.2, lr 1e-4, target KL
0.02, exact full-prefix reconstruction). Warm-up cycles collect without timing
so measured cycles replay representative episode prefixes. Nothing is written
outside the temporary directory except the JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import torch

ROOT = Path(__file__).resolve().parents[2]
COUNCIL = ROOT / "reports/strategy_council_20260928"
TRAINING = COUNCIL / "m0/data/roles_v2/training.json"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--num-envs", type=int, required=True)
    parser.add_argument("--actor-workers", type=int, required=True)
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--inference-device", choices=("cpu", "mps"), default=None)
    parser.add_argument("--rollout-inference", choices=("learner", "worker"), default="learner")
    parser.add_argument("--torch-threads", type=int, default=4)
    parser.add_argument("--warmup-cycles", type=int, default=2)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--rollout-steps", type=int, default=128)
    parser.add_argument("--seed", type=int, default=2901)
    parser.add_argument("--label", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; use a new evidence file")
    if args.inference_device is None:
        args.inference_device = args.device if args.rollout_inference == "learner" else "cpu"
    return args


class ProcessSampler:
    """Samples RSS and CPU of this process and its children."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.process = psutil.Process()
        self.peak_total_rss = 0
        self.peak_learner_rss = 0
        self.peak_children_rss = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._cpu_start = None
        self._wall_start = None
        self._children_cpu: dict[int, float] = {}

    def _children(self):
        try:
            return self.process.children(recursive=True)
        except psutil.Error:
            return []

    def _run(self):
        while not self._stop.is_set():
            try:
                learner = self.process.memory_info().rss
                children = 0
                for child in self._children():
                    try:
                        children += child.memory_info().rss
                        times = child.cpu_times()
                        self._children_cpu[child.pid] = times.user + times.system
                    except psutil.Error:
                        pass
                self.peak_learner_rss = max(self.peak_learner_rss, learner)
                self.peak_children_rss = max(self.peak_children_rss, children)
                self.peak_total_rss = max(self.peak_total_rss, learner + children)
            except psutil.Error:
                pass
            self._stop.wait(self.interval)

    def start(self):
        times = self.process.cpu_times()
        self._cpu_start = times.user + times.system
        self._children_start = dict(self._children_cpu)
        self._wall_start = time.perf_counter()
        if not self._thread.is_alive():
            self._thread.start()

    def cpu_report(self):
        times = self.process.cpu_times()
        learner = times.user + times.system - self._cpu_start
        children = sum(
            value - self._children_start.get(pid, 0.0)
            for pid, value in self._children_cpu.items()
        )
        wall = time.perf_counter() - self._wall_start
        return {
            "wall_seconds": wall,
            "learner_cpu_seconds": learner,
            "actor_cpu_seconds": children,
            "average_cores_busy": (learner + children) / wall if wall else None,
        }

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)


def synchronize(device: torch.device):
    if device.type == "mps":
        torch.mps.synchronize()


def main():
    args = parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", str(args.torch_threads))
    torch.set_num_threads(args.torch_threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    from clasher.rl.council_opponents import (
        CouncilOpponentPool,
        OpponentCheckpoint,
        policy_contract_sha256,
    )
    from clasher.rl.council_pilot import build_council_model_config, file_sha256
    from clasher.rl.model import ClasherPolicy
    from clasher.rl.parallel_rollout import (
        ActorWorkerConfig,
        BatchedInferenceCollector,
        OpponentSpec,
        ParallelRolloutCollector,
        build_policy_observation_builder,
    )
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from clasher.rl.train_recurrent import compute_gae, parse_args as trainer_args, ppo_update

    saved_argv = sys.argv
    sys.argv = ["trainer"]
    defaults = trainer_args()
    sys.argv = saved_argv

    learner_device = torch.device(args.device)
    inference_device = torch.device(args.inference_device)
    probe = StructuredObservationBuilder(
        decks_path=TRAINING,
        max_entities=128,
        card_semantics_version=4,
        public_history_slots=4,
        public_seen_card_slots=8,
        public_entity_levels=True,
        public_hand_levels=True,
        canonical_lane_globals=True,
    )
    config = build_council_model_config(probe)
    builder = build_policy_observation_builder(
        config, decks_path=TRAINING, token_names=tuple(probe.token_names)
    )
    model = ClasherPolicy(config, builder.card_stat_features).to(learner_device)
    inference_model = (
        model
        if inference_device == learner_device
        else ClasherPolicy(config, builder.card_stat_features).to(inference_device)
    )
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, eps=1e-5, weight_decay=1e-5)
    report: dict = {
        "schema": "clasher.council-pilot-throughput-benchmark.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "arguments": {**vars(args), "output": str(args.output)},
        "host": {
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "torch": torch.__version__,
            "load_average_before": list(os.getloadavg()),
        },
        "recipe": {
            "rollout_steps": args.rollout_steps,
            "epochs": 2,
            "sequence_batch_size": 2,
            "learning_rate": 1e-4,
            "clip_ratio": 0.2,
            "target_kl": 0.02,
            "recurrent_reconstruction": "exact full episode prefix (council_recurrence)",
            "opponents": "council pool, initial phase: 50% public scripts, 50% two fresh initial policies, fixed per match",
            "levels": "nominal 11",
        },
        "parameter_count": sum(p.numel() for p in model.parameters()),
    }
    with tempfile.TemporaryDirectory(prefix="council-throughput-") as temporary:
        tmp = Path(temporary)
        data_sha = file_sha256(builder.loader.data_file)
        entries = []
        for index in range(2):
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(args.seed + 17 + index)
                initial = ClasherPolicy(config, builder.card_stat_features)
            path = tmp / f"initial-{index}.pt"
            torch.save(
                {
                    "format_version": 2,
                    "model_config": config.to_dict(),
                    "model_state_dict": initial.state_dict(),
                    "token_names": tuple(builder.token_names),
                    "gamedata_sha256": data_sha,
                },
                path,
            )
            entries.append(OpponentCheckpoint(path=str(path), sha256=file_sha256(path)))
        pool = CouncilOpponentPool(
            generation=0,
            phase="initial",
            gamedata_sha256=data_sha,
            policy_contract_sha256=policy_contract_sha256(config),
            initial=tuple(entries),
        )
        pool_path = tmp / "opponents" / "pool.json"
        pool_path.parent.mkdir(parents=True)
        pool_path.write_text(pool.model_dump_json())
        worker = ActorWorkerConfig(
            decks_path=str(TRAINING),
            token_names=tuple(builder.token_names),
            model_config=config.to_dict(),
            decision_interval=5,
            max_ticks=6001,
            mirror_match=False,
            opponent_mode="strategy",
            opponent_pool=(OpponentSpec(kind="strategy", strategy="balanced"),),
            engine_fast_path="off",
            quiet_engine=True,
            base_seed=args.seed,
            torch_threads=1,
            reward_potential_scale=0.05,
            reward_shaping_gamma=1.0,
            elixir_leak_penalty_scale=0.0,
            level_randomization_after=1_000_000,
            mixed_level_probability=0.5,
            sampling_decks_path=str(TRAINING),
            learner_sampling_decks_path=str(TRAINING),
            opponent_sampling_decks_path=str(TRAINING),
            council_opponent_pool=str(pool_path),
        )
        sampler = ProcessSampler()
        startup = time.perf_counter()
        if args.rollout_inference == "learner":
            collector = BatchedInferenceCollector.with_actor_processes(
                num_workers=args.actor_workers,
                num_envs=args.num_envs,
                config=worker,
                builder=builder,
            )
        else:
            collector = ParallelRolloutCollector(
                num_workers=args.actor_workers, num_envs=args.num_envs, config=worker
            )
        report["startup_seconds"] = time.perf_counter() - startup
        act_times: list[float] = []
        original_act = inference_model.act

        def timed_act(*call_args, **kwargs):
            synchronize(inference_device)
            begin = time.perf_counter()
            try:
                return original_act(*call_args, **kwargs)
            finally:
                synchronize(inference_device)
                act_times.append(time.perf_counter() - begin)

        inference_model.act = timed_act
        from clasher.rl import council_recurrence

        recon = {"seconds": 0.0, "steps": 0}
        original_reconstruct = council_recurrence.reconstruct_recurrent_state

        def timed_reconstruct(m, prefixes, **kwargs):
            device = kwargs.get("device", torch.device("cpu"))
            synchronize(device)
            begin = time.perf_counter()
            try:
                return original_reconstruct(m, prefixes, **kwargs)
            finally:
                synchronize(device)
                recon["seconds"] += time.perf_counter() - begin
                recon["steps"] += sum(p.sequence_length for p in prefixes if p is not None)

        council_recurrence.reconstruct_recurrent_state = timed_reconstruct
        cycles = []
        decisions = 0
        try:
            sampler.start()
            for cycle in range(args.warmup_cycles + args.cycles):
                measured = cycle >= args.warmup_cycles
                if cycle == args.warmup_cycles:
                    act_times.clear()
                    sampler.start()
                if inference_model is not model:
                    inference_model.load_state_dict(model.state_dict())
                recon.update(seconds=0.0, steps=0)
                begin = time.perf_counter()
                if args.rollout_inference == "learner":
                    rollout = collector.collect(
                        model=inference_model,
                        rollout_steps=args.rollout_steps,
                        policy_version=cycle,
                        learner_decisions=decisions,
                    )
                else:
                    rollout = collector.collect(
                        model=model,
                        rollout_steps=args.rollout_steps,
                        policy_version=cycle,
                        learner_decisions=decisions,
                        timeout=3600,
                    )
                collect_seconds = time.perf_counter() - begin
                collect_recon = dict(recon)
                row = {
                    "cycle": cycle,
                    "measured": measured,
                    "collect_seconds": collect_seconds,
                    "collect_reconstruction_seconds": collect_recon["seconds"],
                    "collect_prefix_steps_replayed": collect_recon["steps"],
                    "decisions": int(rollout.transitions),
                    "episodes_finished": int(rollout.episodes_finished),
                    "mean_prefix_length": float(
                        np.mean(
                            [0 if p is None else p.sequence_length for p in rollout.recurrent_prefixes]
                        )
                    ),
                }
                decisions += int(rollout.transitions)
                # The last warm-up cycle also runs one untimed update so device
                # kernels are compiled before the measured cycles.
                if measured or cycle == args.warmup_cycles - 1:
                    advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
                    recon.update(seconds=0.0, steps=0)
                    synchronize(learner_device)
                    begin = time.perf_counter()
                    stats = ppo_update(
                        model=model,
                        optimizer=optimizer,
                        rollout=rollout,
                        advantages=advantages,
                        returns=returns,
                        device=learner_device,
                        epochs=2,
                        sequence_batch_size=2,
                        clip_ratio=0.2,
                        value_coef=defaults.value_coef,
                        entropy_coef=defaults.entropy_coef,
                        action_type_entropy_coef=defaults.action_type_entropy_coef,
                        location_entropy_coef=defaults.location_entropy_coef,
                        conditional_slot_entropy_coef=defaults.conditional_slot_entropy_coef,
                        hand_aux_coef=defaults.hand_aux_coef,
                        elixir_aux_coef=defaults.elixir_aux_coef,
                        target_kl=0.02,
                    )
                    synchronize(learner_device)
                    row.update(
                        update_seconds=time.perf_counter() - begin,
                        update_reconstruction_seconds=recon["seconds"],
                        update_prefix_steps_replayed=recon["steps"],
                        optimizer_steps=stats["optimizer_steps"],
                        kl_early_stop=bool(stats["kl_early_stop"]),
                        loss=stats["loss"],
                        approx_kl=stats["approx_kl"],
                    )
                cycles.append(row)
                print(json.dumps(row), flush=True)
            cpu = sampler.cpu_report()
        finally:
            sampler.stop()
            collector.close()
            council_recurrence.reconstruct_recurrent_state = original_reconstruct
    measured_rows = [row for row in cycles if row["measured"]]
    total_decisions = sum(row["decisions"] for row in measured_rows)
    collect = sum(row["collect_seconds"] for row in measured_rows)
    update = sum(row["update_seconds"] for row in measured_rows)
    full_minibatches = sum(row["decisions"] for row in measured_rows) / (2 * args.rollout_steps) * 2
    steps_taken = sum(row["optimizer_steps"] for row in measured_rows)
    report.update(
        cycles=cycles,
        measured_decisions=total_decisions,
        collect_seconds=collect,
        update_seconds=update,
        learner_decisions_per_second_including_updates=total_decisions / (collect + update),
        collection_decisions_per_second=total_decisions / collect,
        update_seconds_per_full_minibatch=update / max(1.0, steps_taken),
        optimizer_steps=steps_taken,
        planned_full_minibatches=full_minibatches,
        kl_early_stops=sum(bool(row["kl_early_stop"]) for row in measured_rows),
        # Updates that stop early on the KL guard are cheaper; normalize to a
        # full two-epoch update for projection.
        projected_decisions_per_second_full_updates=total_decisions
        / (collect + update / max(1e-9, steps_taken / full_minibatches)),
        inference_forward_p95_ms=float(np.quantile(act_times, 0.95) * 1000) if act_times else None,
        inference_forward_median_ms=float(np.median(act_times) * 1000) if act_times else None,
        memory={
            "peak_total_rss_bytes": sampler.peak_total_rss,
            "peak_learner_rss_bytes": sampler.peak_learner_rss,
            "peak_actor_rss_bytes": sampler.peak_children_rss,
            "mps_driver_allocated_bytes": torch.mps.driver_allocated_memory()
            if torch.backends.mps.is_available()
            else None,
        },
        cpu=cpu,
        load_average_after=list(os.getloadavg()),
        checkpoints_written_outside_tmp=0,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "label": args.label,
                "decisions_per_second": report["learner_decisions_per_second_including_updates"],
                "projected_full_updates": report["projected_decisions_per_second_full_updates"],
                "collect_s": collect,
                "update_s": update,
                "p95_ms": report["inference_forward_p95_ms"],
                "peak_rss_gb": sampler.peak_total_rss / 1e9,
                "cores_busy": cpu["average_cores_busy"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
