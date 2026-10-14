"""Pack sealed ExIt game shards into one mmap corpus (frozen imitation.exit_r1.pack).

    python -m bot.exit.pack --games GEN/games [GEN2/games ...] --out PACKED [--limit N]
        [--teacher K4C-r16] [--student SUBSTR] [--exclude PACKED ...] [--max-rows N --select-seed S]

--limit packs only the first N shards (sorted), via a symlink farm, for quick trainer tests.
--teacher / --student keep only shards whose receipt.json teacher equals / student contains the value.
--exclude drops shards already in earlier packs (their sources.json), so successive packs are disjoint.
--max-rows keeps a seeded random subset of the (filtered) shards, adding whole shards while the total stays <= N rows
(for size-matched label-quality tests). Any filter packs through a symlink farm next to --out.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path


def select(roots, teacher=None, student=None, max_rows=None, seed=0, exclude=()):
    shards = sorted(p for r in roots for p in r.glob('game-*') if (p / 'manifest.json').exists())
    done = {g['path'] for d in exclude for g in json.loads((d / 'sources.json').read_text())['games']}
    keep = []
    for p in shards:
        if str(p.resolve()) in done:
            continue
        rec = json.loads((p / 'receipt.json').read_text())
        if teacher is not None and rec.get('teacher') != teacher:
            continue
        if student is not None and student not in rec.get('student', ''):
            continue
        keep.append((p, int(rec['rows'])))
    if max_rows is not None:
        random.Random(seed).shuffle(keep)
        out, total = [], 0
        for p, n in keep:
            if total + n <= max_rows:
                out.append((p, n)); total += n
        keep = sorted(out)
    return keep


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', nargs='+', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--teacher')
    ap.add_argument('--student')
    ap.add_argument('--exclude', nargs='*', default=[], type=Path)
    ap.add_argument('--max-rows', type=int)
    ap.add_argument('--select-seed', type=int, default=0)
    a = ap.parse_args(argv)
    from bot.exit.train import bootstrap
    bootstrap()
    from imitation.exit_r1.pack import pack
    roots = a.games
    filtered = (a.teacher is not None or a.student is not None or a.max_rows is not None
                or bool(a.exclude))
    if a.limit or filtered:
        farm = a.out.parent / f'.farm-{a.out.name}'
        farm.mkdir(parents=True, exist_ok=False)
        if filtered:
            keep = select(a.games, a.teacher, a.student, a.max_rows, a.select_seed, a.exclude)
            shards = [p for p, _ in keep]
            print(json.dumps(dict(selected_shards=len(shards), selected_rows=sum(n for _, n in keep))), flush=True)
        else:
            shards = sorted(p for r in a.games for p in r.glob('game-*') if (p / 'manifest.json').exists())
        for p in shards[:a.limit] if a.limit else shards:
            (farm / p.name).symlink_to(p.resolve())
        roots = [farm]
    seal = pack(roots, a.out)
    print(json.dumps(dict(out=str(a.out), rows=seal['rows'], totals=seal['totals'])))


if __name__ == '__main__':
    sys.exit(main())
