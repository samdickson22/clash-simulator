"""Own-hand audit: replay LiveSession on a run's logged perception records with the actions the bot actually submitted,
and compare, at every poll and every submitted play, the TRACKED hand (what the bot believes) with the HUD (what
perception read on that frame).

  python hand_audit.py RUN_DIR [RUN_DIR ...] [--json OUT] [--trace RUN:N0-N1]

Needs perception.jsonl + decisions.jsonl + session-config.json (deck). The player is a stub that returns the logged
action at the logged poll, so the translator / OwnTracker / CommandQueue see exactly the live sequence (perception
recomputation is not involved). A submitted play is a MISMATCH when the HUD read a different card in the tapped slot
with probability >= --conf on that frame; 'tracked_vs_hud' counts polls where a confident HUD slot disagrees with the
tracked one.
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ownplay  # noqa: E402
FIX = os.environ.get('HAND_AUDIT_FIX') == '1'     # 1 = apply ownplay.dedupe_own_events as drive.py now does


class ReplayPlayer:
    """Returns the logged action at each logged poll (WAIT otherwise)."""
    def __init__(self, actions):
        self.actions = actions

    def start(self, ctx):
        pass

    def act(self, view):
        from bot.players.base import Decision, WAIT
        a = self.actions.get(int(view.tick))
        return Decision(action=a if a is not None and view.can_act else WAIT)

    def close(self):
        pass


def audit(d, conf=.7, trace=None):
    from bot.players.runtime import Runtime
    from bot.live.translate import LiveSession
    d = Path(d)
    cfg = json.loads((d/'session-config.json').read_text())
    deck = cfg.get('deck')
    P = [json.loads(l) for l in open(d/'perception.jsonl')]
    D = [json.loads(l) for l in open(d/'decisions.jsonl')]
    sub = {int(x['poll']): x for x in D if x.get('submitted')}
    rt = audit.rt = getattr(audit, 'rt', None) or Runtime()
    sess = LiveSession(rt, ReplayPlayer({p: x['action'] for p, x in sub.items()}), deck)
    ev = [json.loads(l) for l in open(d/'events.jsonl')] if (d/'events.jsonl').exists() else []
    start = next((e['ts_ms'] for e in ev if e.get('ev') == 'match_start'), None)
    if start is not None:
        sess.tr.clock.anchor(0, start)            # as drive.py at match start
    rows, polls, mism, disagree, n_polls = [], [], [], 0, 0
    for r in P:
        rec = {k: v for k, v in r.items() if k not in ('n', 'logged', 'tick', 'ts_ms')}   # exactly what step() got
        before = list(sess.tr.own_tracker.hand) if sess.started else None
        if FIX:
            ownplay.dedupe_own_events(rec, sess)
        dcs = sess.step(rec)
        if dcs is None or not sess.started:
            continue
        n_polls += 1
        poll = sess.last_poll
        tracked = before if before is not None else list(sess.tr.own_tracker.hand)
        hud = (r.get('hand') or {}).get('cards') or [None]*4
        probs = (r.get('hand') or {}).get('probs') or [0]*4
        conf_dis = [i for i in range(4) if hud[i] and probs[i] >= conf and tracked[i] != hud[i]]
        disagree += bool(conf_dis)
        if trace and trace[0] <= r['n'] <= trace[1]:
            polls.append(dict(n=r['n'], poll=poll, tracked=tracked, hud=hud, probs=[round(p, 2) for p in probs],
                              next=(r.get('hand') or {}).get('next'), elixir=round(rec.get('elixir', 0), 2),
                              pending=[(c.card, c.action // 576) for c in sess.ch.pending], stats=dict(sess.tr.stats)))
        x = sub.get(poll)
        if x is not None:
            slot = x['action'] // 576
            row = dict(run=d.name, n=r['n'], poll=poll, card=x.get('card'), slot=slot, tracked_slot=tracked[slot],
                       hud_slot=hud[slot], hud_prob=round(probs[slot], 3), tracked=tracked, hud=hud)
            row['mismatch'] = bool(hud[slot] and probs[slot] >= conf and hud[slot] != x.get('card'))
            row['tracked_mismatch'] = bool(hud[slot] and probs[slot] >= conf and hud[slot] != tracked[slot])
            rows.append(row)
            if row['mismatch']:
                mism.append(row)
    return dict(run=d.name, plays=len(rows), mismatches=len(mism), tracked_mismatches=sum(r['tracked_mismatch'] for r in rows),
                polls=n_polls, polls_tracked_vs_hud=disagree,
                stats={k: v for k, v in sess.tr.stats.items() if k.startswith('own')}, mismatch_rows=mism, trace=polls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--conf', type=float, default=.7)
    ap.add_argument('--json')
    ap.add_argument('--trace')
    a = ap.parse_args()
    tr = None
    out = []
    for d in a.runs:
        if a.trace and a.trace.split(':')[0] == Path(d).name:
            lo, hi = a.trace.split(':')[1].split('-'); tr = (int(lo), int(hi))
        else:
            tr = None
        try:
            r = audit(d, a.conf, tr)
        except Exception as ex:
            print(Path(d).name, 'ERROR', repr(ex)[:200]); continue
        out.append(r)
        print(f"{r['run']}: plays {r['plays']} submitted!=HUD {r['mismatches']} tracked!=HUD {r['tracked_mismatches']} "
              f"reanchor_play {r['stats'].get('own_reanchor_play', 0)} dup_dropped {r['stats'].get('own_event_dup_dropped', 0)} "
              f"| polls {r['polls']} with a confident HUD "
              f"slot != tracked: {r['polls_tracked_vs_hud']} | {r['stats']}")
        for p in r['trace']:
            print('   ', p)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str))
    tot_p = sum(r['plays'] for r in out); tot_m = sum(r['mismatches'] for r in out)
    tot_t = sum(r['tracked_mismatches'] for r in out)
    ra = sum(r['stats'].get('own_reanchor_play', 0) for r in out); pv = sum(r['polls_tracked_vs_hud'] for r in out)
    pp = sum(r['polls'] for r in out)
    print(f'TOTAL plays {tot_p}: submitted card != confident HUD {tot_m} ({100*tot_m/max(tot_p, 1):.1f}%); tracked slot != '
          f'confident HUD at those plays {tot_t} ({100*tot_t/max(tot_p, 1):.1f}%); own_reanchor_play {ra}; polls with a '
          f'confident HUD slot != tracked {pv}/{pp} ({100*pv/max(pp, 1):.1f}%)  [fix={FIX}]')


if __name__ == '__main__':
    main()
