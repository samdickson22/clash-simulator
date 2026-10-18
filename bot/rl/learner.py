"""PPO learner (GPU) for the RL fine-tune of a student; consumes bot.rl.actor rollouts (design: reports/bot/rl/DESIGN.md).

    BOT_GPU_MAX_GB=8 $GPU_PY -B -m bot.rl.learner --run RUN --init IT5S2 [--resume]

Each update: take >= --games-per-update finished games whose policy version is >= current-1 (staler ones are
dropped), recompute critic values, GAE(gamma, lambda) on the terminal outcome, then --epochs of clipped PPO with an
analytic KL(pi || it5s2) penalty on the explore distribution (bot.rl.dist). The first --critic-warmup updates train
only the critic, on Monte-Carlo outcomes, and leave the policy at version 0 (= it5s2). Every update publishes
RUN/policies/policy-<v>.pt in student-checkpoint format (+ .calibration.json at tau0), so 'student:<ckpt>' plays it
with the unchanged deployed decode. Every --snapshot-every policy updates the policy is also copied to RUN/snapshots/
(league opponents + eval queue RUN/evalq/).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from bot.rl.actor import LEAGUE, OPP_IDS, TAU0, TOKEN_KEYS


def save_policy(model, cfg, path, version, extra=None):
    import torch
    sd = {k: v.detach().cpu() for k, v in model.state_dict().items()}
    payload = dict(ema=sd, model=sd, config=asdict(cfg), state=dict(step=version),
                   args=dict(advantage_weight=0., source='bot.rl.learner', **(extra or {})))
    tmp = Path(str(path) + '.partial')
    torch.save(payload, tmp)
    os.replace(tmp, path)
    Path(str(path) + '.calibration.json').write_text(json.dumps(dict(
        threshold=TAU0, method='RL gate centre tau0 (mode of the training policy; bot.rl, reports/bot/rl/DESIGN.md)',
        version=version), indent=2))


def make_critic(trunk_init, width):
    import torch
    from torch import nn
    from exit_r3.student import initialize_root

    class Critic(nn.Module):
        def __init__(self):
            super().__init__()
            self.trunk, _ = initialize_root(trunk_init)
            self.opp = nn.Embedding(len(LEAGUE), width)
            nn.init.zeros_(self.opp.weight)
            self.head = nn.Sequential(nn.Linear(width, width), nn.GELU(), nn.Linear(width, 1))

        def forward(self, b, opp):
            x = self.trunk.encode(b)[:, 0] + self.opp(opp)
            return torch.tanh(self.head(x)).squeeze(-1)
    return Critic()


def load_games(paths):
    games = []
    for p in paths:
        try:
            with np.load(p) as z:
                d = {k: z[k] for k in z.files}
        except Exception as ex:
            print(json.dumps(dict(bad_rollout=str(p), error=repr(ex))), flush=True)
            continue
        d['meta'] = json.loads(bytes(d['meta']).decode())
        games.append(d)
    return games


def collate(games):
    """Concatenate games into one padded transition table (numpy, CPU)."""
    ntok = np.concatenate([g['ntok'] for g in games])
    T, N = int(ntok.max()), len(ntok)
    t = {}
    for k in TOKEN_KEYS:
        first = games[0]['b_' + k]
        arr = np.zeros((N, T, *first.shape[1:]), first.dtype)
        row = 0
        for g in games:
            flat, off = g['b_' + k], np.r_[0, np.cumsum(g['ntok'])]
            for i in range(len(g['ntok'])):
                arr[row, :g['ntok'][i]] = flat[off[i]:off[i + 1]]
                row += 1
        t[k] = arr
    for k in games[0]:
        if k.startswith('b_') and k[2:] not in TOKEN_KEYS:
            t[k[2:]] = np.concatenate([g[k] for g in games])
    for k in ('play', 'slot', 'tile', 'logp', 'p_play', 'q', 'deploy', 'action', 'tick'):
        t['x_' + k] = np.concatenate([g[k] for g in games])
    t['x_opp'] = np.concatenate([np.full(len(g['ntok']), OPP_IDS[g['meta']['opponent']], np.int64) for g in games])
    t['x_game'] = np.concatenate([np.full(len(g['ntok']), i, np.int64) for i, g in enumerate(games)])
    t['x_outcome'] = np.concatenate([np.full(len(g['ntok']), g['meta']['outcome'], np.float32) for g in games])
    t['x_ntok'] = ntok
    t['x_last'] = np.concatenate([np.arange(len(g['ntok'])) == len(g['ntok']) - 1 for g in games])
    return t


def to_dev(t, idx, device):
    import torch
    width = int(t['x_ntok'][idx].max())  # trim padding to this micro-batch's longest row
    b = {k: torch.from_numpy(np.ascontiguousarray(t[k][idx][:, :width] if k in TOKEN_KEYS else t[k][idx]))
         .to(device, non_blocking=True) for k in t if not k.startswith('x_')}
    x = {k[2:]: torch.from_numpy(np.ascontiguousarray(t[k][idx])).to(device) for k in t if k.startswith('x_')}
    return b, x


def gae(values, t, gamma, lam):
    """Per game (rows contiguous, in tick order): terminal reward = outcome at the last decision."""
    adv = np.zeros_like(values)
    last_gae, next_v = 0., 0.
    for i in range(len(values) - 1, -1, -1):
        if t['x_last'][i]:
            r, next_v, last_gae = float(t['x_outcome'][i]), 0., 0.
        else:
            r = 0.
        delta = r + gamma * next_v - values[i]
        last_gae = delta + gamma * lam * last_gae
        adv[i] = last_gae
        next_v = values[i]
    return adv


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--init', required=True)
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--games-per-update', type=int, default=160)
    ap.add_argument('--max-games-per-update', type=int, default=320)
    ap.add_argument('--epochs', type=int, default=3)
    ap.add_argument('--max-lag', type=int, default=1, help='use rollouts from policy versions >= current - this')
    ap.add_argument('--critic-epochs', type=int, default=4, help='epochs during critic warm-up')
    ap.add_argument('--critic-warmup', type=int, default=3)
    ap.add_argument('--minibatch', type=int, default=2048)
    ap.add_argument('--microbatch', type=int, default=512)
    ap.add_argument('--lr', type=float, default=1e-5)
    ap.add_argument('--critic-lr', type=float, default=1e-4)
    ap.add_argument('--clip', type=float, default=.2)
    ap.add_argument('--kl-coef', type=float, default=.05)
    ap.add_argument('--gamma', type=float, default=1.)
    ap.add_argument('--lam', type=float, default=.95)
    ap.add_argument('--kappa', type=float, default=.1)
    ap.add_argument('--temp', type=float, default=.1)
    ap.add_argument('--snapshot-every', type=int, default=10)
    ap.add_argument('--max-updates', type=int, default=10**6)
    ap.add_argument('--keep-versions', type=int, default=4, help='delete consumed rollouts older than this')
    ap.add_argument('--seed', type=int, default=2026101490)
    ap.add_argument('--critic-init', help='critic state_dict to start from (bot.rl.critic_pretrain critic-best.pt); with --resume it resets the critic')
    ap.add_argument('--device', default='cuda')
    a = ap.parse_args(argv)
    from bot.exit.train import bootstrap, sha
    bootstrap()
    import torch
    from exit_r3.student import initialize_root
    from bot.rl import dist
    torch.manual_seed(a.seed)
    torch.set_num_threads(4)  # host CPU budget (lead rule: learner threads <= 8)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    device = torch.device(a.device)
    if device.type == 'cuda' and os.environ.get('BOT_GPU_MAX_GB'):
        total = torch.cuda.get_device_properties(0).total_memory
        torch.cuda.set_per_process_memory_fraction(min(1., float(os.environ['BOT_GPU_MAX_GB']) * 2**30 / total), 0)
    run = a.run
    for sub in ('policies', 'snapshots', 'rollouts', 'evalq', 'used'):
        (run / sub).mkdir(parents=True, exist_ok=True)
    policy, cfg = initialize_root(a.init)
    ref, _ = initialize_root(a.init)
    critic = make_critic(a.init, cfg.width)
    policy, ref, critic = policy.to(device).eval(), ref.to(device).eval(), critic.to(device).eval()
    for p in ref.parameters():
        p.requires_grad_(False)
    opt = torch.optim.AdamW(policy.parameters(), lr=a.lr, weight_decay=0.)
    copt = torch.optim.AdamW(critic.parameters(), lr=a.critic_lr, weight_decay=0.)
    state_path = run / 'learner-state.pt'
    version, update = 0, 0
    # what the saved policy/critic mean: a resume with another anchor, gate centre or league order would silently
    # change the KL reference or re-map the critic's opponent embeddings
    identity = dict(tau0=TAU0, init_sha256=sha(a.init), league=[list(x) for x in LEAGUE])
    if a.resume and state_path.exists():
        st = torch.load(state_path, map_location=device, weights_only=False)
        if 'identity' in st and st['identity'] != identity:   # states written before this check carry none
            raise SystemExit(f"resume identity mismatch: saved {st['identity']} != now {identity}")
        policy.load_state_dict(st['policy']); critic.load_state_dict(st['critic'])
        opt.load_state_dict(st['opt']); copt.load_state_dict(st['copt'])
        version, update = st['version'], st['update']
        for o, lr in ((opt, a.lr), (copt, a.critic_lr)):  # command-line learning rates win on resume
            for g in o.param_groups:
                g['lr'] = lr
        if a.critic_init:  # --resume --critic-init: reset the critic (and its optimizer) to these weights
            critic.load_state_dict(torch.load(a.critic_init, map_location=device, weights_only=True))
            copt = torch.optim.AdamW(critic.parameters(), lr=a.critic_lr, weight_decay=0.)
    elif (run / 'policies' / 'LATEST').exists():
        raise SystemExit('run already has policies; use --resume')
    else:
        if a.critic_init:
            critic.load_state_dict(torch.load(a.critic_init, map_location=device, weights_only=True))
        p0 = run / 'policies' / 'policy-00000.pt'
        save_policy(policy, cfg, p0, 0, dict(init=a.init, init_sha256=sha(a.init)))
        (run / 'policies' / 'LATEST').write_text(f'0 {p0}\n')
        (run / 'learner.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()},
                                                         config=asdict(cfg), init_sha256=sha(a.init), tau0=TAU0,
                                                         league=LEAGUE), indent=2))
    log = open(run / 'train.jsonl', 'a', buffering=1)
    while update < a.max_updates and not (run / 'STOP_LEARNER').exists():
        files = sorted(run.joinpath('rollouts').glob('v*.npz'), key=lambda p: p.stat().st_mtime)
        fresh, stale = [], []
        for f in files:
            (fresh if int(f.name[1:6]) >= version - a.max_lag else stale).append(f)
        for f in stale:
            f.unlink()
        if len(fresh) < a.games_per_update:
            time.sleep(10)
            continue
        t0 = time.time()
        take = fresh[:a.max_games_per_update]
        games = load_games(take)
        games = [g for g in games if g['meta']['opponent'] in OPP_IDS]
        bad = [g['meta']['g'] for g in games if (g['meta'].get('kappa'), g['meta'].get('temp')) != (a.kappa, a.temp)
               or g['meta'].get('tau0', 0.5375) != TAU0]   # rollouts without tau0 predate BOT_RL_TAU0 (0.5375)
        if bad:
            raise SystemExit(f'rollouts with other kappa/temp/tau0 than the learner: {bad[:5]}')
        t = collate(games)
        N = len(t['x_play'])
        warm = update < a.critic_warmup
        # critic values (no grad) -> GAE
        with torch.no_grad():
            values = np.zeros(N, np.float32)
            for s in range(0, N, 2048):
                idx = np.arange(s, min(N, s + 2048))
                b, x = to_dev(t, idx, device)
                values[idx] = critic(b, x['opp']).float().cpu().numpy()
        if warm:
            ret = t['x_outcome'].astype(np.float32)
            adv = ret - values
        else:
            adv = gae(values, t, a.gamma, a.lam).astype(np.float32)
            ret = adv + values
        ev = float(1 - np.var(ret - values) / max(1e-8, np.var(ret)))
        adv_n = (adv - adv.mean()) / (adv.std() + 1e-8)
        t['x_adv'], t['x_ret'] = adv_n.astype(np.float32), ret.astype(np.float32)
        stats = dict(kl=[], clipfrac=[], ratio_dev0=[], vloss=[], ent=[], pg=[])
        rng = np.random.default_rng([a.seed, update])
        epochs = a.critic_epochs if warm else a.epochs
        for ep in range(epochs):
            perm = rng.permutation(N)
            for ms in range(0, N, a.minibatch):
                mb = perm[ms:ms + a.minibatch]
                if len(mb) < a.minibatch // 4:
                    continue
                if not warm:
                    opt.zero_grad(set_to_none=True)
                copt.zero_grad(set_to_none=True)
                for us in range(0, len(mb), a.microbatch):
                    idx = mb[us:us + a.microbatch]
                    b, x = to_dev(t, idx, device)
                    w = len(idx) / len(mb)
                    v = critic(b, x['opp'])
                    vloss = ((v - x['ret']) ** 2).mean()
                    (vloss * w).backward()
                    stats['vloss'].append(float(vloss))
                    if warm:
                        continue
                    d = dist.explore(dist.forward(policy, b), TAU0, a.kappa, a.temp)
                    lp = dist.log_prob(d, x['play'], x['slot'].long(), x['tile'].long())
                    with torch.no_grad():
                        r = dist.explore(dist.forward(ref, b), TAU0, a.kappa, a.temp)
                    k = dist.kl(d, r)
                    ratio = torch.exp(lp - x['logp'])
                    A = x['adv']
                    pg = -torch.min(ratio * A, ratio.clamp(1 - a.clip, 1 + a.clip) * A)
                    loss = (pg + a.kl_coef * k).mean()
                    (loss * w).backward()
                    with torch.no_grad():
                        stats['kl'].append(float(k.mean())); stats['pg'].append(float(pg.mean()))
                        stats['clipfrac'].append(float(((ratio - 1).abs() > a.clip).float().mean()))
                        stats['ent'].append(float(dist.entropy(d).mean()))
                        if ep == 0 and ms == 0:
                            stats['ratio_dev0'].append(float((lp - x['logp']).abs().max()))
                torch.nn.utils.clip_grad_norm_(critic.parameters(), 1.)
                copt.step()
                if not warm:
                    torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.)
                    opt.step()
        update += 1
        if not warm:
            version += 1
            path = run / 'policies' / f'policy-{version:05d}.pt'
            save_policy(policy, cfg, path, version, dict(init=a.init, update=update))
            tmp = run / 'policies' / 'LATEST.partial'
            tmp.write_text(f'{version} {path}\n'); os.replace(tmp, run / 'policies' / 'LATEST')
            if version % a.snapshot_every == 0:
                snap = run / 'snapshots' / f'policy-{version:05d}.pt'
                shutil.copy(path, snap); shutil.copy(str(path) + '.calibration.json', str(snap) + '.calibration.json')
                with open(run / 'snapshots' / 'LIST', 'a') as fh:
                    fh.write(f'{snap}\n')
                (run / 'evalq' / f'policy-{version:05d}').write_text(str(snap) + '\n')
            for old in (run / 'policies').glob('policy-*.pt'):
                ov = int(old.name[7:12])
                if ov < version - a.keep_versions and ov % a.snapshot_every:
                    old.unlink(); Path(str(old) + '.calibration.json').unlink(missing_ok=True)
        for f in take:
            f.unlink(missing_ok=True)
        torch.save(dict(policy=policy.state_dict(), critic=critic.state_dict(), opt=opt.state_dict(),
                        copt=copt.state_dict(), version=version, update=update, identity=identity),
                   str(state_path) + '.partial')
        os.replace(str(state_path) + '.partial', state_path)
        by_opp = {}
        for g in games:
            by_opp.setdefault(g['meta']['opponent'], []).append((g['meta']['outcome'] + 1) / 2)
        metas = [g['meta'] for g in games]
        rec = dict(update=update, version=version, warmup=warm, games=len(games), transitions=N,
                   versions_used=sorted({m['version'] for m in metas}), stale_dropped=len(stale),
                   score=float(np.mean([(m['outcome'] + 1) / 2 for m in metas])),
                   score_by_opp={k: [round(float(np.mean(v)), 3), len(v)] for k, v in sorted(by_opp.items())},
                   plays_per_game=float(np.mean([m['plays'] for m in metas])),
                   deploy_plays_per_game=float(np.mean([m['deploy_plays'] for m in metas])),
                   disagree=float(np.mean([m['disagree'] for m in metas])),
                   p_play=float(t['x_p_play'].mean()), q=float(t['x_q'].mean()),
                   adv_raw_std=float(adv.std()), explained_var=ev, value_mean=float(values.mean()),
                   **{k: (float(np.mean(v)) if v else None) for k, v in stats.items() if k != 'ratio_dev0'},
                   ratio_dev0=max(stats['ratio_dev0']) if stats['ratio_dev0'] else None,
                   wall=time.time() - t0, time=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        log.write(json.dumps(rec) + '\n')
        print(json.dumps(rec), flush=True)


if __name__ == '__main__':
    main()
