"""Round 2: UnitFilter variants on a validation dump (units_lo >= .25), scored as unit_sweep.py (empirical.fit matching,
phantom proxy). Selection on the EVEN half by proxy; the selected rows are also reported on the odd half.

  python live/perception/r2/filter_sweep.py DUMP_DIR OUT.json [--count-extras] [--workers 3]
"""
import argparse, itertools, json, sys
from multiprocessing import Pool
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO/'live/perception'))
from bot.live.real_replay import load_dump  # noqa: E402
from bot.live.empirical import _greedy  # noqa: E402
from unit_filter import UnitFilter  # noqa: E402

A_RECALL, B_FP = .0435/(1-.811), .0485/.38


def grid_edge():
    out = [dict(hi=.5, lo=.5), dict(hi=.5, lo=.35, nms=.6)]
    for hi, lo, nms in itertools.product((.45, .5, .55), (.25, .3, .35), (.6, .8, 1.0)):
        out.append(dict(hi=hi, lo=lo, nms=nms))
    return out


def grid():
    out = []
    for t in (.45, .5, .55, .6):
        out.append(dict(hi=t, lo=t))
    for hi, lo, nms, conf in itertools.product((.5, .55, .6, .65), (.35, .4, .45, .5), (0., .4, .6), (0, 1)):
        if lo <= hi:
            out.append(dict(hi=hi, lo=lo, nms=nms, confirm=conf))
    return out


def job(args):
    path, cfgs, extras = args
    _, rows = load_dump(path)
    res = []
    for cfg in cfgs:
        flt = UnitFilter(**cfg); d = dict(tot=0, hit=0, fp0=0, fp1=0, frames=0)
        for r in rows:
            lo = [u for u in r['units_lo'] if not u.get('effect') and (extras or not u.get('counted'))]
            P_all = flt(lo)
            tr = r['truth']
            if tr.get('objects_stale'):      # no truth on this frame; the filter state runs on as it would live
                continue
            d['frames'] += 1
            for owner in (0, 1):
                T = [u for u in tr['units'] if u['owner'] == owner]; P = [u for u in P_all if u['owner'] == owner]
                n = len(_greedy(P, T, 1.)); d['tot'] += len(T); d['hit'] += n; d[f'fp{owner}'] += len(P)-n
        res.append(d)
    return res


def score(ds):
    s = {k: sum(d[k] for d in ds) for k in ds[0]}
    R = s['hit']/max(1, s['tot']); f0, f1 = s['fp0']/s['frames'], s['fp1']/s['frames']
    return dict(recall=round(R, 4), fp_per_frame_own=round(f0, 4), fp_per_frame_opp=round(f1, 4), proxy=round(A_RECALL*R-B_FP*(f0+f1), 4))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dump'); ap.add_argument('out')
    ap.add_argument('--count-extras', action='store_true'); ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--grid', choices=('main', 'edge'), default='main')
    a = ap.parse_args(); cfgs = grid() if a.grid == 'main' else grid_edge()
    files = sorted(Path(a.dump).glob('*.jsonl.gz'))
    with Pool(a.workers) as pool:
        per = pool.map(job, [(f, cfgs, a.count_extras) for f in files])
    rows = []
    for k, cfg in enumerate(cfgs):
        rows.append(dict(cfg=cfg, even=score([per[i][k] for i in range(0, len(files), 2)]),
                         odd=score([per[i][k] for i in range(1, len(files), 2)]), all=score([per[i][k] for i in range(len(files))])))
    best = max(rows, key=lambda r: r['even']['proxy'])
    rows.sort(key=lambda r: -r['all']['proxy'])
    Path(a.out).write_text(json.dumps(dict(dump=a.dump, count_extras=a.count_extras, selected_on_even=best, rows=rows), indent=1))
    print('SELECTED (even):', json.dumps(best))
    for r in rows[:10]:
        print(json.dumps(r['cfg']), 'all', r['all'])
    for r in rows:
        if r['cfg'] in (dict(hi=.5, lo=.5), dict(hi=.55, lo=.55)):
            print('plain', json.dumps(r['cfg']), 'all', r['all'], 'odd', r['odd'])


if __name__ == '__main__':
    main()
