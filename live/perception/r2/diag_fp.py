"""Round 2: where do phantom units (empirical.fit false positives: owner-only greedy <= 1 tile) come from? Validation dump.
  python live/perception/r2/diag_fp.py DUMP_DIR OUT.json [--threshold .4]
Categories (first that applies): displaced (same-owner true unit 1-2 tiles), owner_flip (other-owner true unit <= 1 tile),
lingering (a same-owner same-card true unit within 1.5 tiles in the previous 1 s, now gone: death/dissolve lag),
early (a same-owner same-card true unit appears within 1.5 tiles in the next 1 s: deploy lead), split (a same-owner pred within
1 tile matched a true unit), far (none of these).
"""
import argparse, json, math, sys
from collections import Counter, defaultdict, deque
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from bot.live.real_replay import load_dump  # noqa: E402
from bot.live.empirical import _greedy  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dump'); ap.add_argument('out'); ap.add_argument('--threshold', type=float, default=.4)
    a = ap.parse_args()
    cat = Counter(); by_card = defaultdict(Counter); frames = 0
    for f in sorted(Path(a.dump).glob('*.jsonl.gz')):
        _, rows = load_dump(f)
        ok = [r for r in rows if not r['truth'].get('objects_stale')]
        for k, r in enumerate(ok):
            frames += 1
            P_all = [u for u in r['units_lo'] if not u.get('effect') and u['score'] >= a.threshold]
            T_all = r['truth']['units']
            past = [u for q in ok[max(0, k-10):k] if r['ts']-q['ts'] <= 1000 for u in q['truth']['units']]
            fut = [u for q in ok[k+1:k+11] if q['ts']-r['ts'] <= 1000 for u in q['truth']['units']]
            for owner in (0, 1):
                T = [u for u in T_all if u['owner'] == owner]; P = [u for u in P_all if u['owner'] == owner]
                pairs = _greedy(P, T, 1.); used = {i for i, _, _ in pairs}
                for i, p in enumerate(P):
                    if i in used:
                        continue
                    d = lambda u: math.hypot(u['x']-p['x'], u['y']-p['y'])
                    same_now = any(d(u) <= 1.5 and u['card'] == p['card'] for u in T)
                    if any(1 < d(u) <= 2 for u in T):
                        c = 'displaced_1to2'
                    elif any(d(u) <= 1 for u in T_all if u['owner'] != owner):
                        c = 'owner_flip'
                    elif any(u['owner'] == owner and u['card'] == p['card'] and d(u) <= 1.5 for u in past) and not same_now:
                        c = 'lingering'
                    elif any(u['owner'] == owner and u['card'] == p['card'] and d(u) <= 1.5 for u in fut) and not same_now:
                        c = 'early'
                    elif any(math.hypot(P[j]['x']-p['x'], P[j]['y']-p['y']) <= 1 for j in used):
                        c = 'split'
                    else:
                        c = 'far'
                    cat[c] += 1; by_card[p['card']][c] += 1
    tot = sum(cat.values())
    res = dict(threshold=a.threshold, frames=frames, fp_per_frame=tot/frames, categories={k: dict(n=v, share=round(v/tot, 3)) for k, v in cat.most_common()},
               top_cards=[dict(card=c, n=sum(v.values()), **v) for c, v in sorted(by_card.items(), key=lambda kv: -sum(kv[1].values()))[:20]])
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ('threshold', 'frames', 'fp_per_frame', 'categories')}))
    for r in res['top_cards'][:12]:
        print(r)


if __name__ == '__main__':
    main()
