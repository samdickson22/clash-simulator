"""05: deduped, prioritised frame list for Sol box correction (LEAD 10-17 option a), pre-filled with our best boxes.

  python -B make_correction_list.py OUT_DIR [--total 500] [--per-run 10]

Priority: 1 mirror matchups (`-mirror` runs), 2 our Bats swarms (>= 3 team-0 bats), 3 problem cards, 4 our deck.
Dedup within a run: frames >= 8 ticks apart with a new (class, team, phase) signature first, then spacing only.
Per object prefill: box (x1h_agreed) > box_det > box_diff > box_fit, with `prefill_source`.
Writes OUT_DIR/list.json (ordered) and OUT_DIR/frames/<stem>.json (frame path + objects + exact identity/team/phase).
"""
import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

NIGHT = '/mpac/sdicks02/scratch/nulls/night'
PROBLEM = ['Mortar', 'Tombstone', 'SkeletonDragons', 'BabyDragon', 'SpearGoblins', 'Goblins', 'Barbarians', 'Knight']
DECK = ['Valkyrie', 'Archer', 'Bats', 'Cannon', 'MiniPekka', 'Giant']


def priority(rec):
    run, card = rec['run'], rec.get('card')
    if '-mirror' in run:
        return 1
    if card == 'Bats' and sum(o['class_name'] == 'bat' and o['team'] == 0 for o in rec['objects']) >= 3:
        return 2
    if card in PROBLEM:
        return 3
    if card in DECK:
        return 4
    return None


def prefill(o):
    for key, src in (('box', 'x1h_agreed'), ('box_det', 'x1h'), ('box_diff', 'diff'), ('box_fit', 'anchor_fit')):
        if o.get(key):
            return o[key], src
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out', type=Path)
    ap.add_argument('--total', type=int, default=500)
    ap.add_argument('--per-run', type=int, default=10)
    a = ap.parse_args()
    (a.out / 'frames').mkdir(parents=True, exist_ok=True)
    by_run = defaultdict(list)
    for f in glob.glob(f'{NIGHT}/i*/*/chunk-*/*.json'):
        if '/raw-' in f:
            continue
        try:
            rec = json.loads(Path(f).read_text())
        except (OSError, ValueError):
            continue
        if rec.get('version') != 'night-label-3' or rec.get('purpose') != 'scene' or not rec.get('sync') \
                or rec.get('render_fresh') is False:
            continue
        bodies = [o for o in rec['objects'] if o['kind'] in ('unit', 'building') and o['phase'] != 'death'
                  and o.get('visibility', 'visible') == 'visible']
        if not bodies or any(o.get('body_source') != 'empirical' for o in bodies):
            continue  # identity must be exact for every body in the frame
        pr = priority(rec)
        if pr is None:
            continue
        sig = frozenset((o['class_name'], o['team'], o['phase'].split('_')[0]) for o in bodies)
        by_run[(pr, rec['run'])].append((rec['tick'], f, rec, bodies, sig))
    picked = []
    for (pr, run), frames in sorted(by_run.items()):
        frames.sort(key=lambda t: t[0])
        chosen, seen, last = [], set(), -99
        for t in frames:  # new signatures first
            if t[4] - seen and t[0] - last >= 8:
                chosen.append(t); seen |= t[4]; last = t[0]
        for t in frames:  # then spacing
            if len(chosen) >= a.per_run:
                break
            if t not in chosen and all(abs(t[0] - c[0]) >= 8 for c in chosen):
                chosen.append(t)
        picked += [(pr, run, t) for t in sorted(chosen[:a.per_run], key=lambda t: t[0])]
    # interleave runs within each priority so the list is diverse when cut short
    out, per_pri = [], defaultdict(lambda: defaultdict(list))
    for pr, run, t in picked:
        per_pri[pr][run].append(t)
    for pr in sorted(per_pri):
        runs = list(per_pri[pr].values())
        while any(runs):
            for r in runs:
                if r:
                    out.append((pr, r.pop(0)))
    out = out[:a.total]
    listing = []
    for pr, (tick, f, rec, bodies, sig) in out:
        stem = Path(f).stem
        objs = []
        for o in bodies:
            b, src = prefill(o)
            objs.append(dict(object_id=o['object_id'], class_name=o['class_name'], class_idx=o['class_idx'],
                             in_vocab=o['in_vocab'], team=o['team'], kind=o['kind'], phase=o['phase'],
                             hp_frac=o['hp_frac'], hp_bar_visible=o['hp_bar_visible'], anchor_px=o['anchor_px'],
                             box_prefill=b, prefill_source=src, box_det=o.get('box_det'), box_diff=o.get('box_diff'),
                             box_fit=o.get('box_fit'), det_conf=o.get('det_conf')))
        item = dict(priority=pr, run=rec['run'], card=rec.get('card'), tick=tick, label=f,
                    frame=str(Path(f).parent / rec['frame']), arena_calib=rec.get('arena_calib'),
                    viewport=rec.get('viewport'), hand=rec.get('hand'), objects=objs)
        (a.out / 'frames' / f'{stem}.json').write_text(json.dumps(item, indent=1))
        listing.append(dict(priority=pr, run=rec['run'], stem=stem, n_objects=len(objs),
                            frame=item['frame'], json=str(a.out / 'frames' / f'{stem}.json')))
    (a.out / 'list.json').write_text(json.dumps(listing, indent=1))
    from collections import Counter
    print(len(listing), 'frames', Counter(x['priority'] for x in listing), sum(x['n_objects'] for x in listing), 'objects')


if __name__ == '__main__':
    main()
