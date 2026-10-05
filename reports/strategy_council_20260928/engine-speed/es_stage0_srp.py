"""Recorded es_srp workloads, with every continuation action compared across runs."""
from __future__ import annotations
import argparse
import hashlib
import json
import cloudpickle as pickle
import sys
import time
from pathlib import Path

ES = Path(__file__).resolve().parent
sys.path.insert(0, str(ES / "srp_reference"))
import numpy as np
import oq_lib
import oq_cost
from es_common import battle_digest, host_info, write_json
from clasher.rl.train_recurrent import maybe_silence_stdio
from clasher.rl.script_rollout_planner import ScriptRolloutPlanner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['record', 'reference', 'fast', 'audit'], required=True)
    ap.add_argument('--calls', type=int, default=12)
    ap.add_argument('--label', required=True)
    args = ap.parse_args()
    ctx = oq_lib.Context()
    cache = Path.home() / '.cache/clasher-engine-speed/stage0-srp-snapshots.pkl'
    if args.mode == 'record':
        snaps = []
        for role, style, game in (("holdout", "balanced", 0), ("hog26", "balanced", 1)):
            snapshots, _, _ = oq_cost.collect_snapshots(ctx, role, style, game, every_ticks=300)
            snaps += snapshots
        cache.write_bytes(pickle.dumps(snaps))
        print(json.dumps({'snapshots': len(snaps), 'sha256': hashlib.sha256(cache.read_bytes()).hexdigest()}), flush=True)
        return
    snaps = pickle.loads(cache.read_bytes())
    env = ctx.envs('holdout', 0)[0]
    bot = ctx.bot('balanced')
    cls = oq_lib.ScriptRolloutPlanner if args.mode == 'reference' else ScriptRolloutPlanner
    planner = cls(env, bot, samples=16, script_top=4, horizon=160, rollout_interval=10, seed=1)
    original_model_action = planner._model_action
    action_trace, leaf_trace = [], []
    audit_count = 0
    def model_action(battle, seat, planning_seat):
        nonlocal audit_count
        action = original_model_action(battle, seat, planning_seat)
        if args.mode == 'audit':
            packet = oq_lib.ScriptRolloutPlanner._packet(planner, battle, seat)
            expected = int(bot.select_action(packet))
            assert action == expected, (battle.tick, seat, action, expected)
            audit_count += 1
        action_trace.append([int(battle.tick), seat, action])
        return action
    planner._model_action = model_action
    orig_phi = planner._phi
    def phi(battle, seat):
        score = orig_phi(battle, seat)
        leaf_trace.append([float(score).hex(), battle_digest(battle)])
        return score
    planner._phi = phi
    rows = []
    for battle in snaps:
        if len(rows) >= args.calls:
            break
        if battle.game_over:
            continue
        for seat in (0, 1):
            if len(rows) >= args.calls:
                break
            real, env.battle = env.battle, battle
            try:
                observation = env.get_structured_observation(seat)
                mask = env.get_action_mask(seat, structured_observation=observation)
            finally:
                env.battle = real
            exact = env.action_space.legal_action_mask(battle, seat) & mask
            exact[env.action_space.no_op_action] = True
            legal = np.flatnonzero(exact).astype(np.int64)
            if not np.any(legal != env.action_space.no_op_action):
                continue
            action_trace.clear(); leaf_trace.clear()
            ticks_before = planner.rollout_ticks
            cpu0, wall0 = time.process_time(), time.perf_counter()
            with maybe_silence_stdio(True):
                chosen = planner.select_action(battle, seat, legal)
            cpu, wall = time.process_time() - cpu0, time.perf_counter() - wall0
            row = {'tick': int(battle.tick), 'seat': seat, 'root_digest': battle_digest(battle),
                   'action': int(chosen), 'cpu': cpu, 'wall': wall,
                   'rollout_ticks': planner.rollout_ticks - ticks_before,
                   'script_actions': list(action_trace), 'leaves': list(leaf_trace)}
            rows.append(row)
            print({k: row[k] for k in ['tick', 'seat', 'action', 'cpu', 'rollout_ticks']}, flush=True)
    result = {'mode': args.mode, 'calls': rows, 'cpu_per_call_s': sum(r['cpu'] for r in rows) / max(1, len(rows)),
              'skipped_observations': getattr(planner, 'observation_skips', 0), 'audited_actions': audit_count,
              'snapshot_sha256': hashlib.sha256(cache.read_bytes()).hexdigest(), 'host': host_info()}
    write_json(ES / 'results' / f'stage0_srp_{args.label}.json', result)
    print({k: v for k, v in result.items() if k != 'calls'}, flush=True)

if __name__ == '__main__':
    main()
