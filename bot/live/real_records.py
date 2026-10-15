"""Real perception output vs its ground truth, through the translator and the bot (LIVE track, exploration).

    python -m bot.live.real_records --tier fast|search --out DIR [--records DIR]

Input: the perception owner's sample records (validation matches; one line per processed frame:
{episode, seq, tick, pred, truth}; pred = LivePerception frame_record, truth = the same schema from the labels).
The bot plays OUR seat of the recorded match (the recorded side's own commands are not ours).

Arms (each its own LiveTranslator + LivePlayer, same seeds, polled at the same 5-tick polls):
  truth          truth records, every play from the truth events (the reference)
  truth-births   truth units, opponent plays derived from births (upper bound of the births method on these frames)
  pred-births    perception output, opponent plays from births
  pred-head      perception output, opponent plays from the perception's temporal head (pred.events)
  reseed         (search tier) truth input, seeds +7: the bot's own noise floor
Our own plays come from the truth events in every arm (live: from our own commands).
Ticks: every arm gets the poll tick (as LiveSession does); the HUD-clock path is scored separately (clock rows).

Outputs: agreement.jsonl (bot.live.summarize agreement), plays.json (opponent-play recall/precision per source:
a derived play matches a true play of the same card within 3 tiles and -10..+60 ticks), clock.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

RECORDS = Path('/mpac/sdicks02/jobs/clasher/live-perception-20261014/sample-records')
TICK_MS = 50.


def unique_plays(rows, key='truth'):
    seen = {}
    for r in rows:
        for e in r[key]['events']:
            k = (e['owner'], e['card'], round(e['x'], 1), round(e['y'], 1), round(e['tick']))
            seen.setdefault(k, dict(owner=e['owner'], card=e['card'], x=e['x'], y=e['y'], tick=e['tick']/TICK_MS))
    return sorted(seen.values(), key=lambda e: e['tick'])


def match_plays(derived, truth, owner=1, tiles=3., lo=-10, hi=60):
    import math
    T = [t for t in truth if t['owner'] == owner]
    D = [d for d in derived if d['owner'] == owner]
    used, tp = set(), 0
    for d in D:
        best = None
        for i, t in enumerate(T):
            if i in used or t['card'] != d['card']:
                continue
            dt = d['tick'] - t['tick']
            if lo <= dt <= hi and math.hypot(d['x']-t['x'], d['y']-t['y']) <= tiles:
                if best is None or abs(dt) < abs(T[best]['tick'] - d['tick']):
                    best = i
        if best is not None:
            used.add(best)
            tp += 1
    return dict(true=len(T), derived=len(D), matched=tp, recall=tp/max(1, len(T)), precision=tp/max(1, len(D)))


def run_match(rt, path, tier, out, arms):
    from bot.players.base import MatchContext, PublicView, POLICY_INTERVAL, START_TICK, WAIT
    from bot.live.translate import LiveTranslator
    from bot.live.births import ClockTracker
    from bot.live.replay import make_live
    from dataclasses import replace
    rows = [json.loads(l) for l in open(path) if l.strip()]
    ep = rows[0]['episode']
    truth_plays = unique_plays(rows)
    own_truth = [e for e in truth_plays if e['owner'] == 0]
    hud = rows[0]['truth']['hand']
    deck = list(dict.fromkeys(c for r in rows for c in r['truth']['hand']['cards'] + [r['truth']['hand']['next']] if c))
    assert len(deck) == 8, (ep, deck)
    order = list(hud['cards']) + ([hud['next']] if hud['next'] not in hud['cards'] else [])
    order += [c for c in deck if c not in order]
    ctx = MatchContext(seat=0, seed=int(ep.rsplit('-', 1)[-1]), own_order=tuple(order))
    state = {}
    for a in arms:
        p = make_live(rt, tier, None, 1)
        p.start(replace(ctx, seed=ctx.seed + 7) if a == 'reseed' else ctx)
        tr = LiveTranslator(rt, deck, plays_from='events' if a in ('truth', 'reseed', 'pred-head') else 'births')
        tr.set_own_order(order)
        state[a] = dict(player=p, tr=tr, buf=[], errors=0)
    out_rows, last_poll, t0 = [], None, time.time()
    clocks = {k: ClockTracker() for k in ('pred', 'truth')}
    clock_err = {k: [] for k in clocks}
    for r in rows:
        for k, c in clocks.items():
            clock_err[k].append(c(r[k]['clock_s'], r[k]['phase'], r[k]['timestamp_ms']) - r['tick'])
        tick = int(r['tick'])
        frame_own = [dict(e, tick=round(e['tick'])) for e in own_truth if e['tick'] <= tick]
        for a, st in state.items():
            src = r['pred'] if a.startswith('pred') else r['truth']
            if a in ('truth', 'reseed'):
                ev = [dict(e, tick=e['tick']/TICK_MS) for e in src['events']]
            elif a == 'pred-head':
                ev = [e for e in src['events'] if e['owner'] == 1] + frame_own
            else:
                ev = frame_own
            st['buf'].extend(ev)
        poll = tick - tick % POLICY_INTERVAL
        if poll < START_TICK or poll == last_poll:
            continue
        last_poll = poll
        acts = {}
        for a, st in state.items():
            src = r['pred'] if a.startswith('pred') else r['truth']
            rec = dict(src, tick=poll, events=st['buf'])
            st['buf'] = []
            try:
                info = st['tr'].information(rec)
                view = PublicView(poll, 0, info, info, st['tr'].public_events, (), True)
                d = st['player'].act(view)
                acts[a] = (int(d.action), d.stats)
            except Exception as ex:
                st['errors'] += 1
                acts[a] = (WAIT, dict(error=repr(ex)[:300]))
        ref, ref_stats = acts['truth']
        if ref_stats is None:
            continue
        for a in arms:
            act, s = acts[a]
            out_rows.append(dict(episode=ep, tick=poll, shadow=a, truth=ref, action=act, agree=act == ref,
                                 truth_play=ref < WAIT, shadow_play=act < WAIT, tier=tier,
                                 wall_ms=(s or {}).get('wall_ms'), source=(s or {}).get('source'),
                                 error=(s or {}).get('error')))
    for st in state.values():
        st['player'].close()
    with open(out / 'agreement.jsonl', 'a') as f:
        for x in out_rows:
            f.write(json.dumps(x) + '\n')
    derived = {}
    for a in ('truth-births', 'pred-births'):
        if a in state:
            derived[a] = [dict(owner=o, card=c, x=x, y=y, tick=t) for o, c, x, y, t in state[a]['tr'].derived_plays]
    head = {}
    for r in rows:
        for e in r['pred']['events']:
            k = (e['owner'], e['card'], round(e['tick']))
            head.setdefault(k, dict(owner=e['owner'], card=e['card'], x=e['x'], y=e['y'], tick=e['tick']/TICK_MS))
    derived['pred-head (temporal head events)'] = list(head.values())
    plays = {k: match_plays(v, truth_plays) for k, v in derived.items()}
    plays['_reaching_bot'] = {a: len(state[a]['tr'].events) for a in state}
    plays['_cycle_dropped'] = {a: state[a]['tr'].stats.get('cycle_conflict_dropped:1', 0) for a in state}
    plays['_errors'] = {a: state[a]['errors'] for a in state}
    import statistics as stt
    clock = {k: dict(mean=stt.mean(v), p95_abs=sorted(map(abs, v))[int(.95*len(v))], max_abs=max(map(abs, v)),
                     anchored=clocks[k].fixed is not None) for k, v in clock_err.items()}
    res = dict(episode=ep, frames=len(rows), decisions=len(out_rows)//len(arms), secs=round(time.time()-t0, 1),
               plays=plays, clock=clock,
               translator={a: {k: v for k, v in state[a]['tr'].stats.items()} for a in state},
               tracker={a: dict(state[a]['tr'].tracker.stats) for a in state})
    with open(out / 'matches.jsonl', 'a') as f:
        f.write(json.dumps(res) + '\n')
    print(json.dumps(dict(episode=ep, decisions=res['decisions'], secs=res['secs'], plays=plays, clock=clock)),
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', choices=['fast', 'search'], default='fast')
    ap.add_argument('--records', type=Path, default=RECORDS)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    rt = Runtime()
    arms = ['truth', 'truth-births', 'pred-births', 'pred-head'] + (['reseed'] if a.tier == 'search' else [])
    for path in sorted(a.records.glob('*.jsonl')):
        run_match(rt, path, a.tier, a.out, arms)


if __name__ == '__main__':
    main()
