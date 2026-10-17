"""05: deduped coverage (class x team x phase) over night-label-3 frames, thresholds, and targeted queue items.

  python -B coverage_dedup.py [--write-queue]

Deduped instance = distinct (run, object_id, tick // 8): near-duplicate adjacent frames count once.
Only bodies whose identity was learned from our deploys (body_source empirical) count.
Thresholds (LEAD 10-17): problem cards >= 200 deduped per class x team (all phases); every other class >= 50 per
class x team x core phase (deploy, walk*, attack_windup, attack_hit, stunned, frozen; *walk only for troops).
Writes /mpac/sdicks02/scratch/nulls/coverage-night-dedup.{json,md}; --write-queue prints targeted items for deficits.
"""
import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
NIGHT = '/mpac/sdicks02/scratch/nulls/night'
OUT = Path('/mpac/sdicks02/scratch/nulls')
CARDS = json.loads((HERE.parent / 'cards.json').read_text())
BODY_MAP = json.loads((HERE / 'body_name_map.json').read_text())['bodies']
PROBLEM = ['Mortar', 'Tombstone', 'SkeletonDragons', 'BabyDragon', 'SpearGoblins', 'Goblins', 'Barbarians', 'Knight',
           'MiniPekka', 'Giant']
CORE = ['deploy', 'walk', 'attack_windup', 'attack_hit', 'stunned', 'frozen']


def class_of_card(c):
    names = []
    for b in c.get('bodies') or []:
        e = BODY_MAP.get(b) or {}
        names.append(e.get('name') or e.get('proposed_name'))
    return [n for n in names if n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-queue', action='store_true')
    a = ap.parse_args()
    cells = defaultdict(set)
    frames = 0
    for f in glob.glob(f'{NIGHT}/i*/*/chunk-*/*.json'):
        if '/raw-' in f:
            continue
        try:
            rec = json.loads(Path(f).read_text())
        except (OSError, ValueError):
            continue
        if rec.get('version') != 'night-label-3' or rec.get('purpose') != 'scene':
            continue
        frames += 1
        b = rec['tick'] // 8
        for o in rec['objects']:
            if o['kind'] in ('unit', 'building') and o.get('body_source') == 'empirical' and o.get('class_name'):
                cells[(o['class_name'], o['team'], o['phase'])].add((rec['run'], o['object_id'], b))
                if o.get('hp_bar_visible'):
                    cells[(o['class_name'], o['team'], 'hp_bar')].add((rec['run'], o['object_id'], b))
    cnt = {k: len(v) for k, v in cells.items()}
    classes = sorted({k[0] for k in cnt})
    table = {c: {t: {p: cnt.get((c, t, p), 0) for p in CORE + ['attack_recovery', 'idle', 'death', 'hp_bar']}
                 for t in (0, 1)} for c in classes}
    deficits = []
    for card in CARDS:
        if not card.get('in_nulls') or card['kind'] == 'spell':
            continue
        for cls in class_of_card(card)[:1]:
            for t in (0, 1):
                row = (table.get(cls) or {}).get(t) or {}
                if card['name'] in PROBLEM:
                    tot = sum(row.get(p, 0) for p in CORE + ['attack_recovery', 'idle'])
                    if tot < 200:
                        deficits.append(dict(card=card['name'], cls=cls, team=t, phase='all', have=tot, need=200))
                for p in CORE:
                    if p == 'walk' and card['kind'] == 'building':
                        continue
                    if row.get(p, 0) < 50:
                        deficits.append(dict(card=card['name'], cls=cls, team=t, phase=p, have=row.get(p, 0), need=50))
    out = dict(frames=frames, table=table, deficits=deficits)
    (OUT / 'coverage-night-dedup.json').write_text(json.dumps(out, indent=1))
    cols = CORE + ['attack_recovery', 'death', 'hp_bar']
    lines = [f'# Null\'s night coverage, deduped (distinct run x object x 8-tick bucket); {frames} night-label-3 frames',
             '', 'Identity learned from our own deploys only. Team 0 = ours/bottom, 1 = opp/top.', '',
             '|class|team|' + '|'.join(cols) + '|', '|---|---|' + '---:|' * len(cols)]
    for c in classes:
        for t in (0, 1):
            lines.append(f'|{c}|{t}|' + '|'.join(str(table[c][t].get(p, 0)) for p in cols) + '|')
    lines += ['', f'Deficits vs thresholds: {len(deficits)} cells']
    (OUT / 'coverage-night-dedup.md').write_text('\n'.join(lines) + '\n')
    by_card = defaultdict(int)
    for d in deficits:
        by_card[d['card']] += 1
    print(frames, 'frames;', len(classes), 'classes;', len(deficits), 'deficit cells;', len(by_card), 'cards')
    if a.write_queue:
        # one extra duel per 3 deficit cells (max 3) per card; problem-card shortfalls first
        items = []
        for card, n in sorted(by_card.items(), key=lambda kv: (kv[0] not in PROBLEM, -kv[1])):
            items.append(f'{card}*{min(3, max(1, n // 3))}')
        print(json.dumps(items))


if __name__ == '__main__':
    main()
