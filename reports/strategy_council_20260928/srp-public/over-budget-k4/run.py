"""Frozen, resumable OQ-style public-player evaluation. One single-thread worker."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
import tomllib
from pathlib import Path

import numpy as np
import torch

from support import Context, TRAIN_DECKS, cl_eval, maybe_silence_stdio
from public_planner import PublicPlanner, Resources, observe
from clasher.rl.public_action_mask import PublicActionMaskInput

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def specs(config):
    out = []
    # Interleave players and styles, then paired game index.
    for group in config['groups']:
        for game in range(max(cell['games'] for cell in group['cells'])):
            for cell in group['cells']:
                if game >= cell['games']:
                    continue
                for player in config['players']:
                    out.append(dict(player=player, role=group['role'],
                                    opponent=cell['opponent'], seed=cell['seed'], game=game))
    return out


def game_id(spec):
    return f"{spec['player']['name']}__{spec['role']}__{spec['opponent']}__s{spec['seed']}__g{spec['game']:03d}"


def verify_manifest():
    manifest = json.loads((HERE/'manifest.json').read_text())
    for rel, expected in manifest['sha256'].items():
        got = hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        if got != expected:
            raise RuntimeError(f'frozen dependency changed: {rel}')
    return hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest()


def play(ctx, resources, prior, spec):
    game = spec['game']
    seat = game % 2
    other = 1-seat
    seed = spec['seed']+(game//2)*1009
    env = ctx.envs(spec['role'], spec['seed'])[seat]
    decks = cl_eval._sample_paired_ordered_decks(*ctx.pools(spec['role']), matchup_seed=seed)
    with maybe_silence_stdio(True):
        env.reset(seed=seed, ordered_decks=decks if seat == 0 else decks[::-1])
    torch.manual_seed(seed+271828)
    planner = PublicPlanner(resources, prior, k=spec['player']['k'],
                            seed=seed*2+seat+7919, policy=spec['player']['policy'])
    policy_state = ctx.loaded.model.initial_state(1, device=ctx.device)
    previous_other = resources.no_op
    previous_reward = 0.
    times, search_times, trace = [], [], []
    failures = outside = placements = decisions = 0
    wall, cpu = time.perf_counter(), time.process_time()
    while True:
        t, c = time.perf_counter(), time.process_time()
        information = observe(env, seat)
        before_calls = planner.calls
        action, mask = planner.decide(information, decisions)
        timing = [time.perf_counter()-t, time.process_time()-c]
        times.append(timing)
        if planner.calls != before_calls:
            search_times.append(timing)
        if spec['opponent'] == 'policy':
            other_action, policy_state, other_mask = cl_eval._policy_action(
                ctx.loaded, env, other, state=policy_state,
                previous_action=previous_other, previous_reward=previous_reward,
                episode_start=decisions == 0, deterministic=False, device=ctx.device)
        else:
            packet = observe(env, other).packet
            other_mask = resources.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            other_action = ctx.bot(spec['opponent']).select_action(packet)
        if action != resources.no_op:
            trace.append([env.battle.tick, action, information.own['hand'][action//576]])
            placements += 1
        outside += int(not mask[action])
        with maybe_silence_stdio(True):
            rewards, done, step_info = env.step({seat:action, other:other_action},
                pre_action_masks={seat:mask, other:other_mask})
        failures += int(action != resources.no_op and not step_info.action_success[seat])
        previous_other, previous_reward = other_action, rewards[other]
        decisions += 1
        if done:
            break
    b = env.battle
    assert b.game_over
    outcome = 'draw' if b.winner is None else 'win' if b.winner == seat else 'loss'
    measured = np.asarray(times)
    searched = np.asarray(search_times).reshape(-1,2)
    return dict(schema='srp-public-game-v1', id=game_id(spec), spec=spec,
                privileged_player=False, matchup_seed=seed, candidate_player=seat,
                outcome=outcome, score={'win':1.,'draw':.5,'loss':0.}[outcome],
                candidate_crowns=b.get_crown_count(seat), opponent_crowns=b.get_crown_count(other),
                ticks=b.tick, candidate_deck=list(decks[0]), opponent_deck=list(decks[1]),
                candidate_tower_hp=[getattr(b.players[seat],f'{p}_tower_hp') for p in ('left','right','king')],
                opponent_tower_hp=[getattr(b.players[other],f'{p}_tower_hp') for p in ('left','right','king')],
                decisions=decisions, planner_calls=planner.calls,
                hand_determined_decisions=planner.hand_determined,
                cycle_determined_decisions=planner.cycle_determined,
                elixir_estimate_fallbacks=0,
                planner_seconds=float(searched[:,0].sum()), planner_cpu_seconds=float(searched[:,1].sum()),
                decision_wall_seconds=float(measured[:,0].sum()), decision_cpu_seconds=float(measured[:,1].sum()),
                decision_wall_max=float(measured[:,0].max()),
                decision_cpu_max=float(measured[:,1].max()),
                wall_over_250ms=int((measured[:,0]>.25).sum()),
                cpu_over_250ms=int((measured[:,1]>.25).sum()),
                placements=placements, failed_actions=failures, actions_outside_public_mask=outside,
                wall_seconds=time.perf_counter()-wall, cpu_seconds=time.process_time()-cpu,
                trace=trace, pid=os.getpid())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worker',type=int,required=True)
    parser.add_argument('--workers',type=int,default=3)
    args = parser.parse_args()
    manifest_hash = verify_manifest()
    config = tomllib.loads((HERE/'config.toml').read_text())
    ctx = Context()
    resources = Resources(ctx)
    prior = json.loads(TRAIN_DECKS.read_text())
    for spec in specs(config)[args.worker::args.workers]:
        if (HERE/'STOP').exists():
            break
        output = HERE/'games'/spec['player']['name']/(game_id(spec)+'.json')
        if output.exists():
            continue
        verify_manifest()
        rec = play(ctx, resources, prior, spec)
        rec['manifest_sha256'] = manifest_hash
        output.parent.mkdir(parents=True,exist_ok=True)
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(rec,sort_keys=True)+'\n')
        temporary.replace(output)
        print(rec['id'], rec['outcome'], rec['ticks'], round(rec['wall_seconds'],2),flush=True)
    (HERE/'results'/f'worker-{args.worker}-done.json').write_text(json.dumps(dict(pid=os.getpid(), complete=not (HERE/'STOP').exists()))+'\n')


if __name__ == '__main__':
    main()
