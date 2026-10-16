"""Shared YOLO class map for the LIVE unit detector: `live/yolo_synth/classes.json` (ONE file for the synth compositor,
the r3 YOLO owner and the live integration).

Names = KataCR `unit_list` (katacr/constants/label_list.py @36ceb9f) in its order, then 'unknown', then any new names
(append-only; existing indices never move). Team/belong 0 = ours (bottom, blue), 1 = opponent (top, red).
  KataCR txt line: `name_idx cx cy w h belong` (normalised to the 568x896 arena crop)
  plain YOLO id:   2*name_idx + belong
Per name: kind (tower|troop|building|spell|object|ui|unknown), layer (KataCR draw level 0 ground spell, 1 ground, 2 air,
3 ui), labelled (the compositor emits boxes for it), card / identity / air from the baseline worker's katacr_to_clasher.json.

  python classes.py build [--label-list P] [--k2c P] [--out classes.json]
  python classes.py append NAME CARD KIND AIR(0|1) [--out classes.json]   # new card body (e.g. from Null's cut-outs)
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KATACR = Path('/mpac/sdicks02/jobs/clasher/katacr-20261016')
DEFAULT_OUT = HERE/'classes.json'
LABELLED_KINDS = ('tower', 'troop', 'building', 'spell', 'object')


def katacr_lists(path):
    ns = {}
    exec(Path(path).read_text(), ns)  # plain list literals (KataCR MIT source, pinned commit)
    return {k: v for k, v in ns.items() if isinstance(v, list)}


def build(label_list, k2c_path):
    L = katacr_lists(label_list)
    k2c = json.loads(Path(k2c_path).read_text())['classes'] if k2c_path and Path(k2c_path).exists() else {}
    ground_spell = set(L['ground_unit_list']) & set(L['spell_unit_list'])
    names = []
    for i, n in enumerate(L['unit_list']):
        m = k2c.get(n, {})
        if n in L['tower_unit_list']:
            kind = 'tower'
        elif n in L['other_unit_list'] or n == 'selected':
            kind = 'ui'
        elif n in L['spell_unit_list']:
            kind = 'spell'
        elif n in L['object_unit_list']:
            kind = 'object'
        elif m.get('kind') == 'building':
            kind = 'building'
        else:
            kind = 'troop'
        if n in ground_spell:
            layer = 0
        elif n in L['flying_unit_list']:
            layer = 2
        elif kind == 'ui':
            layer = 3
        else:
            layer = 1
        names.append(dict(idx=i, name=n, kind=kind, layer=layer, labelled=kind in LABELLED_KINDS,
                          card=m.get('source_card'), identity=m.get('identity'), air=bool(m.get('air', layer == 2)),
                          src='katacr'))
    names.append(dict(idx=len(names), name='unknown', kind='unknown', layer=1, labelled=False, card=None, identity=None,
                      air=False, src='r3'))
    return names


def dump(names, out):
    doc = {
        'version': 1,
        'note': __doc__.split('\n\n')[1] if __doc__ else '',
        'katacr_commit': '36ceb9fcfbd117c2ce3d97eacee435c1898eb7b8',
        'image_space': {'w': 568, 'h': 896, 'crop_in_720x1280': [42.2, 31.3, 674.2, 1019.3]},
        'label_format': 'name_idx cx cy w h belong (normalised); yolo_id = 2*name_idx + belong; belong 0 ours, 1 opp',
        'names': names,
        'classes': [dict(id=2*x['idx']+b, name=x['name'], team=b, card=x['card']) for x in names for b in (0, 1)],
    }
    Path(out).write_text(json.dumps(doc, indent=1)+'\n')


def load(path=DEFAULT_OUT):
    doc = json.loads(Path(path).read_text())
    return doc, {x['name']: x for x in doc['names']}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('--label-list', default=str(KATACR/'src/katacr/constants/label_list.py'))
    b.add_argument('--k2c', default=str(KATACR/'katacr_to_clasher.json'))
    b.add_argument('--out', default=str(DEFAULT_OUT))
    a = sub.add_parser('append')
    a.add_argument('name'); a.add_argument('card'); a.add_argument('kind', choices=LABELLED_KINDS)
    a.add_argument('air', type=int); a.add_argument('--out', default=str(DEFAULT_OUT))
    args = p.parse_args()
    if args.cmd == 'build':
        if Path(args.out).exists():
            old = json.loads(Path(args.out).read_text())['names']
            new = build(args.label_list, args.k2c)
            assert [x['name'] for x in new] == [x['name'] for x in old[:len(new)]], 'build would move existing indices'
            names = new + old[len(new):]  # keep appended names
        else:
            names = build(args.label_list, args.k2c)
    else:
        doc, by = load(args.out)
        names = doc['names']
        if args.name not in by:
            names.append(dict(idx=len(names), name=args.name, kind=args.kind, layer=2 if args.air else 1, labelled=True,
                              card=args.card, identity=args.card, air=bool(args.air), src='appended'))
    dump(names, args.out)
    print(f'{len(names)} names -> {args.out}')


if __name__ == '__main__':
    main()
