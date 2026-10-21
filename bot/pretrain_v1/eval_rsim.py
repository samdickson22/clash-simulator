"""Offline evaluation hook (a): pretrain-v1 policy-only arm on the rl-search-prior-20261020-r2 paired bank.

Same harness, bank, opponents, levels and seeds as r2 (RoyaleSim 16.402, account levels on the HOG26-acct row,
opponents LIVE-K4CW-r16-fp / R3a constructed exactly as screen_r2.py does). Only the own seat changes: the
current live search (r2 arm f1a2, rows already sealed in r2/screen/rows/NNNN-f1a2.json) is replaced by
sim_rsim.PolicyV1Player. Pairing is by identical initial conditions (deck order, levels, seat, opponent, seed), not
by trajectory. Every attempted case gets a sealed row (no retries); errors stay rows.

    R2=/mpac/sdicks02/scratch/rl-search-prior-20261020-r2
    $R2/run.sh /mpac/sdicks02/repos/clasher-pretrain-v1/bot/pretrain_v1/eval_rsim.py \
        --ckpt CKPT --out DIR --rows HOG26-acct --workers 16 [--limit N] [--arm NAME]
    ... eval_rsim.py --summarise --out DIR
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_BOT = HERE.parents[1]
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')
GiB = 1024**3


def mem_available():
    return int(next(l.split()[1] for l in open('/proc/meminfo') if l.startswith('MemAvailable:')))*1024


def dump(path, row):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(row))
    tmp.replace(path)


def setup():
    sys.path.insert(0, str(R2))
    import eval_setup
    import bot
    bot.__path__.append(str(REPO_BOT))             # bot.pretrain_v1 from this repo next to r2's code tree
    eval_setup.sim_modules()
    import fullpool_eval as fp
    fp.MODEL_ROOT = R2/'evaluation/models'
    fp.FAST = f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
    fp.OLD_FAST = f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'
    return fp


def worker(wid, workers, a, cases):
    import torch
    torch.set_num_threads(1)
    fp = setup()
    from screen_r2 import runtime
    from bot.livediag.k4cw_fp import make_k4cw_fp
    from bot.eval.headline import make_player
    from bot.players.royalesim_match import play_match
    from bot.pretrain_v1.policy import load
    from bot.pretrain_v1.sim_rsim import PolicyV1Player
    import importlib.util
    spec = importlib.util.spec_from_file_location('eval_profile', R2/'rl-source/bot/levels/profile.py')
    profile = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = profile
    spec.loader.exec_module(profile)
    rt = runtime()
    vocab = json.loads((R2/'evaluation/vocab-full.json').read_text())
    model, ck = load(a.ckpt)
    ck_sha = hashlib.sha256(Path(a.ckpt).read_bytes()).hexdigest()
    bank_sha = hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest()
    out = Path(a.out)
    for pos, case in enumerate(cases):
        if pos % workers != wid:
            continue
        dest = out/'rows'/f"{case['index']:04}-{a.arm}.json"
        if dest.exists():
            continue
        marker = dest.with_suffix('.attempt')
        if marker.exists():
            dump(dest, dict(json.loads(marker.read_text()), error='interrupted attempt (no sealed row)'))
            continue
        while mem_available() <= 28*GiB or os.getloadavg()[0] > 90:
            print('ADMISSION_HOLD', wid, case['index'], flush=True)
            time.sleep(15)
        row = dict(case, arm=a.arm, ckpt=a.ckpt, ckpt_sha256=ck_sha, bank_sha256=bank_sha, host=os.uname().nodename,
                   started=time.time(), pid=os.getpid())
        dump(marker, row)
        t = time.monotonic()
        try:
            seat = case['seat']
            own = PolicyV1Player(rt, model, name=f'pretrain-v1:{a.arm}')
            if case['opponent'] == 'LIVE-K4CW-r16-fp':
                other = fp.Observed(make_k4cw_fp(rt, fp.FAST), 'strong full-pool', 'FullPoolBelief',
                                    fp.FAST.split(':', 1)[1])
            else:
                other = fp.Observed(make_player(rt, case['opponent']), f"full-pool {case['opponent']}")
            other.rec.act = other.rec.inner.act
            players = {seat: own, 1 - seat: other}
            decks = [case['own_deck'], case['opponent_deck']]
            otherlevels = {c: max(profile.FLOOR.get(profile.rarity(rt, c), 1), int(l))
                           for c, l in case['opponent_levels'].items()}
            levels = [case['own_levels'], otherlevels]
            towers = [case['own_king'], case['opponent_king']]
            if seat == 1:
                decks.reverse()
                levels.reverse()
                towers.reverse()
            result = play_match(rt, players, seed=case['seed'], decks=decks, vocab=vocab, client='16.402',
                                levels=levels, tower_levels=towers, verbose=True)
            issues = []
            if not result['terminal']:
                issues.append('nonterminal')
            if result['channels'][seat]['rejected']:
                issues.append('our command rejections')
            row.update(result=result, score=.5 if result['winner'] is None else float(result['winner'] == seat),
                       win=int(result['winner'] == seat), draw=int(result['winner'] is None), issues=issues,
                       policy_counts=own.counts, frame_stats=own.frames.stats, n_plays=len(own.decisions))
        except BaseException as ex:
            row.update(error=repr(ex), traceback=traceback.format_exc())
        row['seconds'] = time.monotonic() - t
        dump(dest, row)
        marker.unlink()
        print('ROW', wid, case['index'], row.get('score'), row.get('issues'), row.get('error'), round(row['seconds'], 1),
              flush=True)
        players = own = other = result = row = None
        gc.collect()


def summarise(a):
    import math
    rows = {}
    for p in sorted((Path(a.out)/'rows').glob(f'*-{a.arm}.json')):
        r = json.loads(p.read_text())
        rows[r['index']] = r
    base = {}
    for i in rows:
        p = R2/'screen'/'rows'/f'{i:04}-f1a2.json'
        if p.exists():
            base[i] = json.loads(p.read_text())
    pairs = [(rows[i], base[i]) for i in sorted(rows) if i in base and 'score' in rows[i] and 'score' in base[i]
             and not base[i].get('error')]
    out = dict(arm=a.arm, rows=len(rows), errors=sum('error' in r for r in rows.values()), pairs=len(pairs))
    by = {}
    for r, b in pairs:
        for key in ('all', f"{r['row']}", f"{r['row']}|{r['opponent']}"):
            by.setdefault(key, []).append((r['score'], b['score']))
    rng = random.Random(2026102021)
    for key, v in sorted(by.items()):
        d = [x - y for x, y in v]
        mean = sum(d)/len(d)
        boots = sorted(sum(d[rng.randrange(len(d))] for _ in d)/len(d) for _ in range(4000))
        out[key] = dict(n=len(v), policy=sum(x for x, _ in v)/len(v), search=sum(y for _, y in v)/len(v), delta=mean,
                        ci95=[boots[100], boots[3899]],
                        se=math.sqrt(sum((x - mean)**2 for x in d)/max(1, len(d) - 1)/len(d)))
    plays = [r.get('n_plays', 0) for r in rows.values() if 'n_plays' in r]
    out['plays_per_game_mean'] = sum(plays)/max(1, len(plays))
    agg = {}
    for r in rows.values():
        for k, v in (r.get('policy_counts') or {}).items():
            agg[k] = agg.get(k, 0) + v
    out['policy_counts'] = agg
    out['issues'] = sum(bool(r.get('issues')) for r in rows.values())
    (Path(a.out)/f'summary-{a.arm}.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt')
    ap.add_argument('--out', required=True)
    ap.add_argument('--arm', default='pv1')
    ap.add_argument('--rows', nargs='+', default=['HOG26-acct'])
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--summarise', action='store_true')
    a = ap.parse_args()
    if a.summarise:
        return summarise(a)
    out = Path(a.out)
    (out/'rows').mkdir(parents=True, exist_ok=True)
    bank = json.loads((R2/'evaluation/bank.json').read_text())
    cases = [c for c in bank['cases'] if c['row'] in a.rows]
    if a.limit:
        cases = cases[:a.limit]
    while mem_available() < (28 + 1.5*a.workers)*GiB or os.getloadavg()[0] + a.workers > 90:
        print('PARENT_ADMISSION_HOLD', flush=True)
        time.sleep(30)
    children = []
    for w in range(a.workers):
        pid = os.fork()
        if pid == 0:
            try:
                worker(w, a.workers, a, cases)
            except BaseException:
                traceback.print_exc()
                os._exit(1)
            os._exit(0)
        children.append(pid)
    for pid in children:
        os.waitpid(pid, 0)


if __name__ == '__main__':
    main()
