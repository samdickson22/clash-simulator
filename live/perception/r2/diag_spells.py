"""Round-2 diagnosis: where do opponent-spell (and troop) event misses come from? Validation dump only.

  python live/perception/r2/diag_spells.py DUMP_DIR OUT.json
"""
import json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/'live/perception'))
from bot.live.real_replay import load_dump, fused_events, OWN_NATIVE   # noqa: E402  (load_dump refuses non-validation)
from events import LIVE_DEFAULT  # noqa: E402

SPELLS = {'Arrows', 'BarbLog', 'Earthquake', 'Fireball', 'GoblinBarrel', 'Lightning', 'Log', 'Poison', 'Rocket',
          'RoyalDelivery', 'Tornado', 'Zap'}
VOCAB = '/mpac/sdicks02/jobs/clasher/live-perception-20261014/export-final/vocab.json'  # same 56 cards in export-r2


def main(dump, out):
    cards = json.loads(Path(VOCAB).read_text())['cards']
    cat = defaultdict(Counter); exist_hist = defaultdict(list); fp_cat = defaultdict(Counter)
    rank_true = defaultdict(Counter)
    for f in sorted(Path(dump).glob('*.jsonl.gz')):
        head, rows = load_dump(f)
        per_row, _ = fused_events(rows, cards, LIVE_DEFAULT)
        em = []   # emitted opponent events, native coords
        for r, evs in zip(rows, per_row):
            for e in evs:
                if e['owner'] == 1:
                    em.append(dict(card=e['card'], x=e['x'], y=32.-e['y'], exec=e['tick'], det=r['ts']))
        t0, t1 = rows[0]['ts'], rows[-1]['ts']
        truth = [e for e in head['truth_events'] if e['side'] != OWN_NATIVE and e['card'] in cards
                 and t0 <= e['exec_tick']*50. <= t1 - 1500]
        used = set()
        for e in sorted(truth, key=lambda e: e['exec_tick']):
            ex = e['exec_tick']*50.; tx, ty = e['tile']; kind = 'spell' if e['card'] in SPELLS else 'troop'
            ci = cards.index(e['card'])
            # head evidence: peaks of this side within 2.5 tiles over [exec, exec+1500]
            best_e, best_p, arg_at_best = 0., 0., None
            for r in rows:
                if not (ex <= r['ts'] <= ex+1500):
                    continue
                for s, x, y, exi, age, probs in r['peaks']:
                    if s != e['side'] or math.hypot(x-tx, y-ty) > 2.5:
                        continue
                    if exi > best_e:
                        best_e = exi; arg_at_best = cards[max(range(len(probs)), key=probs.__getitem__)]
                    best_p = max(best_p, probs[ci])
            # emitted
            cand = [(i, p) for i, p in enumerate(em) if i not in used and 0 <= p['det']-ex <= 1500 and math.hypot(p['x']-tx, p['y']-ty) <= 2.5]
            right = [c for c in cand if c[1]['card'] == e['card']]
            if right:
                i, p = min(right, key=lambda c: c[1]['det']); used.add(i)
                c = 'tp' if p['det']-ex <= 1000 else 'late_1to1.5s'
            elif cand:
                i, p = min(cand, key=lambda c: c[1]['det']); used.add(i)
                c = 'wrong_card'
                fp_cat[e['card']]['as:'+p['card']] += 1
            elif best_e >= LIVE_DEFAULT['threshold']:
                c = 'crossed_not_emitted'   # suppressed (repeat) or held past the window
            elif best_e >= .2:
                c = 'below_thr'
            else:
                c = 'no_peak'
            cat[(kind, e['card'])][c] += 1; cat[(kind, '*')][c] += 1
            exist_hist[kind].append((round(best_e, 3), round(best_p, 3), c, arg_at_best == e['card']))
            if c in ('below_thr', 'no_peak'):
                rank_true[kind]['true_card_argmax_at_best' if arg_at_best == e['card'] else 'other_argmax'] += 1
        # FP analysis for emitted spells
        for i, p in enumerate(em):
            if i in used:
                continue
            kind = 'spell' if p['card'] in SPELLS else 'troop'
            near = [e for e in head['truth_events'] if e['side'] != OWN_NATIVE and -500 <= p['det']-e['exec_tick']*50. <= 3000
                    and math.hypot(e['tile'][0]-p['x'], e['tile'][1]-p['y']) <= 3]
            own = [e for e in head['truth_events'] if e['side'] == OWN_NATIVE and -500 <= p['det']-e['exec_tick']*50. <= 3000
                   and math.hypot(e['tile'][0]-p['x'], e['tile'][1]-p['y']) <= 3]
            if any(e['card'] == p['card'] for e in near):
                k = 'dup_or_late'
            elif near:
                k = 'wrong_card_of_' + ('spell' if any(e['card'] in SPELLS for e in near) else 'troop')
            elif own:
                k = 'own_play_as_opp'
            else:
                k = 'spurious'
            fp_cat[(kind, '*')][k] += 1; fp_cat[(kind, p['card'])][k] += 1
    res = dict(miss_categories={f'{k[0]}:{k[1]}': dict(v) for k, v in sorted(cat.items())},
               fp_categories={(f'{k[0]}:{k[1]}' if isinstance(k, tuple) else f'confusion:{k}'): dict(v) for k, v in fp_cat.items()},
               below_thr_argmax=dict({k: dict(v) for k, v in rank_true.items()}),
               evidence={k: v for k, v in exist_hist.items()})
    Path(out).write_text(json.dumps(res, indent=0))
    for k in sorted(res['miss_categories']):
        if k.endswith('*') or k.startswith('spell'):
            print(k, res['miss_categories'][k])
    for k, v in res['fp_categories'].items():
        if k.endswith('*'):
            print('FP', k, v)
    print(res['below_thr_argmax'])


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
