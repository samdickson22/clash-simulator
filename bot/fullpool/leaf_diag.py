"""Leaf-term diagnostics for K4L vl<P> (exploration; BOT LEAD bug check 2026-10-17).

    BOT_LEAF_VALUE=<npz> python -m bot.fullpool.leaf_diag OUT.json --player K4L-R-gs-rw-mk1a1-rh-vl50 --games 4 --procs 4

Plays our engine games (own deck = s62 vs Battle Log decks, opponent K4C-r16 or --opponent) and wraps core.leaf_value so
every leaf the search scores is logged with: our seat, phi = native.evaluate(sim, seat, elixir_weight) (the value the
term is added to), the added term, d_hat for our seat and for the other seat (antisymmetry), the leaf margin
m(seat) from the public view, and the decision id. Feature parity: at the decision ROOT the hook's leaf function is
also evaluated, and compared with bot.value.model.logit on bot.value.gen-style features of the same root.
Summary: per seat (0/1): the mean term, corr(term, phi), corr(d_hat, margin), within-decision std of phi vs of the term
across candidates, antisymmetry error max |d(0) + d(1)|, root parity max |hook - fit-path|.
"""
from __future__ import annotations

import argparse
import json
import os
from multiprocessing import Pool

import numpy as np

S62 = ['Valkyrie', 'Archers', 'Bats', 'Cannon', 'Fireball', 'Zap', 'MiniPekka', 'Giant']


def game(job):
    player, opponent, k, base = job
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import case, select
    from bot.fullpool.models import install_from_env
    from bot.fullpool.leaf_value import margin_pv
    from bot.value.model import ValueModel
    global _RT
    if '_RT' not in globals():
        _RT = Runtime(); install_from_env(_RT); select(_RT, 'bl:' + '+'.join(S62))
    rt = _RT
    c = case(rt, k, base, 'bl:' + '+'.join(S62))
    seat = c['seat']
    model = ValueModel(os.environ['BOT_LEAF_VALUE'])
    leaves, roots, dec = [], [], [0]
    ours = make_player(rt, player)
    orig_start = ours.start

    def start(ctx):
        orig_start(ctx)
        core = ours.p.core
        native, lv = core.native, core.leaf_value
        ew = core.config.elixir_weight

        def logged(sim, s, tick):
            t = lv(sim, s, tick)
            pv = [json.loads(native.public_view(sim, x)) for x in (0, 1)]
            parts = list(native.evaluation_parts(sim))
            leaves.append(dict(dec=dec[0], seat=s, tick=tick, phi=float(native.evaluate(sim, s, ew)), term=float(t),
                               d=float(model.logit(pv, parts, s, tick)), d_other=float(model.logit(pv, parts, 1 - s, tick)),
                               margin=float(margin_pv(pv[s]['towers']))))
            return t
        core.leaf_value = logged
        sc = core.score_candidates

        def score(root, s, cands, **kw):
            dec[0] += 1
            pv = [json.loads(native.public_view(root, x)) for x in (0, 1)]
            tick = int(core.info.tick)
            roots.append(dict(seat=s, hook=float(lv(root, s, tick)),
                              fit=float(model.logit(pv, list(native.evaluation_parts(root)), s, tick))))
            return sc(root, s, cands, **kw)
        core.score_candidates = score
    ours.start = start
    players = {seat: ours, 1 - seat: make_player(rt, opponent)}
    res = play_match(rt, players, seed=c['seed'], decks=c['decks'])
    return dict(k=k, seat=seat, winner=res['winner'], leaves=leaves, roots=roots)


def summarize(games, kappa):
    out = {}
    for s in (0, 1):
        L = [x for g in games for x in g['leaves'] if x['seat'] == s]
        R = [x for g in games for x in g['roots'] if x['seat'] == s]
        if not L:
            continue
        a = lambda k: np.array([x[k] for x in L])
        phi, term, d, do, m = a('phi'), a('term'), a('d'), a('d_other'), a('margin')
        nonterm = np.abs(phi) < 2
        sp, st = [], []
        for g in games:
            decs = {}
            for x in g['leaves']:
                if x['seat'] == s and abs(x['phi']) < 2:
                    decs.setdefault(x['dec'], []).append(x)
            for v in decs.values():
                if len(v) > 2:
                    sp.append(np.std([x['phi'] for x in v])); st.append(np.std([x['term'] for x in v]))
        hook = np.array([x['hook'] for x in R]); fit = np.array([x['fit'] for x in R])
        out[f'seat{s}'] = dict(
            leaves=int(len(L)), decisions=int(sum(1 for g in games for x in g['roots'] if x['seat'] == s)),
            mean_term=round(float(term[nonterm].mean()), 5), mean_d=round(float(d[nonterm].mean()), 5),
            corr_term_phi=round(float(np.corrcoef(term[nonterm], phi[nonterm])[0, 1]), 4),
            corr_d_margin=round(float(np.corrcoef(d[nonterm], m[nonterm])[0, 1]), 4),
            corr_phi_margin=round(float(np.corrcoef(phi[nonterm], m[nonterm])[0, 1]), 4),
            phi_per_margin=round(float(np.polyfit(m[nonterm], phi[nonterm], 1)[0]), 4),
            within_decision_std_phi=round(float(np.median(sp)), 5) if sp else None,
            within_decision_std_term=round(float(np.median(st)), 5) if st else None,
            antisymmetry_max=round(float(np.max(np.abs(d + do))), 8),
            term_equals_kappa_clip_d=round(float(np.max(np.abs(term - kappa * np.clip(d, -1, 1)))), 8),
            root_parity_max=round(float(np.max(np.abs(hook / kappa - np.clip(fit, -1, 1)))), 8) if kappa and len(R) else None)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--player', default='K4L-R-gs-rw-mk1a1-rh-vl50')
    ap.add_argument('--opponent', default='K4C-r16')
    ap.add_argument('--games', type=int, default=4)
    ap.add_argument('--procs', type=int, default=4)
    ap.add_argument('--base', type=int, default=1866440789737856 + 10**7)   # trueids_smoke seed base + offset (smoke only)
    a = ap.parse_args(argv)
    import re
    m = re.search(r'-vl(n?)(\d+)', a.player)
    kappa = (-1 if m[1] else 1) * int(m[2]) / 100
    with Pool(a.procs) as pool:
        games = pool.map(game, [(a.player, a.opponent, k, a.base) for k in range(a.games)])
    res = dict(player=a.player, kappa=kappa, model=os.environ['BOT_LEAF_VALUE'], summary=summarize(games, kappa),
               winners=[(g['seat'], g['winner']) for g in games])
    json.dump(dict(res, games=games), open(a.out, 'w'))
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
