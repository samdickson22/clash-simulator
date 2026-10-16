"""Replay handsync r3 (guard refusal -> tracker feedback) vs r1/r2 (guard only) on live handsync runs (s44+), scored
against the video truth (slot_audit.py).

  python replay_r3.py --drive <handsync-small-r3 drive.py> RUN_DIR [RUN_DIR ...] [--json OUT] [--jobs 8]

Live r1/r2 runs logged the guard's refusals (decision stats.guarded_action, tap_guard). The replay feeds the logged
perception records (with their live rec['hand']['ui']) and:
  - at a poll where live SUBMITTED: returns that action (guard in measure mode: it only records its verdict);
  - at a poll where live REFUSED: re-runs the guard on that action; arm r3 applies feedback() when it is a confident
    coloured_mismatch (as r3 would live); both arms return WAIT, as live did.
Scores: per submitted play, the card each arm would submit vs the deployed card (video truth); per r3 swap, the
swapped-in card vs the video truth for that slot at that frame.
"""
import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CACHE = '/mpac/sdicks02/scratch/live-loop/slot-cache'


# arm -> (guard threshold override or None = the drive's own, feedback): 'live' = the deployed guard, no feedback
ARMS = {'live': (None, False, False), 'r3c': (None, True, True), 'h1': (None, True, True)}   # + floor_late
HAND_ARMS = {'h1'}      # hand reads from --hand-logits (CAL cleared: swaps off, as live under a new hand head)
HAND_LOGITS = None


def load_drive(path, arm):
    os.environ['LL_HANDSYNC'], os.environ['LL_HANDSYNC_GUARD'] = '1', 'measure'
    spec = importlib.util.spec_from_file_location('drive_r3', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    gp = ARMS[arm][0]
    if hasattr(m, 'FLOOR_LATE'):
        m.FLOOR_LATE = ARMS[arm][2]
    if arm in HAND_ARMS:
        m.CAL.clear()
    if gp is not None and hasattr(m, 'GUARD_PREC'):
        m.GUARD_PREC = gp
    elif gp is not None:
        m.TRUST_P = gp
    return m


class Player:
    def __init__(self, sub, refused, arm):
        self.sub, self.refused, self.arm, self.sess = sub, refused, arm, None
        self.new_refusals, self.at_refusals = [], []

    def start(self, ctx):
        pass

    def close(self):
        pass

    def look(self, a):
        h = (self.sess._rec or {}).get('hand') or {}
        s = a // 576
        info = getattr(self.sess, '_info', None)
        avail = None if info is None else round(info.own['elixir'] - sum(c.cost for c in self.sess.ch.pending), 2)
        return dict(poll=self.sess.last_poll, slot=s, tracked=self.sess.tr.own_tracker.hand[s], avail=avail,
                    read=(h.get('cards') or [None]*4)[s], p=(h.get('probs') or [None]*4)[s], ui=(h.get('ui') or [None]*4)[s])

    def act(self, view):
        from bot.players.base import Decision, WAIT
        p = int(view.tick)
        if p in self.sub and view.can_act:
            why = self.sess.tap_guard(self.sub[p])
            if why:                          # this arm would refuse a play live made (replay diverges here)
                self.new_refusals.append(dict(self.look(self.sub[p]), why=why))
            return Decision(action=self.sub[p])
        a = self.refused.get(p)
        if a is not None and view.can_act:
            x = self.look(a)
            why = self.sess.tap_guard(a)
            self.at_refusals.append(dict(x, why=why))
            if why == 'coloured_mismatch' and ARMS[self.arm][1]:
                self.sess.feedback(a // 576)
        return Decision(action=WAIT)


def replay(d, arm, drive_path, truth_play, truth_frame):
    import ownplay
    from bot.players.runtime import Runtime
    d = Path(d)
    deck = json.loads((d/'session-config.json').read_text())['deck']
    P = [json.loads(l) for l in open(d/'perception.jsonl')]
    D = [json.loads(l) for l in open(d/'decisions.jsonl')]
    sub = {int(x['poll']): x['action'] for x in D if x.get('submitted') and x['action'] < 2304}
    refused = {int(x['poll']): (x.get('stats') or {}).get('guarded_action') for x in D
               if (x.get('stats') or {}).get('guarded_action') is not None}
    bypoll = {int(x['poll']): x for x in D if x.get('submitted')}
    rt = replay.rt = getattr(replay, 'rt', None) or Runtime()
    player = Player(sub, refused, arm)
    sess = load_drive(drive_path, arm).make_session(rt, player, deck)
    player.sess = sess
    ev = [json.loads(l) for l in open(d/'events.jsonl')] if (d/'events.jsonl').exists() else []
    start = next((e['ts_ms'] for e in ev if e.get('ev') == 'match_start'), None)
    if start is not None:
        sess.tr.clock.anchor(0, start)
    rows, swaps = [], []
    bar = {f['n']: f.get('elixir') for f in map(json.loads, open(d/'frames.jsonl'))}   # pre-floor (post-flash) reading
    hand = {}
    if arm in HAND_ARMS:
        import numpy as np, handread
        z = np.load(Path(HAND_LOGITS)/f'{d.parent.name}-{d.name}.npz')
        cards = json.loads((Path(HAND_LOGITS)/'vocab.json').read_text())['cards']
        hand = {int(n): handread.deck_constrained(lg, cards, deck) for n, lg in zip(z['n'], z['logits'])}
    for r in P:
        rec = {k: v for k, v in r.items() if k not in ('n', 'logged', 'tick', 'ts_ms')}
        if arm in HAND_ARMS:
            hr = hand.get(r['n'])
            if hr is not None and isinstance(rec.get('hand'), dict):
                rec['hand'] = dict(rec['hand'], cards=hr['cards'], probs=hr['probs'], next=hr['next'],
                                   next_prob=hr['next_prob'], raw=hr['raw'])
        if rec.get('elixir') is not None:
            if ARMS[arm][2]:
                rec['elixir'] = bar.get(r['n'], rec['elixir'])
            else:
                rec['elixir'] = max(rec['elixir'], sum(c.cost for c in sess.ch.pending))
        ownplay.dedupe_own_events(rec, sess)
        pend0, s0 = len(sess.ch.pending), len(sess.swaps)
        out = sess.step(rec)
        for poll, slot, card in sess.swaps[s0:]:
            swaps.append(dict(n=r['n'], slot=slot, card=card, truth=truth_frame.get((r['n'], slot))))
        if out is None or not sess.started:
            continue
        x = bypoll.get(sess.last_poll)
        if x is None or len(sess.ch.pending) <= pend0:
            continue
        rows.append(dict(n=x['n'], logged=x.get('card'), card=sess.ch.pending[-1].card, truth=truth_play.get(x['n'])))
    n_of = {int(x['poll']): x['n'] for x in D}
    for x in player.new_refusals + player.at_refusals:
        x['n'] = n_of.get(x['poll']); x['truth'] = truth_frame.get((x['n'], x['slot']))
    return dict(run=f'{d.parent.name}-{d.name}', arm=arm, rows=rows, swaps=swaps, new_refusals=player.new_refusals,
                at_refusals=player.at_refusals,
                stats={k: v for k, v in sess.tr.stats.items() if k.startswith(('tap_guard', 'own_sync', 'own_reanchor'))})


def one(job):
    d, arm, drive_path, hl = job
    global HAND_LOGITS
    HAND_LOGITS = hl
    import slot_audit
    frames = []
    rows = slot_audit.audit(d, cache=CACHE, frames=frames)
    truth_play = {r['n']: r['truth'] for r in rows if r['status'] in ('ok', 'WRONG')}
    truth_frame = {(f['n'], f['slot']): f['truth'] for f in frames}
    try:
        return replay(d, arm, drive_path, truth_play, truth_frame)
    except Exception:
        import traceback
        return dict(run=str(d), arm=arm, error=traceback.format_exc()[-1500:])


def summary(res, arm):
    R = [r for r in res if r['arm'] == arm and 'rows' in r]
    rows = [x for r in R for x in r['rows'] if x['truth'] is not None]
    sw = [s for r in R for s in r['swaps']]
    st = Counter()
    for r in R:
        st.update(r['stats'])
    return dict(arm=arm, battles=len(R), plays=len(rows), wrong_beliefs=sum(x['card'] != x['truth'] for x in rows),
                logged_wrong=sum(x['logged'] != x['truth'] for x in rows), swaps=len(sw),
                swaps_checked=sum(s['truth'] is not None for s in sw),
                swaps_wrong=sum(s['truth'] is not None and s['truth'] != s['card'] for s in sw),
                new_refusals=sum(len(r['new_refusals']) for r in R), mismatch_at_live_refusals=mismatch(R), stats=dict(st))


def mismatch(R):
    """At polls live refused with a coloured slot whose read != the tracked card (live coloured_mismatch), with video truth:
    this arm refuses and the tracked card was wrong (right refusal) or right (needless delay); this arm plays the
    tracked card and it was right (saved delay) or wrong (a wrong card)."""
    c = Counter()
    for r in R:
        for x in r['at_refusals']:
            if x['ui'] != 'coloured' or x['read'] in (None, x['tracked']) or x['truth'] is None:
                continue
            ok = x['truth'] == x['tracked']
            c[('refuse_' if x['why'] == 'coloured_mismatch' else 'play_') + ('tracked_right' if ok else 'tracked_wrong')] += 1
    return dict(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--drive', required=True)
    ap.add_argument('--json')
    ap.add_argument('--jobs', type=int, default=8)
    ap.add_argument('--hand-logits', help='dir of hand_logits_offline.py npz + vocab.json (arm h1)')
    a = ap.parse_args()
    jobs = [(d, arm, a.drive, a.hand_logits) for d in a.runs for arm in ARMS if a.hand_logits or arm not in HAND_ARMS]
    with Pool(a.jobs) as p:
        res = p.map(one, jobs, chunksize=1)
    for r in res:
        if 'error' in r:
            print('ERROR', r['run'], r['arm'], r['error'])
    out = {arm: summary(res, arm) for arm in ARMS if any(r.get('arm') == arm for r in res)}
    print(json.dumps(out, indent=1))
    for r in res:
        if r.get('arm') == 'r3':
            for s in r.get('swaps', ()):
                if s['truth'] is not None and s['truth'] != s['card']:
                    print('WRONG SWAP', r['run'], s)
    if a.json:
        Path(a.json).write_text(json.dumps(dict(summary=out, results=res), indent=1, default=str))


if __name__ == '__main__':
    main()
