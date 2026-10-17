"""05: learn the client's dataGlobalId -> body mapping from our own deployments (night raw data).

The probe's dataGlobalId does not follow the CSV row order for later characters (e.g. SpearGoblin is 34000019 in the
running client, GiantSkeleton in the CSV/catalog order), so the body catalog's ids cannot be trusted. Rule: an object
that FIRST appears within 3 ticks after a logged deployment of a single-body card (cards.json) has that card's body.
Spawned children (Tombstone skeletons, Dark Witch bats, death spawns) appear later and are not learned from their
parent's card. Output: COUNTS file {dgid: {body: n}}; label.py reads it (majority >= 80 %, n >= 3).

  python -B dgid_learn.py [--loop]
"""
import argparse
import glob
import gzip
import json
import os
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = Path('/mpac/sdicks02/scratch/nulls/night/raw')
OUT = Path('/mpac/sdicks02/scratch/nulls/client-tables/dgid_counts.json')
CARDS = {c['id']: c for c in json.loads((HERE.parent / 'cards.json').read_text())}


def learn_run(run_dir, counts):
    metas = []
    for f in sorted(run_dir.glob('chunk-*/*.json')):
        if f.name in ('manifest.json', 'events.json'):
            continue
        try:
            m = json.loads(f.read_text())
        except ValueError:
            continue
        if m.get('purpose') == 'scene':
            metas.append((m['tick'], f.parent / m['observations'], m.get('deployments') or []))
    metas.sort()
    seen = set()
    firsts = defaultdict(lambda: defaultdict(set))  # (card, deploy tick, owner) -> dgid -> object ids first seen in window
    for tick, obs_path, deps in metas:
        windows = [(d['card_id'], d['tick'], d.get('owner')) for d in deps
                   if len(CARDS.get(d['card_id'], {}).get('bodies') or []) == 1]
        try:
            with gzip.open(obs_path, 'rt') as fh:
                objs = json.load(fh)['before']['objects']
        except (OSError, ValueError, KeyError):
            continue
        for o in objs:
            k = o.get('nativeObjectId')
            if k in seen or o.get('null') or o.get('projectile'):
                continue
            seen.add(k)
            for cid, t0, owner in windows:
                if o.get('cardId') == cid and o.get('owner') == owner and t0 - 1 <= tick <= t0 + 3:
                    firsts[(cid, t0, owner)][str(o.get('dataGlobalId'))].add(k)
    # riders/attached units appear with the body (Goblin Giant's spear goblins): learn only the dgid group whose
    # object count equals the card's unit count, and only when exactly one group does
    for (cid, t0, owner), groups in firsts.items():
        want = CARDS[cid].get('count', 1) or 1
        match = [dg for dg, ids in groups.items() if len(ids) == want]
        if len(match) == 1:
            counts[match[0]][CARDS[cid]['bodies'][0]] += 1


CACHE = OUT.with_name('dgid_counts_runs.json')


def build():
    """Finished runs (DONE.json) are learned once and cached; open runs are re-read each pass."""
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    counts = defaultdict(lambda: defaultdict(int))
    runs = [Path(p) for p in glob.glob(str(RAW / 'i*' / '*')) if Path(p).is_dir()]
    for r in runs:
        key = f'{r.parent.name}/{r.name}'
        if key in cache:
            per = cache[key]
        else:
            c = defaultdict(lambda: defaultdict(int))
            learn_run(r, c)
            per = {k: dict(v) for k, v in c.items()}
            if (r / 'DONE.json').exists():
                cache[key] = per
        for dg, bodies in per.items():
            for b, n in bodies.items():
                counts[dg][b] += n
    CACHE.write_text(json.dumps(cache))
    tmp = OUT.with_suffix('.part')
    tmp.write_text(json.dumps({k: dict(v) for k, v in counts.items()}, indent=1, sort_keys=True))
    os.replace(tmp, OUT)
    return len(runs), len(counts)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop', action='store_true')
    a = ap.parse_args()
    os.nice(19)
    while True:
        n, k = build()
        print(time.strftime('%H:%M:%SZ', time.gmtime()), n, 'runs', k, 'dgids', flush=True)
        if not a.loop:
            break
        time.sleep(300)
