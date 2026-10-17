"""Per-card sim smoke for the LIVE translator's true-ids classes (exploration; same smoke as true-ids v1/v2).

    CLASHER_BOT_RUNTIME=<root> CLASHER_BOT_RUNTIME_PINS=<pins> BOT_FULLPOOL_POLICIES=... CLASHER_LOPP_MODELS=... \
    PYTHONHASHSEED=0 python -m bot.fullpool.trueids_smoke OUT.jsonl --cards RoyalGiant,... --games 3 --procs 12

Per card (engine names):
- reference: card / card_action tokens (> 1), true cost, in R.meta (bot/fullpool/packet_check.reference);
- games: our seat = the full-pool bundle search K4L-R-gs-mk1a1 (true ids, open-world belief $BOT_BELIEF_PRIOR, our
  e16 deck) vs R3a (extended) holding a full-pool sampler deck that must contain the card;
- at every scored decision of ours: packet_check.check_information on the planner's Information (entity tokens
  rebuildable, events in R.costs with card_action tokens, history tokens, full-pool belief replay);
- board: the enemy body token names seen in our packets, and for each the first/last tick seen (spawn + lifecycle);
- the opponent's accepted plays of the card (cycle entry), errors, winner, ticks.
PASS for a card = reference ok, >= 1 accepted play of it across its games, a body named like the card (first 5 letters)
seen on board, 0 errors and 0 packet issues. All seen entity names are kept per game for the other forms (pups, eggs).
"""
from __future__ import annotations

import argparse
import json
import os
from multiprocessing import Pool

SPEC = os.environ.get('BOT_BELIEF_PRIOR', 'fullpool:11433651:freq=b53b02a1fde4')
BASE = 1866440789737856   # smoke seeds only: int.from_bytes(os.urandom(6),'big')<<4 on 127x03 2026-10-17 (not an eval bank)


def _rt():
    global _RT
    if '_RT' not in globals():
        import torch
        torch.set_num_threads(1)
        from bot.players.runtime import Runtime
        from bot.fullpool.models import install_from_env
        from bot.fullpool.banks import select
        _RT = Runtime()
        install_from_env(_RT)
        select(_RT, SPEC)
    return _RT


def game(job):
    card, k = job
    rt = _rt()
    from bot.players.ours import play_match
    from bot.eval.headline import make_player
    from bot.fullpool.banks import E16
    from bot.fullpool.decks import Sampler
    from bot.fullpool.packet_check import check_information
    i = sum(map(ord, card)) * 100 + k
    opp_deck = Sampler.from_spec(SPEC).deck(i, salt='trueids-v3', require=[card])
    seat = k % 2
    decks = [list(E16), list(opp_deck)] if seat == 0 else [list(opp_deck), list(E16)]
    names = list(rt.R.builder.token_names)
    issues, seen = [], {}
    row = dict(card=card, game=k, seat=seat, opp_deck=opp_deck, seed=BASE + i)
    try:
        ours = make_player(rt, 'K4L-R-gs-mk1a1')
        orig_start = ours.start

        def start(ctx):
            orig_start(ctx)
            core = ours.p.core
            sc = core.score_candidates

            def score(root, s, cands, **kw):
                info = core.info
                issues.extend(check_information(rt, info, belief_spec=SPEC))
                obs = info.packet.observation
                import numpy as np
                ids = np.asarray(obs.entity_ids).reshape(-1)
                for t in {int(t) for t in ids if t > 1}:
                    n = names[t] if t < len(names) else str(t)
                    a = seen.setdefault(n, [int(info.tick), int(info.tick)])
                    a[1] = int(info.tick)
                return sc(root, s, cands, **kw)
            core.score_candidates = score
        ours.start = start
        players = {seat: ours, 1 - seat: make_player(rt, 'R3a')}
        res = play_match(rt, players, seed=BASE + i, decks=decks, verbose=True)
        log = res.get('play_log', {}).get(1 - seat, [])
        row.update(winner=res['winner'], ticks=res['ticks'], terminal=res['terminal'],
                   card_plays=sum(1 for _, c, _, ok in log if c == card and ok),
                   opp_plays=sum(1 for *_, ok in log if ok))
    except Exception as ex:   # recorded, never dropped
        import traceback
        row.update(error=repr(ex)[:400], tb=traceback.format_exc()[-1200:])
    row.update(packet_issues=len(issues), issue_samples=sorted(set(issues))[:5], seen=seen)
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--cards', required=True)
    ap.add_argument('--games', type=int, default=3)
    ap.add_argument('--procs', type=int, default=12)
    a = ap.parse_args(argv)
    cards = a.cards.split(',')
    from bot.fullpool.packet_check import reference
    ref = reference(_rt(), cards)
    jobs = [(c, k) for c in cards for k in range(a.games)]
    rows = []
    with Pool(a.procs) as pool, open(a.out, 'w') as fh:
        fh.write(json.dumps(dict(reference=ref, runtime=os.environ.get('CLASHER_BOT_RUNTIME_PINS'))) + '\n')
        for r in pool.imap_unordered(game, jobs):
            rows.append(r); fh.write(json.dumps(r) + '\n'); fh.flush()
    summary = {}
    for c in cards:
        rs = [r for r in rows if r['card'] == c]
        rf = ref[c]
        ok_ref = rf['card_token'] > 1 and rf['card_action_token'] > 1 and rf['cost'] is not None and rf['in_meta']
        plays = sum(r.get('card_plays', 0) for r in rs)
        errors = sum('error' in r for r in rs)
        pk = sum(r['packet_issues'] for r in rs)
        pre = c.lower()[:5]
        bodies = {n: [min(r['seen'][n][0] for r in rs if n in r['seen']), max(r['seen'][n][1] for r in rs if n in r['seen'])]
                  for n in sorted({n for r in rs for n in r['seen'] if n.lower().startswith(pre)})}
        summary[c] = dict(reference=rf, ref_ok=ok_ref, games=len(rs), errors=errors, packet_issues=pk, card_plays=plays,
                          bodies_first_last_tick=bodies, wins=[r.get('winner') == r['seat'] for r in rs],
                          PASS=bool(ok_ref and plays >= 1 and bodies and errors == 0 and pk == 0))
    print(json.dumps(summary, indent=1))
    with open(a.out, 'a') as fh:
        fh.write(json.dumps(dict(summary=summary)) + '\n')


if __name__ == '__main__':
    main()
