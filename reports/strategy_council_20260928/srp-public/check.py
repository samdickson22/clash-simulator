"""Pre-evaluation partial-trajectory checks and whole-decision benchmarks."""
import copy
import json
import pickle
import random
import time
from collections import deque
from pathlib import Path

import numpy as np
import torch

from support import Context, TRAIN_DECKS, cl_eval, maybe_silence_stdio
from public_planner import PublicPlanner, Resources, observe

HERE = Path(__file__).resolve().parent


class HiddenDenied:
    def __init__(self, original):
        self.original = original

    def __getattr__(self, name):
        if name in ('hand','deck','cycle_queue','elixir','next_card_refill_cooldown_ms','card_levels'):
            raise AssertionError('forbidden opponent read: '+name)
        return getattr(self.original, name)


class RngDenied:
    def __getattr__(self, name):
        raise AssertionError('forbidden true RNG read: '+name)


def main():
    ctx = Context()
    r = Resources(ctx)
    prior = json.loads(TRAIN_DECKS.read_text())
    roots = []
    sensors = []
    # Partial script trajectories only. No test of candidate player outcomes.
    for game in range(4):
        env = ctx.envs('holdout', 991001+game)[game % 2]
        decks = cl_eval._sample_paired_ordered_decks(*ctx.pools('holdout'), matchup_seed=991001+game)
        with maybe_silence_stdio(True):
            env.reset(seed=991001+game, ordered_decks=decks if game % 2 == 0 else decks[::-1])
        belief = PublicPlanner(r, prior)
        for d in range(200):
            sensor_wall, sensor_cpu = time.perf_counter(), time.process_time()
            info = observe(env, game % 2)
            sensor = (time.perf_counter()-sensor_wall, time.process_time()-sensor_cpu)
            belief.belief.update(info.tick, info.history)
            true = env.battle.players[1-game % 2]
            assert abs(belief.belief.elixir_units/10000-true.elixir) < 1e-8
            assert belief.belief.refill == true.next_card_refill_cooldown_ms
            actual = np.zeros(12, dtype=np.int16)
            actual[:4] = [belief.belief.ids[x] if x else 0 for x in true.hand]
            actual[4:4+len(true.cycle_queue)] = [belief.belief.ids[x] for x in true.cycle_queue]
            assert np.any(np.all(belief.belief.states == actual, axis=1)), ('true cycle not in posterior', game, d, true.hand, list(true.cycle_queue))
            if d in (0, 20, 50, 100, 150, 199):
                roots.append(info)
                sensors.append(sensor)
            if d == 50:
                baseline = info
                original = env.battle
                from differential import snapshot
                before = snapshot(original, r.config)
                for pol in (False, True):
                    a = PublicPlanner(r, prior, k=1, seed=87, policy=pol)
                    aa = a.decide(baseline, 0)
                    env.battle = original.clone()
                    true = env.battle.players[1-game % 2]
                    revealed = {n for _,n in baseline.history}
                    true.deck = sorted(revealed)+[n for n in reversed(r.costs) if n not in revealed][:8-len(revealed)]
                    env.battle.rng = random.Random(12345)
                    changed = observe(env, game % 2)
                    b = PublicPlanner(r, prior, k=1, seed=87, policy=pol)
                    bb = b.decide(changed, 0)
                    assert aa[0] == bb[0] and a.last == b.last
                    assert np.array_equal(aa[1], bb[1])
                    env.battle.players[1-game % 2] = HiddenDenied(true)
                    env.battle.rng = RngDenied()
                    denied = observe(env, game % 2)
                    guard = PublicPlanner(r, prior, k=1, seed=87, policy=pol)
                    assert guard.decide(denied, 0)[0] == aa[0] and guard.last == a.last
                    env.battle = original
                    true = env.battle.players[1-game % 2]
                # A planner cannot read a live battle: no reference is supplied.
                assert not hasattr(r, 'env') and not hasattr(r, 'battle')
                assert snapshot(env.battle, r.config) == before, 'planner mutated live state'
            actions, masks = {}, {}
            for seat in (0, 1):
                packet = observe(env, seat).packet
                actions[seat] = ctx.bot(('balanced','pressure','defense')[game % 3]).select_action(packet)
                masks[seat] = r.mask_builder.build(__import__('clasher.rl.public_action_mask', fromlist=['PublicActionMaskInput']).PublicActionMaskInput.from_confidence_observation(packet))
            with maybe_silence_stdio(True):
                _, done, _ = env.step(actions, pre_action_masks=masks)
            if done:
                break
    (HERE/'results/roots.pkl').write_bytes(pickle.dumps(roots))
    out = dict(non_privilege_k=1, non_privilege_cases=8, forbidden_read_denial_cases=8,
               history_checked_decisions=800, purity=True, costs={})
    for pol in (False, True):
        for k in (1,4,8):
            times = []
            for j, info in enumerate(roots):
                planner = PublicPlanner(r, prior, k=k, seed=990+j, policy=pol)
                # History assimilation is included. Per-game construction is not.
                t, c = time.perf_counter(), time.process_time()
                planner.decide(info, 0)
                times.append(dict(wall=time.perf_counter()-t+sensors[j][0], cpu=time.process_time()-c+sensors[j][1],
                                  calls=planner.calls, tick=info.tick))
            measured = [x for x in times if x['calls']]
            key = ('srp-pub-pol' if pol else 'srp-pub')+f'-k{k}'
            out['costs'][key] = dict(n=len(measured),
                cpu_mean=float(np.mean([x['cpu'] for x in measured])),
                wall_mean=float(np.mean([x['wall'] for x in measured])),
                wall_max=max(x['wall'] for x in measured), samples=times)
            (HERE/'results/check.json').write_text(json.dumps(out, indent=2)+'\n')
            print(key, {k:v for k,v in out['costs'][key].items() if k != 'samples'}, flush=True)
    print('CHECKS PASS', flush=True)


if __name__ == '__main__':
    main()
