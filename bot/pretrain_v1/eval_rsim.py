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
            kept = json.loads(dest.read_text())
            if kept.get('ckpt_sha256') != ck_sha or kept.get('bank_sha256') != bank_sha or kept['seed'] != case['seed']:
                raise SystemExit(f'{dest}: retained row from another checkpoint / bank / case')
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
            issues, invalid = [], []
            if not result['terminal']:
                invalid.append('nonterminal')                 # a failure, never a draw
            if result['channels'][seat]['rejected']:
                issues.append('our command rejections')
            bad = {k: v for k, v in own.counts.items()
                   if k.startswith(('frame_error', 'feature_error', 'unoriented', 'shadow_MISMATCH'))}
            if bad:
                invalid.append(f'projection/contract failure {bad}')
            row.update(invalid=invalid)
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
    """DEV readout over ALL assigned cases of the selected rows (no case is dropped):
    complete-pair mean of policy - search on pairs where both arms produced a valid terminal game; conservative
    intention-to-treat bounds (candidate failures scored as losses / control failures as wins, and the reverse);
    a 20,000-draw PCG64 case bootstrap stratified by opponent controller with fixed equal controller weights, 95% and
    97.5% intervals. DEV / selection evidence only, not a registered confirmation."""
    import numpy as np
    bank = json.loads((R2/'evaluation/bank.json').read_text())
    cases = [c for c in bank['cases'] if c['row'] in a.rows]
    man = json.loads((Path(a.out)/'manifest.json').read_text())
    recs = []
    for c in cases:
        p = Path(a.out)/'rows'/f"{c['index']:04}-{a.arm}.json"
        r = json.loads(p.read_text()) if p.exists() else None
        if r is not None and r.get('ckpt_sha256') != man['ckpt_sha256']:
            raise SystemExit(f'{p}: checkpoint differs from the run manifest')
        q = R2/'screen'/'rows'/f"{c['index']:04}-f1a2.json"
        b = json.loads(q.read_text()) if q.exists() else None
        cand_ok = r is not None and 'score' in r and not r.get('error') and not r.get('invalid')
        ctrl_ok = b is not None and 'score' in b and not b.get('error') and (b.get('result') or {}).get('terminal', True)
        recs.append(dict(index=c['index'], opp=c['opponent'], cand=r['score'] if cand_ok else None,
                         ctrl=b['score'] if ctrl_ok else None, ran=r is not None))
    out = dict(arm=a.arm, assigned=len(recs), ran=sum(x['ran'] for x in recs),
               candidate_failures=sum(x['ran'] and x['cand'] is None for x in recs),
               control_failures=sum(x['ctrl'] is None for x in recs), manifest=man)
    opps = sorted({x['opp'] for x in recs})
    rng = np.random.Generator(np.random.PCG64(2026102021))

    def boot(diffs_by_opp, draws=20000):
        stats = np.zeros(draws)
        for o in opps:
            d = np.array(diffs_by_opp[o])
            if len(d):
                stats += rng.choice(d, size=(draws, len(d))).mean(1)/len(opps)
        return [float(np.quantile(stats, q)) for q in (.0125, .025, .975, .9875)]
    for label, fc, fk in (('complete_pairs', None, None), ('itt_lower', 0.0, 1.0), ('itt_upper', 1.0, 0.0)):
        by = {o: [] for o in opps}
        pol, src = {o: [] for o in opps}, {o: [] for o in opps}
        for x in recs:
            if not x['ran']:
                continue
            cnd = x['cand'] if x['cand'] is not None else fc
            ctl = x['ctrl'] if x['ctrl'] is not None else fk
            if cnd is None or ctl is None:
                continue
            by[x['opp']].append(cnd - ctl)
            pol[x['opp']].append(cnd)
            src[x['opp']].append(ctl)
        if not any(by.values()):
            continue
        q = boot(by)
        out[label] = dict(n=sum(len(v) for v in by.values()),
                          delta=float(np.mean([np.mean(by[o]) for o in opps if by[o]])),
                          ci95=[q[1], q[2]], ci975=[q[0], q[3]],
                          by_opponent={o: dict(n=len(by[o]), policy=float(np.mean(pol[o])), search=float(np.mean(src[o])),
                                               delta=float(np.mean(by[o]))) for o in opps if by[o]})
    rows = [json.loads(p.read_text()) for p in sorted((Path(a.out)/'rows').glob(f'*-{a.arm}.json'))]
    plays = [r.get('n_plays', 0) for r in rows if 'n_plays' in r]
    out['plays_per_game_mean'] = sum(plays)/max(1, len(plays))
    agg = {}
    for r in rows:
        for k, v in (r.get('policy_counts') or {}).items():
            agg[k] = agg.get(k, 0) + v
    out['policy_counts'] = agg
    out['invalid'] = sum(bool(r.get('invalid')) for r in rows)
    out['errors'] = sum('error' in r for r in rows)
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
    sys.path.insert(0, str(REPO_BOT.parent))
    from bot.pretrain_v1 import featurize as F
    man = dict(arm=a.arm, ckpt=a.ckpt, ckpt_sha256=hashlib.sha256(Path(a.ckpt).read_bytes()).hexdigest(),
               bank_sha256=hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest(), rows=a.rows,
               feature_hash=F.feature_hash(), code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                           for p in sorted(HERE.parent.glob('*.py'))})
    mp = out/'manifest.json'
    if mp.exists():
        old = json.loads(mp.read_text())
        if {k: old.get(k) for k in ('arm', 'ckpt_sha256', 'bank_sha256', 'feature_hash')} != \
                {k: man[k] for k in ('arm', 'ckpt_sha256', 'bank_sha256', 'feature_hash')}:
            raise SystemExit('output directory belongs to another run (manifest differs)')
    else:
        mp.write_text(json.dumps(man, indent=1) + '\n')
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
