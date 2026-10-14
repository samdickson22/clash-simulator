"""Pack sealed ExIt game shards into one mmap corpus (frozen imitation.exit_r1.pack).

    python -m bot.exit.pack --games GEN/games [GEN2/games ...] --out PACKED [--limit N]

--limit packs only the first N shards (sorted), via a symlink farm, for quick trainer tests.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--games', nargs='+', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args(argv)
    from bot.exit.train import bootstrap
    bootstrap()
    from imitation.exit_r1.pack import pack
    roots = a.games
    if a.limit:
        farm = a.out.parent / f'.farm-{a.out.name}'
        farm.mkdir(parents=True, exist_ok=False)
        shards = sorted(p for r in a.games for p in r.glob('game-*') if (p / 'manifest.json').exists())[:a.limit]
        for p in shards:
            (farm / p.name).symlink_to(p.resolve())
        roots = [farm]
    seal = pack(roots, a.out)
    print(json.dumps(dict(out=str(a.out), rows=seal['rows'], totals=seal['totals'])))


if __name__ == '__main__':
    sys.exit(main())
