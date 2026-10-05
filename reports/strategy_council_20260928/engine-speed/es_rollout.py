"""One pilot actor's share of collection, in process, plus the real PPO update.

Same construction as scripts/perf/benchmark_council_pilot_throughput.py (council
actor 2.6M params with fresh weights, council opponent pool in its initial phase:
50% public scripts / 50% two fresh initial policies, decision interval 5, max ticks
6001, nominal level 11, engine fast path off), but the environments live in THIS
process (LocalSlotBackend) so a stack sampler sees env, observation, mask,
opponent and model time together. num_envs=8 with torch_threads=1 corresponds to
one of the 8 actor processes of the 64-env/8-worker pilot layout.

Writes results/rollout_<label>.json (+ .collapsed stacks).
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import torch

from es_classify import classify_rollout_stacks
from es_common import RESULTS, TRAIN_DECKS, CollapsedSampler, Timer, host_info, peak_rss_mb, write_json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--num-envs", type=int, default=8)
    ap.add_argument("--rollout-steps", type=int, default=128)
    ap.add_argument("--warmup", type=int, default=2)
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--update-threads", type=int, default=2)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--seed", type=int, default=2901)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    from clasher.rl.council_opponents import CouncilOpponentPool, OpponentCheckpoint, policy_contract_sha256
    from clasher.rl.council_pilot import build_council_model_config, file_sha256
    from clasher.rl.model import ClasherPolicy, PolicyConfig
    from clasher.rl.parallel_rollout import (
        ActorWorkerConfig,
        BatchedInferenceCollector,
        EnvSlot,
        LocalSlotBackend,
        OpponentSpec,
        build_actor_environment,
        build_environment_opponents,
        build_policy_observation_builder,
    )
    from clasher.rl.structured_obs import StructuredObservationBuilder
    from clasher.rl.train_recurrent import compute_gae, maybe_silence_stdio, parse_args as trainer_args, ppo_update

    saved = sys.argv
    sys.argv = ["trainer"]
    defaults = trainer_args()
    sys.argv = saved

    probe = StructuredObservationBuilder(
        decks_path=TRAIN_DECKS, max_entities=128, card_semantics_version=4, public_history_slots=4,
        public_seen_card_slots=8, public_entity_levels=True, public_hand_levels=True,
        canonical_lane_globals=True,
    )
    config = build_council_model_config(probe)
    builder = build_policy_observation_builder(config, decks_path=TRAIN_DECKS, token_names=tuple(probe.token_names))
    model = ClasherPolicy(config, builder.card_stat_features)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, eps=1e-5, weight_decay=1e-5)
    out = {"args": vars(args), "host_before": host_info(),
           "parameter_count": sum(p.numel() for p in model.parameters())}

    with tempfile.TemporaryDirectory(prefix="es-rollout-") as temporary:
        tmp = Path(temporary)
        data_sha = file_sha256(builder.loader.data_file)
        entries = []
        for index in range(2):
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(args.seed + 17 + index)
                initial = ClasherPolicy(config, builder.card_stat_features)
            path = tmp / f"initial-{index}.pt"
            torch.save({"format_version": 2, "model_config": config.to_dict(),
                        "model_state_dict": initial.state_dict(), "token_names": tuple(builder.token_names),
                        "gamedata_sha256": data_sha}, path)
            entries.append(OpponentCheckpoint(path=str(path), sha256=file_sha256(path)))
        pool = CouncilOpponentPool(generation=0, phase="initial", gamedata_sha256=data_sha,
                                   policy_contract_sha256=policy_contract_sha256(config), initial=tuple(entries))
        pool_path = tmp / "opponents" / "pool.json"
        pool_path.parent.mkdir(parents=True)
        pool_path.write_text(pool.model_dump_json())
        worker = ActorWorkerConfig(
            decks_path=str(TRAIN_DECKS), token_names=tuple(builder.token_names), model_config=config.to_dict(),
            decision_interval=5, max_ticks=6001, mirror_match=False, opponent_mode="strategy",
            opponent_pool=(OpponentSpec(kind="strategy", strategy="balanced"),), engine_fast_path="off",
            quiet_engine=True, base_seed=args.seed, torch_threads=1, reward_potential_scale=0.05,
            reward_shaping_gamma=1.0, elixir_leak_penalty_scale=0.0, level_randomization_after=1_000_000,
            mixed_level_probability=0.5, sampling_decks_path=str(TRAIN_DECKS),
            learner_sampling_decks_path=str(TRAIN_DECKS), opponent_sampling_decks_path=str(TRAIN_DECKS),
            council_opponent_pool=str(pool_path),
        )
        policy_config = PolicyConfig.from_dict(worker.model_config)
        indices = tuple(range(args.num_envs))
        with maybe_silence_stdio(True):
            envs = [build_actor_environment(worker, i, policy_config, builder) for i in indices]
        opponents = build_environment_opponents(worker, indices, builder=builder, learner_model=model)
        slots = [EnvSlot(env_index=i, env=e, learner_player=i % 2, opponent_kind=k, opponent=o)
                 for i, e, (k, o) in zip(indices, envs, opponents)]
        backend = LocalSlotBackend(slots, actor_observation_domain=policy_config.actor_observation_domain,
                                   truncation_bootstrap=True)
        collector = BatchedInferenceCollector(backend, builder=builder)

        # Count engine ticks by wrapping each env's battle.step via the env step.
        tick_counter = {"ticks": 0}
        for slot in slots:
            original = slot.env.step

            def wrapped(actions, *, pre_action_masks=None, _orig=original, _env=slot.env):
                before = _env.battle.tick
                r = _orig(actions, pre_action_masks=pre_action_masks)
                tick_counter["ticks"] += max(0, _env.battle.tick - before)
                return r

            slot.env.step = wrapped

        decisions = 0
        cycles = []
        sampler = None
        for cycle in range(args.warmup + args.cycles):
            measured = cycle >= args.warmup
            if measured and args.sample and sampler is None:
                sampler = CollapsedSampler().start()
            tick_counter["ticks"] = 0
            ct = Timer()
            with ct:
                rollout = collector.collect(model=model, rollout_steps=args.rollout_steps,
                                            policy_version=cycle, learner_decisions=decisions)
            row = {"cycle": cycle, "measured": measured, "collect_wall": ct.wall, "collect_cpu": ct.cpu,
                   "decisions": int(rollout.transitions), "engine_ticks": tick_counter["ticks"],
                   "episodes_finished": int(rollout.episodes_finished),
                   "mean_prefix_length": float(np.mean([0 if p is None else p.sequence_length
                                                        for p in rollout.recurrent_prefixes]))}
            decisions += int(rollout.transitions)
            if measured or cycle == args.warmup - 1:
                torch.set_num_threads(args.update_threads)
                advantages, returns = compute_gae(rollout, gamma=1.0, gae_lambda=0.95)
                ut = Timer()
                with ut:
                    stats = ppo_update(
                        model=model, optimizer=optimizer, rollout=rollout, advantages=advantages,
                        returns=returns, device=torch.device("cpu"), epochs=2, sequence_batch_size=2,
                        clip_ratio=0.2, value_coef=defaults.value_coef, entropy_coef=defaults.entropy_coef,
                        action_type_entropy_coef=defaults.action_type_entropy_coef,
                        location_entropy_coef=defaults.location_entropy_coef,
                        conditional_slot_entropy_coef=defaults.conditional_slot_entropy_coef,
                        hand_aux_coef=defaults.hand_aux_coef, elixir_aux_coef=defaults.elixir_aux_coef,
                        target_kl=0.02,
                    )
                torch.set_num_threads(args.threads)
                row.update(update_wall=ut.wall, update_cpu=ut.cpu, optimizer_steps=stats["optimizer_steps"],
                           kl_early_stop=bool(stats["kl_early_stop"]))
            cycles.append(row)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
        if sampler is not None:
            sampler.stop()

    m = [r for r in cycles if r["measured"]]
    dec = sum(r["decisions"] for r in m)
    out.update(
        cycles=cycles,
        measured_decisions=dec,
        collect_wall=sum(r["collect_wall"] for r in m),
        collect_cpu=sum(r["collect_cpu"] for r in m),
        update_wall=sum(r["update_wall"] for r in m),
        update_cpu=sum(r["update_cpu"] for r in m),
        engine_ticks=sum(r["engine_ticks"] for r in m),
        host_after=host_info(),
        peak_rss_mb=peak_rss_mb(),
    )
    out["collect_cpu_ms_per_decision"] = 1e3 * out["collect_cpu"] / dec
    out["update_cpu_ms_per_decision"] = 1e3 * out["update_cpu"] / dec
    out["update_wall_ms_per_decision"] = 1e3 * out["update_wall"] / dec
    if sampler is not None:
        sampler.dump(RESULTS / f"rollout_{args.label}.collapsed")
        out["sample"] = classify_rollout_stacks(dict(sampler.stacks))
    write_json(RESULTS / f"rollout_{args.label}.json", out)
    print("collect cpu ms/decision", round(out["collect_cpu_ms_per_decision"], 2),
          "update cpu ms/decision", round(out["update_cpu_ms_per_decision"], 2))


if __name__ == "__main__":
    main()
