"""Parity of the full-pool extensions on C56 inputs: original vs extended model outputs must be bit-identical.

    # 1. record policy inputs (single_features batches) from C56 games; light, one process (05 OK)
    python -m bot.fullpool.parity record --out ROOTS.pt --games 6
    # 2. policy nets: every output tensor of every recorded root, torch.equal; plus the deployed decision
    python -m bot.fullpool.parity policy --roots ROOTS.pt --pair ORIG.pt EXT.pt [--pair ...] [--loader student|v1]
    # 3. K4L rollout-opponent nets on recorded native public views (bot/search/lopp_record.py rec-*.jsonl.gz)
    python -m bot.fullpool.parity lopp --rec REC.jsonl.gz [...] --pair pool.npz poolfp.npz --rows 2000

Recorded games: StudentPlayer(RL r5 v10 original, or --student) vs R3a / v1, on HEADLINE x4s cases and on C56
human-catalog decks chosen to cover all 56 cards (greedy set cover by catalog frequency), so every C56 card token
appears. The hook is a forward pre-hook on each policy module, i.e. exactly the tensors the model is served.
Also reported: the token ids seen in the recorded inputs vs the rows the converter rewrote (must be disjoint).
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import sys
from pathlib import Path

import numpy as np

RL5 = '/mpac/sdicks02/jobs/clasher/bot-fullpool/ckpt/policy-00010.pt@0.5375'


def cover_decks(prior, cards):
    """Greedy set cover of `cards` by catalog decks (highest frequency first among the best gains)."""
    left, out = set(cards), []
    decks = sorted(prior['decks'], key=lambda d: (-d.get('frequency', 1), d['cards']))
    while left:
        best = max(decks, key=lambda d: len(left & set(d['cards'])))
        if not left & set(best['cards']):
            break
        out.append(list(best['cards']))
        left -= set(best['cards'])
    return out


def record(a):
    import torch
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import make_player
    from bot.fullpool.cards import C56
    rt = Runtime()
    roots, seen = [], set()

    def hook(module, args):
        b = args[0]
        roots.append({k: v.detach().clone() for k, v in b.items()})
    from bot.exit.student import load_policy, parse_spec
    student = f'student:{a.student}'
    for m in (rt.POLICY.model, rt.STUDENT.model, load_policy(*parse_spec(student)).model):   # the modules players use
        m.register_forward_pre_hook(hook)
    cover = cover_decks(rt.PRIOR, C56)
    games = [x4s_setup(rt, i, a.base) for i in range(a.games)]
    for k in range(0, len(cover), 2):        # every cover deck plays once (pairs), so all 56 cards appear
        i = a.games + k // 2
        own, other = list(cover[k]), list(cover[(k + 1) % len(cover)])
        rng = random.Random(a.base + i)
        rng.shuffle(own); rng.shuffle(other)
        games.append(dict(seed=a.base + i, seat=i % 2, decks=[own, other] if i % 2 == 0 else [other, own]))
    for i, case in enumerate(games):
        opp = 'R3a' if i % 4 < 2 else 'v1'
        players = {case['seat']: make_player(rt, student), 1 - case['seat']: make_player(rt, opp)}
        n0 = len(roots)
        res = play_match(rt, players, seed=case['seed'], decks=case['decks'])
        seen |= {c for d in case['decks'] for c in d}
        print(json.dumps(dict(game=i, opp=opp, decks=case['decks'], winner=res['winner'], ticks=res['ticks'],
                              roots=len(roots) - n0)), flush=True)
    # keep a uniform deterministic subset
    idx = sorted(random.Random(0).sample(range(len(roots)), min(a.keep, len(roots))))
    keep = [roots[i] for i in idx]
    ids = sorted({int(t) for r in keep for t in r['ids'].flatten().tolist()})
    torch.save(dict(roots=keep, total=len(roots), cards=sorted(seen), ids=ids, games=games), a.out)
    print(json.dumps(dict(out=str(a.out), recorded=len(roots), kept=len(keep), distinct_ids=len(ids),
                          c56_cards_in_decks=len(seen & set(C56)))))


def load_model(path, loader):
    import torch
    if loader == 'v1':
        from imitation.model import load_policy
        model = load_policy(path).model
    else:
        from proposals import load_student
        model = load_student(path).model
    model.eval()
    return model


def compare_policy(a):
    import torch
    from bot.players.runtime import Runtime
    Runtime(verify=False)   # import paths (proposals, imitation) only
    data = torch.load(a.roots, map_location='cpu', weights_only=False)
    roots = data['roots']
    report = dict(roots=len(roots), recorded_ids=len(data['ids']), pairs=[])
    for orig, ext in a.pair:
        rows = json.loads(Path(str(ext) + '.fullpool.json').read_text())['rows']
        rewritten = {r['dst'] for r in rows}
        m0, m1 = load_model(orig, a.loader), load_model(ext, a.loader)
        from proposals import outputs, rank_actions
        diff_tensors, diff_decisions, keys = 0, 0, set()
        with torch.inference_mode():
            for b in roots:
                o0 = m0(b, torch.empty(0, dtype=torch.long))
                o1 = m1(b, torch.empty(0, dtype=torch.long))
                keys |= set(o0)
                if set(o0) != set(o1) or any(not torch.equal(o0[k], o1[k]) for k in o0):
                    diff_tensors += 1
                g0, r0 = outputs(m0, b)
                g1, r1 = outputs(m1, b)
                mask = b['action_mask'][0].numpy()
                d0 = (float(g0[0]), tuple(rank_actions(r0[0].numpy(), mask)[:5]))
                d1 = (float(g1[0]), tuple(rank_actions(r1[0].numpy(), mask)[:5]))
                diff_decisions += d0 != d1
        overlap = sorted(set(data['ids']) & rewritten)
        e0 = m0.card_embed.weight.detach(); e1 = m1.card_embed.weight.detach()
        changed = sorted(int(t) for t in torch.nonzero((e0 != e1).any(1)).flatten())
        report['pairs'].append(dict(orig=str(orig), ext=str(ext), outputs=sorted(keys), roots_with_any_output_diff=diff_tensors,
                                    roots_with_decision_diff=diff_decisions, rewritten_rows=len(rewritten),
                                    changed_rows=len(changed), changed_rows_match_receipt=set(changed) <= rewritten,
                                    recorded_ids_in_rewritten=overlap,
                                    PASS=diff_tensors == 0 and diff_decisions == 0 and not overlap))
    print(json.dumps(report, indent=1))
    return all(p['PASS'] for p in report['pairs'])


def compare_lopp(a):
    from bot.search.lopp_feat import NumpyOpponent, featurize
    views = []
    for f in a.rec:
        with gzip.open(f, 'rt') as fh:
            for line in fh:
                g = json.loads(line)
                for row in g['rows']:
                    views.append((row[0], row[3]))
    rng = random.Random(0)
    views = [views[i] for i in sorted(rng.sample(range(len(views)), min(a.rows, len(views))))]
    report = dict(rows=len(views), pairs=[])
    for orig, ext in a.pair:
        m0, m1 = NumpyOpponent(orig), NumpyOpponent(ext)
        nb = len(m0.vocab)
        bad = dict(features=0, gate=0, logits=0, decision=0, tiles=0)
        X0, C0, X1, C1 = [], [], [], []
        for tick, vj in views:
            v = json.loads(vj)
            x0, h0 = featurize(v, tick, m0.cost_of)
            x1, h1 = featurize(v, tick, m1.cost_of)
            bad['features'] += not (np.array_equal(x0, x1) and h0 == h1)
            X0.append(x0); X1.append(x1)
            C0.append([m0.vocab.get(t, 0) for t in h0]); C1.append([m1.vocab.get(t, 0) for t in h1])
        X0, X1, C0, C1 = map(np.asarray, (X0, X1, C0, C1))
        bad['card_index'] = int((C0 != C1).sum())
        for mode in ('rowwise', 'batched'):
            if mode == 'rowwise':
                h0 = np.concatenate([m0.trunk(X0[r:r+1], C0[r:r+1]) for r in range(len(X0))])
                h1 = np.concatenate([m1.trunk(X1[r:r+1], C1[r:r+1]) for r in range(len(X1))])
                hd0 = [m0.heads(h0[r:r+1]) for r in range(len(X0))]; hd1 = [m1.heads(h1[r:r+1]) for r in range(len(X1))]
                g0, v0 = np.concatenate([g for g, _ in hd0]), np.concatenate([v for _, v in hd0])
                g1, v1 = np.concatenate([g for g, _ in hd1]), np.concatenate([v for _, v in hd1])
            else:
                h0, h1 = m0.trunk(X0, C0), m1.trunk(X1, C1)
                (g0, v0), (g1, v1) = m0.heads(h0), m1.heads(h1)
            key = f'{mode}_'
            bad[key + 'trunk'] = int((h0 != h1).any(1).sum())
            bad[key + 'gate'] = int((g0 != g1).any(1).sum())
            bad[key + 'logits_base'] = int((v0 != v1[:, :nb]).any(1).sum())
            hand0 = np.take_along_axis(v0, C0, 1); hand1 = np.take_along_axis(v1, C1, 1)
            bad[key + 'hand_logits'] = int((hand0 != hand1).any(1).sum())
            bad[key + 'card_argmax'] = int((hand0.argmax(1) != hand1.argmax(1)).sum())
            t_bad = 0
            for r in range(len(X0)):
                for s in range(4):
                    t0 = m0.tiles(h0[r:r+1], C0[r:r+1, s])[0]; t1 = m1.tiles(h1[r:r+1], C1[r:r+1, s])[0]
                    t_bad += not np.array_equal(t0, t1)
            bad[key + 'tile_logits'] = t_bad
        bad.pop('gate'); bad.pop('logits'); bad.pop('decision'); bad.pop('tiles')
        report['pairs'].append(dict(orig=str(orig), ext=str(ext), base_vocab=nb, ext_vocab=len(m1.vocab),
                                    mismatches=bad, PASS=not any(bad.values())))
    print(json.dumps(report, indent=1))
    return all(p['PASS'] for p in report['pairs'])


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record')
    r.add_argument('--out', required=True, type=Path)
    r.add_argument('--games', type=int, default=4, help='HEADLINE x4s cases; cover-deck games are added')
    r.add_argument('--keep', type=int, default=600)
    r.add_argument('--base', type=int, default=1455777415631152)
    r.add_argument('--student', default=RL5)
    p = sub.add_parser('policy')
    p.add_argument('--roots', required=True, type=Path)
    p.add_argument('--pair', nargs=2, action='append', required=True, type=Path)
    p.add_argument('--loader', default='student', choices=['student', 'v1'])
    k = sub.add_parser('lopp')
    k.add_argument('--rec', nargs='+', required=True, type=Path)
    k.add_argument('--pair', nargs=2, action='append', required=True, type=Path)
    k.add_argument('--rows', type=int, default=2000)
    a = ap.parse_args(argv)
    if a.cmd == 'record':
        record(a)
        return
    ok = compare_policy(a) if a.cmd == 'policy' else compare_lopp(a)
    print('PARITY', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
