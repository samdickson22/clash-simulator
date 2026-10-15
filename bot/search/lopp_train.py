"""Train the learned rollout opponent on recorded v1/R3a decisions (exploration).

    python -m bot.search.lopp_train --rec DIR[,DIR] --out MODELDIR --name pool [--opponents R3a,v1] [--epochs 8]

Data: bot/search/lopp_record.py rows (native public_view of the opponent's own seat at every free poll + the
action it took). Split by case index (index % 10 == 9 -> validation). Heads: play gate (BCE, all polls), card
among the legal hand slots (CE, plays), tile among the slot's legal tiles (CE, plays). The play threshold tau is
the train-set quantile of P(play) that reproduces the empirical per-poll play rate (as R3a's calibrated gate).
Exports <name>.npz (numpy forward in lopp_feat.NumpyOpponent) and <name>.json (validation metrics).
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
from multiprocessing import Pool
from pathlib import Path

import numpy as np


def load_file(args):
    path, opponents, cost_of = args
    from bot.search.lopp_feat import featurize
    out = []
    for line in gzip.open(path, 'rt'):
        g = json.loads(line)
        if g['opponent'] not in opponents:
            continue
        for tick, a, wt, vj, mhex, legal in g['rows']:
            x, hand = featurize(json.loads(vj), tick, cost_of)
            play = a < 2304 and bool(legal)
            mask = np.unpackbits(np.frombuffer(bytes.fromhex(mhex), np.uint8))[:2304].astype(bool) if play else None
            out.append((g['index'], g['opponent'], x, hand, a if play else 2304, mask, tick))
    return out


def card_meta():
    from bot.players.runtime import Runtime
    rt = Runtime(verify=False)
    meta = rt.R.meta
    cards = meta['cards'] if isinstance(meta, dict) else json.loads(meta)['cards']
    toks = sorted({int(c['token']) for c in cards.values()})
    cost = {int(c['token']): float(c['cost']) for c in cards.values()}
    return toks, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rec', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--name', required=True)
    ap.add_argument('--opponents', default='R3a,v1')
    ap.add_argument('--epochs', type=int, default=8)
    ap.add_argument('--hidden', type=int, default=256)
    ap.add_argument('--dropout', type=float, default=0.3)
    ap.add_argument('--threads', type=int, default=16)
    ap.add_argument('--procs', type=int, default=16)
    ap.add_argument('--layers', type=int, default=2, choices=[2, 3], help='trunk depth (3 adds W3/b3)')
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--bs', type=int, default=1024)
    a = ap.parse_args()
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)
    toks, cost_of = card_meta()
    vocab_tokens = [0] + toks
    vocab = {t: i for i, t in enumerate(vocab_tokens)}
    opponents = set(a.opponents.split(','))
    files = sorted(p for d in a.rec.split(',') for p in Path(d).glob('rec-*.jsonl.gz'))
    with Pool(a.procs) as pool:
        rows = [r for part in pool.map(load_file, [(f, opponents, cost_of) for f in files]) for r in part]
    val = np.array([r[0] % 10 == 9 for r in rows])
    if not val.any():   # smoke runs: hold out every 10th row instead
        val = np.arange(len(rows)) % 10 == 9
    X = np.stack([r[2] for r in rows]).astype(np.float32)
    C = np.array([[vocab.get(t, 0) for t in r[3]] for r in rows], np.int64)
    A = np.array([r[4] for r in rows], np.int64)
    play = A < 2304
    # legal masks only for plays (a dense rows x 2304 mask is 5.5 GB at 2.4M rows); MI = row -> mask index
    MI = np.full(len(rows), -1, np.int64)
    MI[play] = np.arange(int(play.sum()))
    M = np.zeros((int(play.sum()), 2304), bool)
    for i in np.flatnonzero(play):
        M[MI[i]] = rows[i][5]
    rows = [(r[0], r[1]) for r in rows]      # free the per-row arrays (X, C, A, M hold everything else)
    mu = X[~val].mean(0)
    sd = X[~val].std(0)
    sd[sd < 1e-3] = 1.
    print(json.dumps(dict(rows=len(rows), plays=int(play.sum()), val_rows=int(val.sum()),
                          play_rate=float(play[~val].mean()))), flush=True)

    V, D, E, H = len(vocab_tokens), X.shape[1], 16, a.hidden

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.emb = nn.Embedding(V, E)
            self.l1 = nn.Linear(D, H)
            self.l1c = nn.Linear(4 * E, H, bias=False)
            self.l2 = nn.Linear(H, H)
            self.l3 = nn.Linear(H, H) if a.layers == 3 else None
            self.g = nn.Linear(H, 1)
            self.v = nn.Linear(H, V)
            self.t = nn.Linear(H, H)
            self.tem = nn.Embedding(V, H)
            self.o = nn.Linear(H, 576)

        def trunk(self, x, c):
            h = F.dropout(F.relu(self.l1(x) + self.l1c(self.emb(c).flatten(1))), a.dropout, self.training)
            h = F.dropout(F.relu(self.l2(h)), a.dropout, self.training)
            return h if self.l3 is None else F.dropout(F.relu(self.l3(h)), a.dropout, self.training)

        def tiles(self, h, card):
            return self.o(F.relu(self.t(h) + self.tem(card)))

    net = Net()
    opt = torch.optim.Adam(net.parameters(), lr=a.lr, weight_decay=1e-5)
    Xt = torch.from_numpy((X - mu) / sd)
    Ct, At, Pt, Mt, MIt = (torch.from_numpy(C), torch.from_numpy(A), torch.from_numpy(play), torch.from_numpy(M),
                           torch.from_numpy(MI))
    tr = np.flatnonzero(~val)
    va = np.flatnonzero(val)

    def losses(idx):
        idx = torch.from_numpy(idx)
        x, c, act, p = Xt[idx], Ct[idx], At[idx], Pt[idx]
        h = net.trunk(x, c)
        lg = F.binary_cross_entropy_with_logits(net.g(h)[:, 0], p.float())
        out = dict(gate=lg)
        if p.any():
            hp, cp, ap_, mp = h[p], c[p], act[p], Mt[MIt[idx][p]].view(-1, 4, 576)
            slot = ap_ // 576
            legal = mp.any(-1)
            vl = net.v(hp).gather(1, cp)
            vl = vl.masked_fill(~legal, -1e9)
            out['card'] = F.cross_entropy(vl, slot)
            card = cp.gather(1, slot[:, None])[:, 0]
            tl = net.tiles(hp, card).masked_fill(~mp[torch.arange(len(slot)), slot], -1e9)
            out['tile'] = F.cross_entropy(tl, ap_ % 576)
            out['_vl'], out['_tl'], out['_slot'], out['_tile'] = vl, tl, slot, ap_ % 576
        return out

    bs = a.bs
    rng = np.random.default_rng(0)
    best = None
    for ep in range(a.epochs):
        net.train()
        perm = rng.permutation(tr)
        tot = {}
        for s in range(0, len(perm), bs):
            o = losses(perm[s:s + bs])
            loss = o['gate'] + o.get('card', 0.) + o.get('tile', 0.)
            opt.zero_grad(); loss.backward(); opt.step()
            for k in ('gate', 'card', 'tile'):
                if k in o:
                    tot[k] = tot.get(k, 0.) + float(o[k].detach()) * len(perm[s:s + bs])
        net.eval()
        with torch.no_grad():
            vo = losses(va)
            vloss = float(vo['gate'] + vo.get('card', 0.) + vo.get('tile', 0.))
        print(json.dumps(dict(epoch=ep, **{k: v / len(perm) for k, v in tot.items()},
                              val={k: float(vo[k]) for k in ('gate', 'card', 'tile') if k in vo})), flush=True)
        if best is None or vloss < best[0]:
            best = (vloss, ep, copy.deepcopy(net.state_dict()))
    net.load_state_dict(best[2])
    print(json.dumps(dict(best_epoch=best[1], best_val=best[0])), flush=True)

    net.eval()
    with torch.no_grad():
        ptr = torch.cat([torch.sigmoid(net.g(net.trunk(Xt[torch.from_numpy(tr[s:s+8192])],
                         Ct[torch.from_numpy(tr[s:s+8192])]))[:, 0]) for s in range(0, len(tr), 8192)]).numpy()
        rate = float(play[tr].mean())
        tau = float(np.quantile(ptr, 1 - rate))
        metrics = dict(rows=len(rows), train=len(tr), val=len(va), play_rate=rate, tau=tau, best_epoch=best[1])
        for who in sorted(opponents) + ['all']:
            sel = va if who == 'all' else va[np.array([rows[i][1] == who for i in va], dtype=bool)]
            if not len(sel):
                continue
            hv = net.trunk(Xt[torch.from_numpy(sel)], Ct[torch.from_numpy(sel)])
            pv = torch.sigmoid(net.g(hv)[:, 0]).numpy()
            y = play[sel]
            pred = pv >= tau
            order = np.argsort(pv)
            ranks = np.empty(len(pv)); ranks[order] = np.arange(len(pv))
            auc = float((ranks[y].mean() - (y.sum() - 1) / 2) / max(1, (~y).sum())) if y.any() and (~y).any() else None
            o = losses(sel)
            m = dict(n=len(sel), plays=int(y.sum()), play_rate=float(y.mean()), pred_rate=float(pred.mean()),
                     gate_auc=auc, gate_acc=float((pred == y).mean()),
                     gate_recall=float(pred[y].mean()) if y.any() else None,
                     gate_precision=float(y[pred].mean()) if pred.any() else None,
                     gate_nll=float(o['gate']))
            if 'card' in o:
                slot, tile = o['_slot'].numpy(), o['_tile'].numpy()
                card_hit = o['_vl'].argmax(1).numpy() == slot
                tp = o['_tl'].argmax(1).numpy()
                dx = np.abs(tp % 18 - tile % 18); dy = np.abs(tp // 18 - tile // 18)
                m.update(card_top1=float(card_hit.mean()), card_nll=float(o['card']), tile_top1=float((tp == tile).mean()),
                         tile_within1=float((np.maximum(dx, dy) <= 1).mean()),
                         tile_within2=float((np.maximum(dx, dy) <= 2).mean()), tile_nll=float(o['tile']),
                         card_and_tile2=float((card_hit & (np.maximum(dx, dy) <= 2)).mean()))
            metrics[who] = m
    print(json.dumps(metrics, indent=1), flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    sd_ = {k: v.detach().numpy() for k, v in net.state_dict().items()}
    np.savez(a.out / f'{a.name}.npz',
             emb=sd_['emb.weight'], W1=sd_['l1.weight'].T.copy(), b1=sd_['l1.bias'], W1c=sd_['l1c.weight'].T.copy(),
             W2=sd_['l2.weight'].T.copy(), b2=sd_['l2.bias'],
             **({} if a.layers == 2 else dict(W3=sd_['l3.weight'].T.copy(), b3=sd_['l3.bias'])), wg=sd_['g.weight'].T.copy(), bg=sd_['g.bias'],
             Wv=sd_['v.weight'].T.copy(), bv=sd_['v.bias'], Wt=sd_['t.weight'].T.copy(), bt=sd_['t.bias'],
             tem=sd_['tem.weight'], Wo=sd_['o.weight'].T.copy(), bo=sd_['o.bias'],
             meta_vocab=np.array(vocab_tokens, np.int64), meta_cost=np.array([cost_of.get(t, 0.) for t in vocab_tokens]),
             meta_tau=np.array(tau), meta_mu=mu.astype(np.float32), meta_sd=sd.astype(np.float32))
    (a.out / f'{a.name}.json').write_text(json.dumps(dict(metrics, args=vars(a) | dict(out=str(a.out))), indent=1))

    # numpy forward must match torch
    from bot.search.lopp_feat import NumpyOpponent
    npm = NumpyOpponent(a.out / f'{a.name}.npz')
    idx = va[:64]
    with torch.no_grad():
        ht = net.trunk(Xt[torch.from_numpy(idx)], Ct[torch.from_numpy(idx)])
        gt = net.g(ht)[:, 0].numpy()
    hn = npm.trunk(X[idx], C[idx])
    gn = npm.heads(hn)[0][:, 0]
    print('numpy-vs-torch gate max diff', float(np.abs(gn - gt).max()), flush=True)


if __name__ == '__main__':
    main()
