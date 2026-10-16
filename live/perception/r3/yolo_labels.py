"""Point labels (tiles, ground position) -> YOLO detection labels on the official capture frames.

Class = KataCR unit name (body level, e.g. 'spear-goblin', 'skeleton', 'goblin-cage') and team = 0 ours / 1 opponent (KataCR's
'belong'); the YOLO class id is `name_team` from classes.txt. Boxes are DRAFTS from per-class size priors anchored at the ground
point (feet) unless a label already has `box_px` (capture pixels x1, y1, x2, y2), which wins. Off-vocabulary / UNKNOWN units are
written with class 'unknown' so they can be ignored or kept.

Outputs per frame: OUT/labels/<id>.txt (YOLO: cls cx cy w h, normalised to the capture), OUT/boxes/<id>.json (pixel boxes + names),
OUT/classes.txt, OUT/index.json (id -> source image path, split, arena, battle).

  python yolo_labels.py LABEL_DIR INDEX_JSON OUT_DIR --split train|heldout [--classes KATACR_LABEL_LIST.py]
"""
import argparse
import json
import re
import sys
from pathlib import Path

import cv2

R = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R/'live/loop')]
import canvas as LC  # noqa: E402

# our card/body -> KataCR unit name (body level)
BODY = {'Barbarian': 'barbarian', 'Golemite': 'golemite', 'SpearGoblin': 'spear-goblin', 'Skeleton': 'skeleton', 'GoblinBrawler': 'goblin-brawler', 'GoblinCage': 'goblin-cage',
        'Tombstone': 'tombstone', 'Bomber': 'bomber'}
CARD = {'Archers': 'archer', 'Minions': 'minion', 'MinionHorde': 'minion', 'Knight': 'knight', 'Giant': 'giant',
        'MiniPekka': 'mini-pekka', 'Musketeer': 'musketeer', 'Goblins': 'goblin', 'GoblinHut': 'goblin-hut', 'Valkyrie': 'valkyrie',
        'Skeletons': 'skeleton', 'SkeletonArmy': 'skeleton', 'Bats': 'bat', 'BabyDragon': 'baby-dragon', 'HogRider': 'hog-rider',
        'Prince': 'prince', 'DarkPrince': 'dark-prince', 'Wizard': 'wizard', 'Princess': 'princess', 'Cannon': 'cannon',
        'Tesla': 'tesla', 'InfernoTower': 'inferno-tower', 'BombTower': 'bomb-tower', 'IceSpirit': 'ice-spirit',
        'ElectroSpirit': 'electro-spirit', 'FireSpirits': 'fire-spirit', 'Firecracker': 'firecracker', 'Balloon': 'balloon',
        'Golem': 'golem', 'IceGolem': 'ice-golem', 'Miner': 'miner', 'Wallbreakers': 'wall-breaker', 'RoyalHogs': 'royal-hog',
        'Bomber': 'bomber', 'Tombstone': 'tombstone', 'GoblinCage': 'goblin-cage', 'SpearGoblins': 'spear-goblin',
        'Barbarians': 'barbarian', 'OOV:Barbarians': 'barbarian', 'BarbarianHut': 'barbarian-hut', 'OOV:BarbarianHut': 'barbarian-hut',
        'BattleRam': 'battle-ram', 'OOV:BattleRam': 'battle-ram', 'MegaMinion': 'mega-minion', 'OOV:MegaMinion': 'mega-minion',
        'Mortar': 'mortar', 'OOV:Mortar': 'mortar', 'FlyingMachine': 'flying-machine', 'OOV:FlyingMachine': 'flying-machine',
        'OOV:GoblinCage': 'goblin-cage', 'OOV:GoblinBrawler': 'goblin-brawler', 'OOV:Bomber': 'bomber', 'OOV:Tombstone': 'tombstone',
        'Witch': 'witch', 'OOV:Witch': 'witch', 'AngryBarbarians': 'elite-barbarian', 'Xbow': 'x-bow', 'Rascals': 'rascal-boy', 'MightyMiner': 'mighty-miner', 'ArcherQueen': 'archer-queen'}
# size prior (tiles): width, height above the ground point, depth below it
SIZE = {'giant': (2.2, 3.2, .5), 'goblin-hut': (2.6, 3.0, .9), 'goblin-cage': (2.4, 2.8, .8), 'tombstone': (1.9, 2.4, .7),
        'mini-pekka': (1.5, 2.2, .4), 'knight': (1.4, 2.1, .4), 'valkyrie': (1.5, 2.1, .4), 'musketeer': (1.3, 2.1, .4),
        'goblin-brawler': (1.6, 2.2, .4), 'bomber': (1.2, 1.8, .4), 'minion': (1.3, 2.6, .3), 'baby-dragon': (2.2, 3.4, .3),
        'balloon': (2.2, 4.2, .3), 'bat': (1.0, 2.2, .3)}
DEFAULT = (1.1, 1.6, .35)


def tile_px(x, y, w, h):
    cx, cy = LC.TILE_B+LC.TILE_A*x, LC.TILE_D+LC.TILE_C*y
    ax, ay = LC.ARENA_S*cx+LC.ARENA_T[0], LC.ARENA_S*cy+LC.ARENA_T[1]
    return ax*w/LC.W, ay*h/LC.H


def katacr_names(path):
    ns = {}
    exec(Path(path).read_text(), ns)  # KataCR's label_list.py (constants only)
    return list(ns['unit_list'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('labels', type=Path); p.add_argument('index', type=Path); p.add_argument('out', type=Path)
    p.add_argument('--split', required=True)
    p.add_argument('--classes', default='/mpac/sdicks02/jobs/clasher/katacr-20261016/src/katacr/constants/label_list.py')
    a = p.parse_args()
    for sub in ('labels', 'boxes'):
        (a.out/sub).mkdir(parents=True, exist_ok=True)
    names = katacr_names(a.classes)+['unknown']
    classes = [f'{n}_{t}' for n in names for t in (0, 1)]
    (a.out/'classes.txt').write_text('\n'.join(classes)+'\n')
    ix = {x['id']: x for x in json.loads(a.index.read_text())}
    idx_path = a.out/'index.json'
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    tile_px_w = LC.ARENA_S*LC.TILE_A
    missing = {}
    for f in sorted(a.labels.glob('*.json')):
        lab = json.loads(f.read_text())
        if lab.get('exclude') or lab['id'] not in ix:
            continue
        src = ix[lab['id']]['source']; im = cv2.imread(src)
        h, w = im.shape[:2]; sx = w/LC.W
        rows, boxes = [], []
        for u in lab['units']:
            name = BODY.get(u.get('body')) or CARD.get(u['card'])
            if name is None or name not in names:
                missing[u['card']] = missing.get(u['card'], 0)+1; name = 'unknown'
            team = 0 if u['owner'] == 'us' else 1
            if u.get('box_px'):
                x1, y1, x2, y2 = u['box_px']; draft = False
            else:
                gx, gy = tile_px(float(u['x']), float(u['y']), w, h)
                bw, up, dn = SIZE.get(name, DEFAULT); t = tile_px_w*sx
                x1, x2, y1, y2 = gx-bw*t/2, gx+bw*t/2, gy-up*t, gy+dn*t; draft = True
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
            c = classes.index(f'{name}_{team}')
            rows.append(f'{c} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}')
            boxes.append(dict(name=name, team=team, card=u['card'], body=u.get('body'), box_px=[round(v, 1) for v in (x1, y1, x2, y2)],
                              draft=draft, ground_tile=[u['x'], u['y']], conf=u.get('conf')))
        (a.out/'labels'/f"{lab['id']}.txt").write_text('\n'.join(rows)+('\n' if rows else ''))
        (a.out/'boxes'/f"{lab['id']}.json").write_text(json.dumps(dict(id=lab['id'], source=src, size=[w, h], units=boxes), indent=1))
        index[lab['id']] = dict(source=src, split=a.split, arena=lab['id'].split('-')[0], complete=lab.get('complete', True))
    idx_path.write_text(json.dumps(index, indent=1))
    print(len(index), 'frames; unmapped cards ->unknown:', missing)


if __name__ == '__main__':
    main()
