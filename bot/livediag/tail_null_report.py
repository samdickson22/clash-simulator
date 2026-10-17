"""Paired L16 null test readout: each arm vs --ref, bootstrap 95 % CI over cases, plus how many games differ at all
(play logs of both seats) -- a cap that never fires leaves the game identical."""
import argparse, glob, hashlib, json, random
ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--ref', required=True)
a = ap.parse_args()
by, logs, errs = {}, {}, {}
for d in a.dirs:
    for p in glob.glob(d + '/rows/*.json'):
        r = json.load(open(p)); k = (d, r['index'], r['opponent'])   # bank-aware: indices repeat across banks
        if r.get('error') or 'result' not in r:
            errs[r['player']] = errs.get(r['player'], 0) + 1; continue
        by.setdefault(r['player'], {})[k] = .5 if r.get('draw') else float(r.get('win') or 0)
        logs.setdefault(r['player'], {})[k] = hashlib.sha256(json.dumps(r['result']['play_log']).encode()).hexdigest()
def boot(d, seed=0):
    rng = random.Random(seed); m = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(4000))
    return round(sum(d) / len(d), 4), [round(m[100], 4), round(m[3900], 4)]
print('errors', errs)
for arm in sorted(by):
    n = len(by[arm]); print(f'{arm}: n={n} score {round(sum(by[arm].values())/n, 4)}')
    if arm == a.ref: continue
    k = sorted(set(by[arm]) & set(by[a.ref]))
    d = [by[arm][i] - by[a.ref][i] for i in k]
    same = sum(logs[arm][i] == logs[a.ref][i] for i in k)
    print(f'   {arm} - {a.ref}: n={len(d)}', *boot(d), f'identical games {same}/{len(k)}')
