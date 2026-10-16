"""(b) End-to-end replay on REAL perception output: LivePerception records -> LiveTranslator -> LivePlayer
(LIVE integration, step-3 offline proof; exploration tier).

Input: the per-frame VALIDATION dump (live/perception/dump_records.py; one gz per match: header line with the true
plays, then per processed frame {seq, tick, ts, pred, truth, units_lo, peaks}) and, for the true engine state, the
same match's recording in clasher-bot-data/t1-trainval (bot.live.replay.T1Match). Both must be registered
'validation'; anything else (heldout included) raises before a file of that match is opened.

Frame. The perception frame is a y-flip of the native board (x from the screen left); T1Match's seat-1 frame is the
engine's 180-degree rotation. Every perception/truth record is mirrored (x -> 18 - x, tower sides swapped) into the
T1 frame so all arms decide in ONE frame and actions compare directly.

Arms (each its own translator + LivePlayer, same seeds, decided at the same 5-tick polls; poll tick = the true tick
unless noted):
  ref         true engine state (T1Match record: all hit-point objects by spawning card, own HUD, accepted plays)
  reseed      ref input, seeds +7: the bot's own noise floor (and wall-clock jitter for the search tier)
  ref-eps     ref input with every unit moved by +0.01 tile in x: the input-sensitivity floor (it5s2 samples its
              gate/card/tile, so a negligible input change can flip a near-tie tile)
  truth       dense-label truth record (sample_records.truth_record) with the true play events
  births      perception, opponent plays derived from unit births (the step-C default)
  head        perception, opponent plays from the temporal head + the original tracker (pred.events)
  fused       perception, opponent plays from the body-fused tracker (live/perception/events.py hold)
  fused+births perception, fused head events + birth-derived plays, de-duplicated (BothTranslator)
  fused-hud   'fused' with the tick from the HUD clock path (translator ClockTracker anchored at match start, as
              the live loop does), polls floored/caught up/skipped exactly as LiveSession
  fused-noanchor  same without the start anchor (phase-transition anchor or robust clock centre only)
Own plays come from the true plays in every perception/truth arm (live: from our own commands, LiveSession).
Plays executed before the first dumped frame reach every arm as true history (T1Match gives them to ref).

    PYTHONPATH=. CLASHER_BOT_RUNTIME=... python -m bot.live.real_replay --tier fast --out DIR [--matches N]
Outputs: agreement.jsonl (rows as bot.live.summarize; truth=ref action), matches.jsonl (per match: opponent plays
reaching the bot per arm, translator/stream-guard drops, errors, clock error), launch json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from pathlib import Path

from bot.noise.livefix.translate import LiveTranslator, frame_identity
from bot.noise.livefix.resync import restart_if_resynced

DUMP = Path('/mpac/sdicks02/jobs/clasher/live-integration-20261015/dump')
T1_DATA = Path('/mpac/sdicks02/repos/clasher-bot-data')
PERCEPTION = Path(__file__).resolve().parents[2] / 'live/perception'
SPLIT_SHA = '3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258'   # = live/perception/common.SPLIT_SHA
OWN_NATIVE = 1                      # recorded viewpoint = native owner 1 = T1 seat 1
ARMS = ('ref', 'reseed', 'ref-eps', 'truth', 'births', 'births-rs', 'head', 'fused', 'fused-rs', 'fused-prov', 'fused-prov-rs',
        'fused+births-rs', 'fused-hud-rs', 'fused-noanchor-rs')
HUD_ARMS = ('fused-hud', 'fused-noanchor')     # tick from the HUD clock path (anchored at match start / not)
# Suffix '-rs': the resync-capable cycle tracking (bot/live/resync.py) instead of dropping contradicting plays.
# 'fused-prov[...]': the provisional fusion config (FUSION_PROVISIONAL) instead of FUSION.


def base_arm(n):
    return n[:-3] if n.endswith('-rs') else n
# Arm 'fused' = the even-half F1 pick; 'fused-prov' = events.LIVE_DEFAULT (thr .6, hold 500), the deployed choice
# (RESULTS (b): tied bot-level agreement, 44% fewer wrong plays reaching the bot).
FUSION = dict(threshold=.5, hold_ms=700., max_hold_ms=700., vote_min=.35, prior_min=.02, unit_radius=2.5, agree_frames=2,
              early_share=.6)
FUSION_PROVISIONAL = dict(threshold=.6, hold_ms=500., max_hold_ms=500., vote_min=.35, prior_min=.02, unit_radius=1.5,
                          agree_frames=2, early_share=.6)


# -- guards and loading --------------------------------------------------------------------------------------
def validation_entry(ep, split_path=T1_DATA / 't1-split.json'):
    """The registered T1 entry of a VALIDATION match; raises for anything else (never an assert)."""
    import hashlib
    raw = Path(split_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SPLIT_SHA:
        raise ValueError(f'{split_path}: not the registered split (sha256 {SPLIT_SHA[:8]}...); refusing')
    split = json.loads(raw)
    entry = next((m for m in split['matches'] if m['episode'] == ep), None)
    if entry is None or entry.get('split') != 'validation':
        raise ValueError(f'{ep}: not a registered validation match ({None if entry is None else entry.get("split")}); refusing')
    return entry


def load_dump(path):
    with gzip.open(path, 'rt') as f:
        head = json.loads(f.readline())
        if head.get('split') != 'validation':
            raise ValueError(f'{path}: dump split {head.get("split")!r}; refusing')
        validation_entry(head['episode'])
        rows = [json.loads(x) for x in f]
    return head, rows


# -- frames ---------------------------------------------------------------------------------------------------
def mirror(rec):
    """Perception frame (y-flip of native) -> T1 seat-1 frame (180-degree rotation): x -> 18 - x, sides swap."""
    sw = {'left': 'right', 'right': 'left'}
    out = dict(rec)
    out['units'] = [dict(u, x=round(18. - float(u['x']), 3)) for u in rec.get('units', ())]
    if rec.get('towers') is not None:
        out['towers'] = [dict(t, side=sw.get(t.get('side'), t.get('side'))) for t in rec['towers']]
    out['events'] = [dict(e, x=round(18. - float(e['x']), 3)) for e in rec.get('events', ())]
    return out


def t1_frame(native_side, x, y):
    """Native tile -> (owner, x, y) in the T1 seat-1 frame (owner 0 = us)."""
    return (0 if native_side == OWN_NATIVE else 1), 18. - float(x), 32. - float(y)


def true_plays(head):
    out = []
    for e in head['truth_events']:
        o, x, y = t1_frame(e['side'], *e['tile'])
        out.append(dict(owner=o, card=e['card'], x=x, y=y, tick=float(e['exec_tick'])))
    return out


def fused_events(rows, cards, cfg):
    """Re-run the event tracker over the dump's stored peaks + units -> per-row event lists (perception frame,
    frame_record convention: tick = execution time in ms on the timestamp clock)."""
    if str(PERCEPTION) not in sys.path:
        sys.path.insert(0, str(PERCEPTION))
    import torch
    from events import EventTracker
    tr = EventTracker(cards, **cfg)
    per_row = []
    for r in rows:
        pk = [(s, x, y, e, torch.tensor(p), age) for s, x, y, e, age, p in r['peaks']]
        evs = []
        for c in tr.update(None, r['ts'], peaks=pk, units=r['units_lo']):
            owner = 0 if c['side'] == OWN_NATIVE else 1
            evs.append(dict(owner=owner, card=c['card'], x=round(c['x_tiles'], 3), y=round(32. - c['y_tiles'], 3),
                            tick=round(float(c['execution_timestamp_ms']), 1), score=round(float(c['existence_q']), 4)))
        per_row.append(evs)
    return per_row, tr.revised


# -- translator with both opponent-play sources -------------------------------------------------------------
class BothTranslator(LiveTranslator):
    """plays_from='events' + birth-derived opponent plays. A head event and a derived play describe the same
    opponent play when they are the same card within `same_ticks`, or any card within `any_ticks` and `tiles`; the
    first to arrive is kept (neither stream can be retracted downstream)."""

    def __init__(self, *a, same_ticks=60, any_ticks=30, tiles=2.5, **kw):
        kw['plays_from'] = 'events'
        super().__init__(*a, **kw)
        self.same_ticks, self.any_ticks, self.tiles = same_ticks, any_ticks, tiles
        self._stash = []

    def assign(self, record):
        assigned, plays = super().assign(record)
        for owner, card, x, y, tick in plays:
            if owner == 1:
                self._stash.append(dict(owner=1, card=card, x=x, y=y, tick=tick, derived=True, tick_unit='tick'))
                self.derived_plays.append((owner, card, x, y, tick))
        return assigned, plays

    def _dup(self, e, kept):
        t, name = float(e['tick']), self.card_name(str(e['card']))
        rows = [r for r in self.public_events if r['seat'] == 1] + kept
        for r in rows:
            dt = abs(t - float(r['tick']))
            if (r['name'] == name and dt <= self.same_ticks) or \
                    (dt <= self.any_ticks and math.hypot(float(r['x']) - float(e.get('x', 9.)), float(r['y']) - float(e.get('y', 16.))) <= self.tiles):
                return True
        return False

    def accept_events(self, record):
        evs = list(record.get('events', ())) + self._stash
        self._stash = []
        kept, out = [], []
        for e in sorted(evs, key=lambda e: float(e['tick'])):
            key = (int(e['owner']), str(e['card']), int(e['tick']), round(float(e.get('x', 0)), 1), round(float(e.get('y', 0)), 1))
            if key in self._seen:          # a re-sent row (cumulative streams): the base class drops it
                continue
            if int(e['owner']) == 1:
                if self._dup(e, kept):
                    self.stats['both_duplicate_dropped:' + ('birth' if e.get('derived') else 'event')] += 1
                    continue
                kept.append(dict(name=self.card_name(str(e['card'])), tick=float(e['tick']), x=e.get('x', 9.), y=e.get('y', 16.)))
            out.append(e)
        super().accept_events(dict(record, events=out))


# -- one match --------------------------------------------------------------------------------------------------
def match_plays(acc, truth, owner=1, tiles=3., lo=-10, hi=60):
    """Accepted plays vs true plays (same card, within `tiles`, tick in [true+lo, true+hi])."""
    T = [t for t in truth if t['owner'] == owner]
    used, tp, wrong = set(), 0, 0
    for d in acc:
        best = None
        for i, t in enumerate(T):
            if i in used or t['card'] != d['card']:
                continue
            dt = d['tick'] - t['tick']
            if lo <= dt <= hi and math.hypot(d['x'] - t['x'], d['y'] - t['y']) <= tiles:
                if best is None or abs(dt) < abs(T[best]['tick'] - d['tick']):
                    best = i
        if best is None:
            wrong += 1
        else:
            used.add(best)
            tp += 1
    return dict(true=len(T), accepted=len(acc), matched=tp, wrong=wrong, recall=tp / max(1, len(T)),
                precision=tp / max(1, len(acc)))


def run_match(rt, path, a, out, cards):
    from dataclasses import replace
    from bot.players.base import MatchContext, PublicView, POLICY_INTERVAL, START_TICK, WAIT
    from bot.live.replay import T1Match, make_live
    head, rows = load_dump(path)
    ep = head['episode']
    entry = validation_entry(ep)
    m = T1Match(rt, T1_DATA / 't1-trainval' / ep, entry, seat=OWN_NATIVE)
    if any(c not in rt.R.costs for c in m.deck):
        return print(json.dumps(dict(episode=ep, skipped='non-C56 own deck')), flush=True)
    ref_recs = {r['tick']: r for r in m.records(POLICY_INTERVAL) if r['tick'] >= START_TICK}
    plays = true_plays(head)
    own_plays = [p for p in plays if p['owner'] == 0]
    fev, revised = fused_events(rows, cards, a.fusion)
    fev_prov = fused_events(rows, cards, FUSION_PROVISIONAL)[0] if any('fused-prov' in n for n in a.arms.split(',')) else None
    first = ref_recs[min(ref_recs)]['hand']
    order = list(first['cards']) + ([first['next']] if first['next'] not in first['cards'] else [])
    order += [c for c in m.deck if c not in order]
    ctx = MatchContext(seat=0, seed=entry['seed'], own_order=tuple(order))
    arms = [x for x in a.arms.split(',')]
    st = {}
    from bot.noise.livefix.resync import ResyncTranslator, resync_both
    for n in arms:
        b, rs = base_arm(n), n.endswith('-rs')
        p = make_live(rt, a.tier, a.wall_ms, a.threads)
        actx = replace(ctx, seed=ctx.seed + 7) if n == 'reseed' else ctx
        p.start(actx)
        if b.startswith('fused+births'):
            tr = (resync_both() if rs else BothTranslator)(rt, m.deck)
        else:
            tr = (ResyncTranslator if rs else LiveTranslator)(rt, m.deck, plays_from='births' if b == 'births' else 'events')
        tr.set_own_order(order)
        st[n] = dict(player=p, tr=tr, buf=[], errors=0, clock=[], dec={}, ctx=actx, base=b)
    rows_out, t0, nown = [], time.time(), 0
    ref_ticks = sorted(ref_recs)
    lo_tick = max(START_TICK, ref_ticks[0], int(rows[0]['tick']) - int(rows[0]['tick']) % POLICY_INTERVAL + POLICY_INTERVAL)
    hi_tick = min(ref_ticks[-1], int(rows[-1]['tick']) - int(rows[-1]['tick']) % POLICY_INTERVAL)
    for n, s in st.items():
        if s['base'] == 'fused-hud':          # as the live loop: anchor the HUD clock at match start (timestamp of tick 0)
            s['tr'].clock.anchor(0, float(rows[0]['ts']) - 50. * float(rows[0]['tick']))
    k, ri, nown = 0, 0, 0
    # Plays before the perception window: every arm gets the same TRUE history (ref sees it via T1Match), so only
    # perception inside the window differs. Own plays before the window are consumed here.
    pre = [dict(owner=e['owner'], card=e['card'], x=e['x'], y=e['y'], tick=int(e['tick']), tick_unit='tick')
           for e in plays if e['tick'] < float(rows[0]['tick'])]
    while nown < len(own_plays) and own_plays[nown]['tick'] < float(rows[0]['tick']):
        nown += 1
    for n, s in st.items():
        if n not in ('ref', 'reseed', 'ref-eps'):
            s['buf'].extend(pre)
    for poll in range(lo_tick, hi_tick + 1, POLICY_INTERVAL):
        # feed every frame before this poll window plus the FIRST frame inside it (events buffered); the poll decides
        # on that first frame, as LiveSession does and as T1Match's reference record is taken (else the latest earlier)
        while k < len(rows) and (float(rows[k]['tick']) < poll or
                                 (float(rows[k]['tick']) < poll + POLICY_INTERVAL and (k == 0 or float(rows[k-1]['tick']) < poll))):
            r = rows[k]; tick = float(r['tick'])
            own = []
            while nown < len(own_plays) and own_plays[nown]['tick'] <= tick:
                e = own_plays[nown]; nown += 1
                own.append(dict(owner=0, card=e['card'], x=e['x'], y=e['y'], tick=int(e['tick']), tick_unit='tick'))
            for n, s in st.items():
                if n in ('ref', 'reseed', 'ref-eps'):
                    continue
                if n == 'truth':
                    ev = [dict(owner=1, card=e['card'], x=18. - float(e['x']), y=float(e['y']), tick_unit='tick',
                               tick=int(round(float(e['tick']) / 50.))) for e in r['truth']['events'] if e['owner'] == 1] + own
                elif s['base'] == 'births':
                    ev = own
                else:
                    src = r['pred']['events'] if s['base'] == 'head' else fev_prov[k] if 'fused-prov' in s['base'] else fev[k]
                    # ms on the timestamp clock -> match ticks here, once ('score' dropped: no translator re-conversion)
                    ev = [dict(owner=1, card=e['card'], x=18. - float(e['x']), y=float(e['y']), tick_unit='tick',
                               tick=int(round(tick - (float(r['ts']) - float(e['tick'])) / 50.)))
                          for e in src if e['owner'] == 1] + own
                s['buf'].extend(ev)
                if s['base'] in HUD_ARMS:
                    _hud_frame(s, r, tick, PublicView, WAIT)
            k += 1
        r = rows[max(0, k - 1)]; tick = float(r['tick'])
        while ri + 1 < len(ref_ticks) and ref_ticks[ri + 1] <= poll:
            ri += 1
        acts = {}
        for n, s in st.items():
            if n in ('ref', 'reseed', 'ref-eps'):
                rec = dict(ref_recs[ref_ticks[ri]], tick=poll)
                if n == 'ref-eps':
                    rec['units'] = [dict(u, x=min(18., float(u['x']) + .01)) for u in rec['units']]
            elif s['base'] in HUD_ARMS:      # decided per frame in _hud_frame (as LiveSession); look the poll up
                acts[n] = s['dec'].pop(poll, (WAIT, dict(no_decision_at_this_poll=True)))
                for q in [q for q in s['dec'] if q < poll]:
                    s['dec'].pop(q)
                continue
            else:
                rec = mirror(r['truth'] if n == 'truth' else r['pred'])
                rec = dict(rec, events=s['buf'], tick=poll)
                if n == 'truth':
                    rec['timestamp_ms'] = r['ts']
                s['buf'] = []
            try:
                info = s['tr'].information(rec)
                restart_if_resynced(s['tr'], s['player'], s['ctx'])
                view = PublicView(info.tick, 0, info, info, s['tr'].public_events, (), True)
                d = s['player'].act(view)
                acts[n] = (int(d.action), d.stats)
            except Exception as ex:
                s['errors'] += 1
                acts[n] = (WAIT, dict(error=repr(ex)[:300]))
        ref, ref_stats = acts['ref']
        if ref_stats is None:
            continue
        tr_act = acts.get('truth', (None, None))[0]
        for n in arms:
            act, s2 = acts[n]
            rows_out.append(dict(episode=ep, tick=poll, shadow=n, truth=ref, action=act, agree=act == ref,
                                 truth_play=ref < WAIT, shadow_play=act < WAIT, tier=a.tier,
                                 truth_record_action=tr_act, agree_truth_record=act == tr_act,
                                 wall_ms=(s2 or {}).get('wall_ms'), source=(s2 or {}).get('source'),
                                 error=(s2 or {}).get('error')))
    for s in st.values():
        s['player'].close()
    with open(out / 'agreement.jsonl', 'a') as f:
        for x in rows_out:
            f.write(json.dumps(x) + '\n')
    window = [p for p in plays if lo_tick <= p['tick'] <= hi_tick]
    reach = {}
    for n, s in st.items():
        acc = [dict(card=e['name'], x=e['x'], y=e['y'], tick=e['tick']) for e in s['tr'].public_events
               if e['seat'] == 1 and not e.get('injected')]        # inferred (resync) plays are counted separately
        reach[n] = dict(match_plays(acc, window), inferred=sum(1 for e in s['tr'].public_events if e.get('injected')))
    res = dict(episode=ep, rows=len(rows), decisions=len(rows_out) // max(1, len(arms)), secs=round(time.time() - t0, 1),
               ticks=[lo_tick, hi_tick], true_opp_plays=sum(p['owner'] == 1 for p in window), fused_revised=revised,
               reach=reach, translator={n: dict(s['tr'].stats) for n, s in st.items()},
               tracker={n: dict(s['tr'].tracker.stats) for n, s in st.items()}, errors={n: s['errors'] for n, s in st.items()},
               decision_errors={n: sum(1 for x in rows_out if x['shadow'] == n and x['error']) for n in arms},
               clock={n: dict(err=_q(st[n]['clock']), skipped=st[n].get('skipped', 0), catchup=st[n].get('catchup', 0))
                      for n in st if st[n]['base'] in HUD_ARMS},
               restarts={n: getattr(s['tr'], 'restarts', 0) for n, s in st.items()}, t1_records=m.stats)
    with open(out / 'matches.jsonl', 'a') as f:
        f.write(json.dumps(res) + '\n')
    print(json.dumps(dict(episode=ep, decisions=res['decisions'], secs=res['secs'],
                          reach={n: (v['matched'], v['wrong'], v['true']) for n, v in reach.items()},
                          errors=res['errors'])), flush=True)


def _hud_frame(s, r, tick, PublicView, WAIT, interval=5):
    """One frame for a HUD-clock arm, exactly as LiveSession.step: tick from the HUD clock (ClockTracker, every
    frame); the first frame in a new 5-tick poll window decides (catch-up polls with can_act=False for a gap). The
    catch-up records repeat this capture: tagged synthetic with its identity, never new perception evidence."""
    rec = mirror(r['pred'])
    rec.pop('tick', None)
    ht = s['tr'].tick_of(rec)
    s['clock'].append(ht - tick)
    hp = ht - ht % interval
    last = s.get('last_hud_poll')
    if last is not None and hp <= last:
        s['skipped'] = s.get('skipped', 0) + 1           # same poll window: frame only feeds the event buffer
        return
    frame = frame_identity(dict(rec, tick=ht))       # the capture's identity (a supplied id is kept)
    if last is not None and hp - last > interval:
        for q in range(last + interval, hp, interval):
            s['catchup'] = s.get('catchup', 0) + 1
            try:
                info = s['tr'].information(dict(rec, tick=q, events=[], _frame=frame, _synthetic=True))
                restart_if_resynced(s['tr'], s['player'], s['ctx'])
                s['player'].act(PublicView(q, 0, info, info, s['tr'].public_events, (), False))
            except Exception:
                s['errors'] += 1
    s['last_hud_poll'] = hp
    rec = dict(rec, tick=hp, events=s['buf'], _frame=frame)
    s['buf'] = []
    try:
        info = s['tr'].information(rec)
        restart_if_resynced(s['tr'], s['player'], s['ctx'])
        d = s['player'].act(PublicView(hp, 0, info, info, s['tr'].public_events, (), True))
        s.setdefault('dec', {})[hp] = (int(d.action), d.stats)
    except Exception as ex:
        s['errors'] += 1
        s.setdefault('dec', {})[hp] = (WAIT, dict(error=repr(ex)[:300]))


def _q(v):
    if not v:
        return None
    s = sorted(abs(x) for x in v)
    return dict(n=len(v), mean=sum(v) / len(v), median_abs=s[len(s) // 2], p95_abs=s[int(.95 * (len(s) - 1))], max_abs=s[-1])


def report(out, *more):
    """Markdown tables from a replay dir: agreement vs ref (95% CI = bootstrap over MATCHES), opponent plays reaching
    the bot, translator / stream-guard drops, errors."""
    import random
    from collections import defaultdict
    from bot.live.summarize import close
    rows, ms, seen = [], [], set()
    for d in (out,) + tuple(more):
        m_d = [json.loads(l) for l in (d / 'matches.jsonl').read_text().splitlines() if l.strip()]
        keep = {m['episode'] for m in m_d} - seen
        ms += [m for m in m_d if m['episode'] in keep]
        rows += [r for r in (json.loads(l) for l in (d / 'agreement.jsonl').read_text().splitlines() if l.strip())
                 if r['episode'] in keep]
        seen |= keep
    arms = list(dict.fromkeys(r['shadow'] for r in rows))
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r['shadow']][r['episode']].append(r)
    eps = sorted({r['episode'] for r in rows})
    rng = random.Random(0)
    boot = [[rng.choice(eps) for _ in eps] for _ in range(1000)]

    def stat(arm, f, sel=lambda r: True):
        num = {e: sum(f(r) for r in by[arm][e] if sel(r)) for e in eps}
        den = {e: sum(1 for r in by[arm][e] if sel(r)) for e in eps}
        tot = sum(den.values())
        m = sum(num.values()) / max(1, tot)
        bs = sorted(sum(num[e] for e in b) / max(1, sum(den[e] for e in b)) for b in boot)
        return m, bs[25], bs[974], tot
    print(f'{len(eps)} matches, {sum(1 for r in rows if r["shadow"] == arms[0])} decisions per arm\n')
    print('| arm | exact | 95% CI (by match) | play/wait same | ref plays: exact | same card | card+<=2 tiles | ref WAITs kept |'
          ' plays when ref waits | agree w/ truth record | decision errors |')
    print('|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for a in arms:
        ex, lo, hi, n = stat(a, lambda r: r['agree'])
        pw = stat(a, lambda r: r['truth_play'] == r['shadow_play'])[0]
        pe, _, _, npl = stat(a, lambda r: r['agree'], lambda r: r['truth_play'])
        sc = stat(a, lambda r: r['shadow_play'] and r['action'] // 576 == r['truth'] // 576, lambda r: r['truth_play'])[0]
        ct = stat(a, lambda r: close(r['truth'], r['action']), lambda r: r['truth_play'])[0]
        wk = stat(a, lambda r: not r['shadow_play'], lambda r: not r['truth_play'])[0]
        pww = sum(r['shadow_play'] for e in eps for r in by[a][e] if not r['truth_play'])
        atr = stat(a, lambda r: r['agree_truth_record'])[0]
        er = sum(bool(r['error']) for e in eps for r in by[a][e])
        print(f'| {a} | {ex:.3f} | [{lo:.3f}, {hi:.3f}] | {pw:.3f} | {pe:.3f} (n={npl}) | {sc:.3f} | {ct:.3f} | {wk:.3f} | {pww} | {atr:.3f} | {er} |')
    print('\n| arm | true opp plays | reaching the bot (matched) | recall | wrong plays accepted | precision | stream-guard drops '
          '(cycle_conflict:1) | resyncs (plays inferred) / failed | late retimed | dup dropped (both) | translator errors |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for a in arms:
        T = sum(m['reach'][a]['true'] for m in ms); M = sum(m['reach'][a]['matched'] for m in ms)
        W = sum(m['reach'][a]['wrong'] for m in ms); A = sum(m['reach'][a]['accepted'] for m in ms)
        g = lambda k: sum(v for m in ms for kk, v in m['translator'][a].items() if kk.startswith(k))
        x = lambda k: sum(m['translator'][a].get(k, 0) for m in ms)
        print(f'| {a} | {T} | {M} | {M/max(1,T):.3f} | {W} | {M/max(1,A):.3f} | {g("cycle_conflict_dropped:1")} | '
              f'{x("resync")} ({x("resync_injected")}) / {x("resync_failed")} | '
              f'{g("late_event_retimed")} | {g("both_duplicate")} | {sum(m["errors"][a] for m in ms)} |')
    other = defaultdict(int)
    for m in ms:
        for a, d in m['translator'].items():
            for k, v in d.items():
                if not k.startswith(('cycle_conflict_dropped:1', 'late_event_retimed', 'both_duplicate', 'future_event', 'resync')):
                    other[(a, k.split(':')[0])] += v
    print('\nother translator counters:', dict(sorted(other.items())) or 'none')
    clk = [m['clock'] for m in ms if m.get('clock')]
    for a in sorted({k for c in clk for k in c}):
        e = [c[a]['err'] for c in clk if a in c and c[a]['err']]
        if e:
            print(f'{a}: |tick err| median of match medians {sorted(x["median_abs"] for x in e)[len(e)//2]}, '
                  f'max p95 {max(x["p95_abs"] for x in e)}, polls skipped {sum(c[a]["skipped"] for c in clk if a in c)}, '
                  f'caught up {sum(c[a]["catchup"] for c in clk if a in c)}')


def main():
    if len(sys.argv) > 2 and sys.argv[1] == 'report':
        return report(*map(Path, sys.argv[2:]))
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', choices=['fast', 'search'], default='fast')
    ap.add_argument('--wall-ms', type=int, default=None)
    ap.add_argument('--threads', type=int, default=1)
    ap.add_argument('--dump', type=Path, default=DUMP)
    ap.add_argument('--matches', type=int, default=0, help='first N dump files (sorted); 0 = all')
    ap.add_argument('--shard', type=int, default=0)
    ap.add_argument('--nshards', type=int, default=1)
    ap.add_argument('--arms', default=','.join(ARMS))
    ap.add_argument('--reverse', action='store_true', help='process the dump files last-first (a second host from the end)')
    ap.add_argument('--skip-done', type=Path, action='append', default=[], help='also skip episodes finished in this dir')
    ap.add_argument('--fusion', type=json.loads, default=FUSION)
    ap.add_argument('--vocab', default='/mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final/vocab.json')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    if not a.arms.startswith('ref'):
        raise ValueError('the first arm must be ref (agreement reference)')
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f'launch-{int(time.time())}-{a.shard}.json').write_text(json.dumps({k: str(v) for k, v in vars(a).items()}))
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    rt = Runtime()
    cards = json.loads(Path(a.vocab).read_text())['cards']
    files = sorted(a.dump.glob('*.jsonl.gz'))
    files = files[:a.matches] if a.matches else files
    done = set()
    if (a.out / 'matches.jsonl').exists():
        done = {json.loads(l)['episode'] for l in (a.out / 'matches.jsonl').read_text().splitlines() if l.strip()}
    files = files[::-1] if a.reverse else files
    for path in files[a.shard::a.nshards]:
        for d in a.skip_done:
            if (d / 'matches.jsonl').exists():
                done |= {json.loads(l)['episode'] for l in (d / 'matches.jsonl').read_text().splitlines() if l.strip()}
        if path.name.split('.')[0] in done:
            continue
        run_match(rt, path, a, a.out, cards)


if __name__ == '__main__':
    main()
