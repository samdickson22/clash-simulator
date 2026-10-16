"""Cut-out index for the compositor: BANK/sprites.jsonl, one line per cut-out
{file (relative to BANK), name (classes.json name), belong (0 ours / 1 opp), src, scale (-> 568x896 crop px)}.

  python sprites.py BANK katacr SEGMENT_DIR            # KataCR images/segment (already at crop scale)
  python sprites.py BANK nulls CUTOUTS_DIR [--map M]   # Null's Royale cutouts.jsonl (scale in official capture px)

Each source is (re)written as its own block; sprites.jsonl = concatenation of BANK/sprites-<src>.jsonl.
Null's cut-outs: cutouts.jsonl rows are read tolerantly (card / name, team / belong / owner, path / file / png, scale);
card -> KataCR body name via katacr_to_clasher.json (reverse, `body`) or kebab-case of the card (then `classes.py append`).
"""
import argparse
import json
import re
import shutil
from pathlib import Path

CAPTURE_TO_CROP = (568/632.0 + 896/988.0)/2      # 720x1280 capture px -> crop px (0.8987 x, 0.9069 y)
SKIP = {'backgrounds', 'scoreboard'}


def kebab(card):
    return re.sub(r'(?<!^)(?=[A-Z])', '-', card).lower()


def katacr_rows(seg, bank):
    rows = []
    dst = bank/'sprites'/'katacr'
    for d in sorted(Path(seg).iterdir()):
        if not d.is_dir() or d.name in SKIP:
            continue
        for f in sorted(d.glob('*.png')):
            stem = f.stem
            if d.name == 'background-items':
                name, _, tail = stem.rpartition('_')
                if not name:
                    name = stem
                if name.startswith('scoreboard'):
                    continue
                belong = 0
            else:
                parts = stem.split('_')
                name = parts[0]
                if len(parts) < 3 or not parts[1].isdigit():
                    continue
                belong = int(parts[1])
            (dst/d.name).mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst/d.name/f.name)
            rows.append(dict(file=f'sprites/katacr/{d.name}/{f.name}', name=name, belong=belong, src='katacr', scale=1.0))
    return rows


def nulls_rows(cut_dir, bank, k2c_path):
    cut_dir = Path(cut_dir)
    rev = {}
    if k2c_path and Path(k2c_path).exists():
        for name, m in json.loads(Path(k2c_path).read_text())['classes'].items():
            if m.get('source_card') and m.get('body') == name and m['source_card'] not in rev:
                rev[m['source_card']] = name
    rows, dst = [], bank/'sprites'/'nulls'
    for line in (cut_dir/'cutouts.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        card = r.get('card') or r.get('name')
        path = r.get('path') or r.get('file') or r.get('png')
        team = r.get('team', r.get('belong', r.get('owner')))
        if card is None or path is None or team is None:
            continue
        belong = {'us': 0, 'ours': 0, 'blue': 0, 'friendly': 0, 'opp': 1, 'enemy': 1, 'red': 1}.get(str(team).lower(), team)
        src = Path(path) if Path(path).is_absolute() else cut_dir/path
        if not src.exists():
            continue
        name = r.get('katacr') or r.get('body') or rev.get(card) or kebab(card)
        (dst/name).mkdir(parents=True, exist_ok=True)
        out = dst/name/src.name
        if not out.exists():
            shutil.copy2(src, out)
        scale = float(r.get('scale', 1.0))*CAPTURE_TO_CROP     # scale: cut-out px -> official 720x1280 capture px
        rows.append(dict(file=str(out.relative_to(bank)), name=name, belong=int(belong), src='nulls', scale=round(scale, 5),
                         card=card, state=r.get('state'), frame=r.get('frame')))
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument('bank', type=Path)
    p.add_argument('source', choices=('katacr', 'nulls'))
    p.add_argument('dir', type=Path)
    p.add_argument('--k2c', default='/mpac/sdicks02/jobs/clasher/katacr-20261016/katacr_to_clasher.json')
    a = p.parse_args()
    rows = katacr_rows(a.dir, a.bank) if a.source == 'katacr' else nulls_rows(a.dir, a.bank, a.k2c)
    (a.bank/f'sprites-{a.source}.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
    blocks = sorted(a.bank.glob('sprites-*.jsonl'))
    (a.bank/'sprites.jsonl').write_text(''.join(b.read_text() for b in blocks))
    names = {(r['name'], r['belong']) for r in rows}
    print(f'{a.source}: {len(rows)} cut-outs, {len({n for n, _ in names})} names; sprites.jsonl from {[b.name for b in blocks]}')


if __name__ == '__main__':
    main()
