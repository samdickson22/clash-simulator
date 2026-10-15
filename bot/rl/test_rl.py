"""Parity self-test for bot.rl (run on a GPU host; ~3 short games on CPU).

    BOT_RL_BANK=... CLASHER_BOT_RUNTIME=... $GPU_PY -B -m bot.rl.test_rl [--ticks 1500] [--device cuda]

1. deploy parity: RLPlayer(explore=False) and StudentPlayer('student:<ckpt>@tau0') give the same command hash;
2. log-prob parity: the learner's recomputation (bot.rl.learner.collate/to_dev + bot.rl.dist) of the actor's
   behaviour log-probs, on CPU and on --device, and KL(pi||ref) = 0 at init;
3. explore statistics of one game (decisions, explore vs deploy plays, disagreement).
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ticks', type=int, default=1500)
    ap.add_argument('--device', default='cuda')
    ap.add_argument('--index', type=int, default=7)
    ap.add_argument('--kappa', type=float, default=.5)
    ap.add_argument('--temp', type=float, default=1.)
    a = ap.parse_args()
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.players.policy import PolicyPlayer
    from bot.exit.student import StudentPlayer
    from bot.rl.actor import RLPlayer, RL_BANK, IT5S2, TAU0, check_bank, pack_records
    from bot.rl import dist, learner
    check_bank(RL_BANK)
    rt = Runtime()
    from proposals import load_student
    from exit_r3.student import initialize_root
    case = x4s_setup(rt, a.index, RL_BANK)
    seat = case['seat']
    out = {}

    def game(me):
        return play_match(rt, {seat: me, 1 - seat: PolicyPlayer(rt, 'v1')}, seed=case['seed'], decks=case['decks'],
                          max_ticks=a.ticks)
    base = load_student(IT5S2, TAU0)
    r_ref = game(StudentPlayer.from_spec(rt, f'student:{IT5S2}@{TAU0}'))
    r_dep = game(RLPlayer(rt, base, TAU0, a.kappa, a.temp, False, salt='test'))
    out['deploy_parity'] = r_ref['command_sha256'] == r_dep['command_sha256']
    out['deploy_plays'] = [r_ref['plays'][seat], r_dep['plays'][seat]]
    me = RLPlayer(rt, base, TAU0, a.kappa, a.temp, True, salt='test')
    r_exp = game(me)
    recs = me.records
    out.update(explore_plays=r_exp['plays'][seat], decisions=len(recs),
               sampled_plays=int(sum(r['play'] for r in recs)), deploy_would_play=int(sum(r['deploy'] < 2304 for r in recs)),
               disagree=float(np.mean([r['action'] != r['deploy'] for r in recs])),
               card_or_tile_differs_when_both_play=float(np.mean([r['action'] != r['deploy'] for r in recs
                                                                  if r['play'] and r['deploy'] < 2304] or [0])),
               mean_q=float(np.mean([r['q'] for r in recs])), mean_p=float(np.mean([r['p_play'] for r in recs])))
    arrays = pack_records(recs)
    arrays['meta'] = dict(opponent='v1', outcome=0)
    t = learner.collate([arrays])
    for dev in ('cpu', a.device):
        device = torch.device(dev)
        model, _ = initialize_root(IT5S2)
        model = model.to(device).eval()
        errs, kls = [], []
        with torch.no_grad():
            for s in range(0, len(recs), 256):
                idx = np.arange(s, min(len(recs), s + 256))
                b, x = learner.to_dev(t, idx, device)
                d = dist.explore(dist.forward(model, b), TAU0, a.kappa, a.temp)
                lp = dist.log_prob(d, x['play'], x['slot'].long(), x['tile'].long())
                errs.append(float((lp - x['logp']).abs().max()))
                kls.append(float(dist.kl(d, d).abs().max()))
        if dev == 'cpu':  # how often a sampled play equals the deployed top-1, by temperature
            with torch.no_grad():
                b, x = learner.to_dev(t, np.arange(len(recs)), device)
                raw = dist.forward(model, b)
                dep = torch.from_numpy(t['x_deploy'].astype(np.int64))
                m = dep < 2304
                for T in (1., .5, .3, .2, .1, .05):
                    d = dist.explore(raw, TAU0, a.kappa, T)
                    lp = d['card'][torch.arange(len(dep)), (dep // 576).clamp(0, 3)] + \
                        d['tile'][torch.arange(len(dep)), (dep // 576).clamp(0, 3), dep % 576]
                    out[f'p_top1_given_play_T{T}'] = float(lp[m].exp().mean())
                    out[f'entropy_T{T}'] = float(dist.entropy(d).mean())
        out[f'logp_max_abs_err_{dev}'] = max(errs)
        out[f'kl_self_{dev}'] = max(kls)
    print(json.dumps(out, indent=2))
    assert out['deploy_parity'], 'deployed RL decode differs from StudentPlayer'
    assert out['logp_max_abs_err_cpu'] < 1e-4, 'CPU log-prob recomputation differs'


if __name__ == '__main__':
    main()
