"""pretrain-v1 featurizer qualification: live-record schema/distribution parity, serving-path equality, hidden-state
and future-suffix mutation suite (PREREG G0: >= 100,000 polls from >= 200 games; >= 10,000 mutation cases, zero
violations).

    python -m bot.pretrain_v1.audit_parity --out reports/bot/pretrain-v1/parity.json [--matches 120] [--workers 16]

  live      every record in /mpac/sdicks02/scratch/live-mem/mirror/mem-c*/m*/records.jsonl must pass the featurizer's
            allow-list unchanged (only the logged `poll` key stripped) and featurise without error; feature
            distributions are summarised next to the re-drive's (live recordings log no unit ids, so their RF unit
            ages are missing, exactly the live translator's missing-extras state).
  serving   for re-drive perspectives, the dataset builder's per-poll feature bytes must equal those produced by
            policy.Session.step (the sim / live entry point) fed the same records, extras and channel verdicts.
  mutation  per perspective, features must be byte-identical after (a) randomising every opponent-private field of
            the raw native frame (elixir, hand, next, queue), (b) randomising non-projectile objects' native target
            fields, (c) replacing all frames after a random cut with another match's frames (prefix polls compared).
"""
from __future__ import annotations

import argparse
import copy
import glob
import gzip
import json
import random
from collections import Counter
from pathlib import Path


from . import dataset as D
from . import featurize as F

LIVE_GLOB = '/mpac/sdicks02/scratch/live-mem/mirror/mem-c*/m*/records.jsonl'


def feature_summary(feats):
    """Scalar summaries comparable across producers."""
    s = Counter()
    for f in feats:
        s['polls'] += 1
        e = f['ent']
        u = e[e[:, F.E_KIND] == 1]
        s['units'] += len(u)
        s['units_opp'] += int((u[:, F.E_OWNER] == 1).sum())
        s['unk_body'] += int((u[:, F.E_BODY] == 1).sum())
        s['unk_card'] += int((u[:, F.E_CARD] == 1).sum())
        s['hp_missing'] += int((u[:, F.E_HP] < 0).sum())
        s['mot_ok'] += int(u[:, F.E_MOT].sum())
        s['carriers'] += int((e[:, F.E_KIND] == 2).sum())
        s['towers_present'] += int(f['tow'][:, F.T_PRESENT].sum())
        s['towers_dead'] += int(((f['tow'][:, F.T_PRESENT] == 1) & (f['tow'][:, F.T_ALIVE] == 0)).sum())
        s['elixir_q'] += int(f['glob'][F.G_ELIXIR])
        s['slot_ok'] += int(f['slot_ok'].sum())
        s['busy'] += int(f['glob'][F.G_BUSY])
        s['ev'] += int(f['ev'][:, F.V_PRESENT].sum())
        s['rev'] += int(f['rev'][:, F.R_PRESENT].sum())
        s['hand_unk'] += int((f['hand'][:4, F.H_CARD] == 1).sum())
    n = max(1, s['polls'])
    out = {k: round(v/n, 4) for k, v in s.items() if k != 'polls'}
    out['polls'] = s['polls']
    return out


def audit_live():
    files = sorted(glob.glob(LIVE_GLOB))
    errs, n_rec, n_files = Counter(), 0, 0
    sample = []
    rng = random.Random(0)
    for p in files:
        h = F.History()
        n_files += 1
        for line in open(p):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                errs['json'] += 1
                continue
            n_rec += 1
            try:
                f = F.observe(r, None, h)
            except F.FeatureError as ex:
                msg = str(ex)[:60]
                errs[msg] += 1
                if 'did not advance' in msg:
                    h = F.History()                   # a logged reader-epoch continuation: new history
                continue
            if rng.random() < .1:
                sample.append(f)
    return dict(files=n_files, records=n_rec, errors=dict(errs), features=feature_summary(sample))


def _match_paths(n, seed=0):
    src = D.SRC
    acked = [b for b in (src/'acked.txt').read_text().split() if (src/'receipts'/f'batch-{b}.json').exists()]
    rng = random.Random(seed)
    keys = []
    for b in acked:
        rec = json.loads((src/'receipts'/f'batch-{b}.json').read_text())
        keys += [(rec['shard'], k) for k in rec['keys']]
    rng.shuffle(keys)
    return keys[:n]


def _load(shard, key, jobs_cache):
    d = json.loads(gzip.open(D.SRC/'out'/shard/f"{key.split(':')[1]}.json.gz").read())
    if d['labels'].get('status') != 'ok' or d['labels'].get('tier') == 'failed' or not d.get('frames'):
        return None, None
    if shard not in jobs_cache:
        jobs_cache.clear()
        with gzip.open(D.JOBS/f'{shard}.jsonl.gz', 'rt') as f:
            jobs_cache[shard] = {json.loads(l)['key']: l for l in f}
    return d, json.loads(jobs_cache[shard][key])


def _trace(d, job, seat):
    rows, stats, tr = D.Rows(), Counter(), []
    D.build_perspective(d, job, seat, rows, stats, 0, -1, 1., trace=tr)
    return tr


def _mutate_private(d, seat, rng):
    d = copy.deepcopy(d)
    other = 1 - seat
    for f in d['frames']:
        for p in f['p']:
            if p[0] == other:
                p[1] = rng.randrange(0, 100001)
                slots = rng.sample(range(8), 5)
                p[2], p[4] = slots[:4], slots[4]
                p[3] = [rng.randrange(26000000, 26000100) for _ in range(4)]
                p[5] = rng.sample(range(8), 4)
        for o in f['o']:
            if not (o[7] and o[7]//1000000 == 10) and len(o) >= 11:
                o[9], o[10] = rng.randrange(0, 18000), rng.randrange(0, 32000)
    return d


def _mutate_suffix(d, donor, rng):
    d = copy.deepcopy(d)
    fr = d['frames']
    cut = rng.randrange(len(fr)//4, max(len(fr)//4 + 1, 3*len(fr)//4))
    cut_tick = fr[cut]['t']
    tail = [copy.deepcopy(f) for f in donor['frames'] if f['t'] > cut_tick]
    d['frames'] = fr[:cut + 1] + tail
    return d, cut_tick


def audit_redrive(n_matches, seed=0):
    from .model import PolicyV1
    from .policy import Session
    import torch
    torch.manual_seed(0)
    model = PolicyV1(d=32, layers=1, heads=2, ffn=64)
    model.eval()
    rng = random.Random(seed)
    jobs = {}
    res = Counter()
    viol = []
    feats = []
    hog = []
    donor = None
    for shard, key in _match_paths(n_matches, seed):
        d, job = _load(shard, key, jobs)
        if d is None:
            res['skipped'] += 1
            continue
        res['matches'] += 1
        for seat in (0, 1):
            base = _trace(d, job, seat)
            if not base:
                continue
            res['perspectives'] += 1
            res['polls'] += len(base)
            # serving path: Session.step on the same records / extras / channel verdicts
            recs, _ = D.project(d, seat, Counter())
            sess = Session(model, 0)
            for (rec, extras), (t, sha, lab, hints) in zip(recs, base):
                sess.step(rec, extras)
                if F.feature_bytes(sess.last_feat) != sha:
                    viol.append(('serving', key, seat, t))
                for card, tile in hints:           # unadmitted human plays (offline only; live plays are submissions)
                    sess.hist.hint_own_tile(card, tile)
                if lab is not None:
                    slot, tile = lab
                    sess.hist.submit(t, slot, rec['hand']['cards'][slot], tile)
                if rng.random() < .02:
                    (hog if 'HogRider' in rec['hand']['cards'] + [rec['hand']['next']] else feats).append(sess.last_feat)
            res['serving_polls'] += len(base)
            # (a)+(b) hidden opponent-private / target mutation
            mut = _trace(_mutate_private(d, seat, rng), job, seat)
            res['mutation_private_cases'] += len(base)
            if [s for _, s, *_ in mut] != [s for _, s, *_ in base]:
                viol.append(('private', key, seat, None))
            # (c) future-suffix mutation (prefix polls compared)
            if donor is not None:
                md, cut_tick = _mutate_suffix(d, donor, rng)
                mt = _trace(md, job, seat)
                pre_b = [s for t, s, *_ in base if t <= cut_tick]
                pre_m = [s for t, s, *_ in mt if t <= cut_tick]
                res['mutation_suffix_cases'] += len(pre_b)
                if pre_b != pre_m:
                    viol.append(('suffix', key, seat, cut_tick))
        donor = d
    feats_all = feats + hog
    return dict(counts=dict(res), violations=viol[:50], n_violations=len(viol),
                features=feature_summary(feats_all), features_hog_hand=feature_summary(hog))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--matches', type=int, default=120)
    ap.add_argument('--skip-live', action='store_true')
    a = ap.parse_args(argv)
    out = dict(schema='clasher.pretrain_v1.parity.v1', feature_hash=F.feature_hash())
    out['redrive'] = audit_redrive(a.matches)
    print(json.dumps(out['redrive']['counts']), out['redrive']['n_violations'], flush=True)
    if not a.skip_live:
        out['live'] = audit_live()
        print(json.dumps({k: v for k, v in out['live'].items() if k != 'features'}), flush=True)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    main()
