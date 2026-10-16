"""Submitted card vs the card the tap actually deployed, from the recorded video (independent of the HUD classifier).

  python slot_audit.py RUN_DIR [RUN_DIR ...] [--json OUT] [--trace RUN:N]

Ground truth comes from two things the client always shows:
- a played card leaves its slot and the slot shows the empty (blue crown) placeholder until the next card slides in,
  so each slot's frames split into OCCUPANCY INTERVALS (maximal non-empty runs) that each hold ONE card;
- the card that slides in is the coloured "Next" preview shown while the slot was empty (the HUD reads it at ~.98).
TRUTH of an interval = the mode of confident Next reads (>= --next-conf) during the empty run before it; the
opening-hand intervals (each slot's first: the empty run before them is the deal, whose preview is card 5) use the mode of confident reads (>= --conf) on COLOURED frames
(mean saturation > 60; greyed, unaffordable cards are read badly by the HUD model and are never used as truth).
Where both exist they are cross-checked ('truth_conflict') and the coloured reads win (the 4 conflicts on s17-s22
were all Next-label errors on video).

Each submitted play maps to the interval holding the tapped slot at the tap frame:
  ok        submitted == truth          WRONG     submitted != truth (the tap deployed another card)
  unknown   no truth for that interval  no_card   the slot was empty at the tap
'deployed_after' = frames until the interval ended (the card left; None = it never left before the next play of that
slot or the end). Each WRONG play is attributed: 'perception' when the HUD's (constrained) read of the slot at the tap
equals the submitted card, i.e. the bot believed a misread; otherwise 'tracker' (the bot's tracked hand differed from a
HUD that was right or unsure).
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import cv2


HERE = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(HERE))
from handui import COLOURED_SAT, slot_stats as slot_state  # noqa: E402  (same slot UI rule as the driver)


def slot_states(d, P, cache=None):
    """{n: slot_state} for the frames with a perception record; cached as JSON under `cache` (a directory)."""
    cf = Path(cache)/f'{d.parent.name}-{d.name}.json' if cache else None
    if cf is not None and cf.exists():
        return {int(k): [tuple(x) for x in v] for k, v in json.loads(cf.read_text()).items()}
    S = {}
    for n in sorted(P):
        f = d/'video'/f'{n:06d}.jpg'
        im = cv2.imread(str(f)) if f.exists() else None
        if im is not None:
            S[n] = slot_state(im)
    if cf is not None:
        cf.parent.mkdir(parents=True, exist_ok=True); cf.write_text(json.dumps(S))
    return S


def mode(xs):
    return Counter(xs).most_common(1)[0][0] if xs else None


def intervals(ns, P, S, deck, conf, next_conf):
    """Per slot: [dict(a, b, truth, next_truth, col_truth)] over frames ns (frames with perception + video)."""
    out = []
    for s in range(4):
        iv, cur, empty_next = [], None, None
        for n in ns:
            empty, sat = S[n][s]
            h = P[n].get('hand') or {}
            if empty:
                if cur is not None:
                    iv.append(cur); cur = None
                if empty_next is None:
                    empty_next = []
                nx, p = h.get('next'), h.get('next_prob') or 0
                if nx in deck and p >= next_conf:
                    empty_next.append((n, nx))
                continue
            if cur is None:
                # the preview can switch to the following card on the fill frame itself: drop the last 2 empty reads
                nt = mode([c for _, c in empty_next[:-2]]) if empty_next and len(empty_next) > 2 else \
                    (mode([c for _, c in empty_next]) if empty_next else None)
                cur = dict(a=n, b=n, next_truth=nt, col=[])
                empty_next = None
            cur['b'] = n
            c, p = (h.get('cards') or [None]*4)[s], (h.get('probs') or [0]*4)[s]
            if sat > COLOURED_SAT and c in deck and p >= conf:
                cur['col'].append(c)
        if cur is not None:
            iv.append(cur)
        if iv:
            iv[0]['next_truth'] = None    # the opening hand: the empty run before it is the deal, its preview is card 5
        for x in iv:
            x['col_truth'] = mode(x.pop('col'))
            # coloured reads (>= --conf) are right ~99% (s17-s22); on a conflict they win (4 checked on video, 10-16)
            x['truth'] = x['col_truth'] or x['next_truth']
            x['conflict'] = bool(x['next_truth'] and x['col_truth'] and x['next_truth'] != x['col_truth'])
        out.append(iv)
    # one card is in one slot at a time: a Next-only truth that overlaps the same card in another slot is the preview
    # of a later card (two plays within a few frames; s27-m01 slot 0 n109-519 'Fireball' was Valkyrie on video) -> drop it
    for s in range(4):
        for x in out[s]:
            if x['truth'] and not x['col_truth'] and any(y['truth'] == x['truth'] and y['a'] <= x['b'] and x['a'] <= y['b']
                                                         for t in range(4) if t != s for y in out[t]):
                x['truth'], x['dup'] = None, True
    return out


def audit(d, conf=.8, next_conf=.7, trace=None, cache=None, frames=None):
    d = Path(d)
    deck = json.loads((d/'session-config.json').read_text()).get('deck') or []
    P = {}
    for l in open(d/'perception.jsonl'):
        r = json.loads(l); P[r['n']] = r
    S = slot_states(d, P, cache)
    ns = sorted(S)
    IV = intervals(ns, P, S, deck, conf, next_conf)
    D = [json.loads(l) for l in open(d/'decisions.jsonl')]
    plays = [x for x in D if x.get('submitted') and x['action'] < 2304]
    name = f'{d.parent.name}-{d.name}'
    rows = []
    for x in plays:
        n, slot, card = x['n'], x['action'] // 576, x.get('card')
        m = max((k for k in ns if k <= n), default=None)          # last recorded frame at/before the tap
        iv = next((v for v in IV[slot] if m is not None and v['a'] <= m <= v['b']), None)
        h = (P.get(n) or P.get(m) or {}).get('hand') or {}
        hud, p_hud = (h.get('cards') or [None]*4)[slot], (h.get('probs') or [0]*4)[slot]
        sat = S[m][slot][1] if m in S else None
        if iv is None:
            status, truth = 'no_card', None
        else:
            truth = iv['truth']
            status = 'unknown' if truth is None else ('ok' if truth == card else 'WRONG')
        later = [y['n'] for y in plays if y['n'] > n and y['action'] // 576 == slot]
        dep = None
        if iv is not None and (not later or iv['b'] < later[0]) and iv['b'] < ns[-1]:
            dep = iv['b'] + 1 - n
        rows.append(dict(run=name, n=n, slot=slot, submitted=card, truth=truth, status=status,
                         source=None if iv is None else ('next' if iv['next_truth'] else 'coloured'),
                         truth_conflict=bool(iv and iv['conflict']), hud=hud, p_hud=round(p_hud, 3),
                         greyed=None if sat is None else sat <= COLOURED_SAT, deployed_after=dep,
                         cause=None if status != 'WRONG' else ('perception' if hud == card else 'tracker'),
                         elixir=None if (P.get(n) or {}).get('elixir') is None else round(P[n]['elixir'], 2)))
    if frames is not None:                    # per (frame, non-empty slot) HUD read vs the interval truth
        for s in range(4):
            for v in IV[s]:
                if v['truth'] is None:
                    continue
                for k in ns:
                    if v['a'] <= k <= v['b']:
                        h = P[k].get('hand') or {}
                        frames.append(dict(run=name, n=k, slot=s, truth=v['truth'], coloured=S[k][s][1] > COLOURED_SAT,
                                           card=(h.get('cards') or [None]*4)[s], p=(h.get('probs') or [0]*4)[s],
                                           raw=(h.get('raw') or [None]*5)[s], elixir=P[k].get('elixir')))
    if trace is not None:
        for s in range(4):
            for v in IV[s]:
                if v['a'] - 60 <= trace <= v['b'] + 60:
                    print(name, 'slot', s, v)
    return rows


def summary(rows):
    c = Counter(r['status'] for r in rows)
    known = c['ok'] + c['WRONG']
    out = dict(plays=len(rows), ok=c['ok'], wrong=c['WRONG'], unknown=c['unknown'], no_card=c['no_card'],
               wrong_rate_known=round(c['WRONG'] / known, 4) if known else None,
               truth_conflicts=sum(r['truth_conflict'] for r in rows))
    for k, sel in (('coloured_at_tap', False), ('greyed_at_tap', True)):
        rr = [r for r in rows if r['greyed'] is sel and r['status'] in ('ok', 'WRONG')]
        w = sum(r['status'] == 'WRONG' for r in rr)
        out[k] = dict(plays=len(rr), wrong=w, rate=round(w / len(rr), 4) if rr else None)
    W = [r for r in rows if r['status'] == 'WRONG']
    out['wrong_cause'] = dict(Counter(r['cause'] for r in W))
    out['wrong_pairs'] = Counter(f"{r['submitted']}->{r['truth']}" for r in W).most_common()
    out['never_left'] = sum(r['deployed_after'] is None for r in rows if r['status'] != 'no_card')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--conf', type=float, default=.8)
    ap.add_argument('--next-conf', type=float, default=.7)
    ap.add_argument('--json')
    ap.add_argument('--cache', default='/mpac/sdicks02/scratch/live-loop/slot-cache', help="slot-state cache dir ('' = none)")
    ap.add_argument('--trace', help='RUN_NAME:N, e.g. s21-m03:364 (prints that slot intervals around N)')
    a = ap.parse_args()
    tr = a.trace.split(':') if a.trace else None
    rows = []
    for d in a.runs:
        name = f'{Path(d).parent.name}-{Path(d).name}'
        rows += audit(d, a.conf, a.next_conf, trace=int(tr[1]) if tr and tr[0] == name else None, cache=a.cache or None)
    s = summary(rows)
    for r in rows:
        if r['status'] != 'ok':
            print(json.dumps(r))
    print(json.dumps(s, indent=1))
    if a.json:
        Path(a.json).write_text(json.dumps(dict(summary=s, rows=rows), indent=1))


if __name__ == '__main__':
    main()
