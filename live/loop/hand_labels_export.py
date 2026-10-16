"""Video-truth labels for the own hand (4 slots + next), per recorded frame, for training/evaluating a hand classifier.

  python hand_labels_export.py --out DIR RUN_DIR [RUN_DIR ...] [--jobs 12]

Truth comes from slot_audit.intervals (see slot_audit.py): each slot's occupancy interval holds ONE card, labelled by the
mode of confident (>= .8) COLOURED HUD reads in it ('coloured') or else by the Next preview read (>= .7) while the slot
was empty before it ('next'). Intervals with neither are unlabelled (opening hands without a confident read, mostly).
NEXT label (derived): the truth of the first non-opening interval (any slot) that starts after the frame; frames within
2 frames of that start are marked ambiguous (the preview switches on the fill frame).
Writes DIR/labels/<run>.jsonl.gz (one row per frame x slot), DIR/precision/*.json, DIR/summary.json.
"""
import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CACHE = '/mpac/sdicks02/scratch/live-loop/slot-cache'


def run_id(d):
    d = Path(d)
    return d.name if d.parent.name == 'runs' else f'{d.parent.name}-{d.name}'


def export(job):
    d, out = Path(job[0]), Path(job[1])
    import slot_audit
    from handui import COLOURED_SAT
    deck = json.loads((d/'session-config.json').read_text()).get('deck') or []
    P = {}
    for l in open(d/'perception.jsonl'):
        r = json.loads(l); P[r['n']] = r
    S = slot_audit.slot_states(d, P, CACHE)
    ns = sorted(S)
    IV = slot_audit.intervals(ns, P, S, deck, .8, .7)
    starts = sorted((v['a'], v['truth']) for iv in IV for v in iv[1:])
    rid, rows, nxt_agree = run_id(d), [], Counter()
    j = 0
    for k in ns:
        h = P[k].get('hand') or {}
        cards, probs = h.get('cards') or [None]*4, h.get('probs') or [None]*4
        for s in range(4):
            empty, sat = S[k][s]
            v = None if empty else next((x for x in IV[s] if x['a'] <= k <= x['b']), None)
            rows.append(dict(run=rid, n=k, slot=s, ui='empty' if empty else 'coloured' if sat > COLOURED_SAT else 'greyed',
                             sat=round(sat, 1), truth=None if v is None else v['truth'],
                             source=None if v is None or v['truth'] is None else ('coloured' if v['col_truth'] else 'next'),
                             conflict=bool(v and v['conflict']), hud=cards[s],
                             hud_p=None if probs[s] is None else round(probs[s], 4)))
        while j < len(starts) and starts[j][0] <= k:
            j += 1
        nt, amb = (starts[j][1], starts[j][0] - k <= 2) if j < len(starts) else (None, False)
        rows.append(dict(run=rid, n=k, slot='next', ui=None, sat=None, truth=nt, source='derived' if nt else None,
                         ambiguous=amb, hud=h.get('next'),
                         hud_p=None if h.get('next_prob') is None else round(h['next_prob'], 4)))
        if nt and not amb and h.get('next') and (h.get('next_prob') or 0) >= .7:
            nxt_agree[h['next'] == nt] += 1
    (out/'labels').mkdir(parents=True, exist_ok=True)
    with gzip.open(out/'labels'/f'{rid}.jsonl.gz', 'wt') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    lab = [r for r in rows if r['slot'] != 'next' and r['truth']]
    return dict(run=rid, deck=deck, video=str(d/'video'), frames=len(ns), slot_rows=sum(r['slot'] != 'next' for r in rows),
                labelled=len(lab), coloured=sum(r['ui'] == 'coloured' for r in lab), greyed=sum(r['ui'] == 'greyed' for r in lab),
                next_hud_agree=nxt_agree[True], next_hud_disagree=nxt_agree[False],
                acc=card_acc(lab))


def card_acc(lab):
    """per true card, COLOURED frames: [n, HUD right] (recall of the HUD per true card)."""
    c = defaultdict(lambda: [0, 0])
    for r in lab:
        if r['ui'] == 'coloured' and r['hud']:
            c[r['truth']][0] += 1; c[r['truth']][1] += r['hud'] == r['truth']
    return dict(c)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('runs', nargs='+')
    ap.add_argument('--out', required=True)
    ap.add_argument('--jobs', type=int, default=12)
    a = ap.parse_args()
    out = Path(a.out)
    with Pool(a.jobs) as p:
        res = p.map(export, [(d, out) for d in a.runs], chunksize=1)
    (out/'summary.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k: sum(r[k] for r in res) for k in ('frames', 'slot_rows', 'labelled', 'coloured', 'greyed',
                                                         'next_hud_agree', 'next_hud_disagree')}))


if __name__ == '__main__':
    main()
