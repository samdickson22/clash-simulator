"""Record real search roots (R.root as the planner builds them) as snapshots, for native parity checks.

    python record_roots.py --out DIR --index I [--player K4S-m2] [--opponent R3a] [--every 3]

Plays x4s case I (fresh exploration bank, not HEADLINE) with the pinned runtime and writes
DIR/roots-<I>.jsonl.gz: one line per kept root {index, n, tick, seat, head, tail} (snapshot minus config)
and DIR/config.json once (the shared config text, sha-checked per root).
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, '/mpac/sdicks02/repos/clasher-bot')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--index', type=int, required=True)
    ap.add_argument('--player', default='K4S-m2')
    ap.add_argument('--opponent', default='R3a')
    ap.add_argument('--every', type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    from bot.players.runtime import Runtime
    rt = Runtime()
    from bot.players.ours import play_match, x4s_setup
    from bot.eval.headline import HEADLINE_BASE, make_player
    from bot.search.lopp_fast import split_snapshot
    R = rt.R
    real_root = R.root
    rows, n = [], [0]
    cfg_sha = [None]

    def spy(info, opponent, rng):
        root = real_root(info, opponent, rng)
        n[0] += 1
        if n[0] % a.every == 0:
            head, cfg, tail = split_snapshot(root.snapshot())
            h = hashlib.sha256(cfg.encode()).hexdigest()
            if cfg_sha[0] is None:
                cfg_sha[0] = h
                p = out / f'config-{h[:16]}.json'
                if not p.exists():
                    p.write_text(cfg)
            rows.append(dict(index=a.index, n=n[0], tick=int(info.tick), seat=int(info.seat), config=h,
                             head=head, tail=tail))
        return root
    R.root = spy
    case = x4s_setup(rt, a.index, HEADLINE_BASE + 9 * 10**6)
    players = {case['seat']: make_player(rt, a.player), 1 - case['seat']: make_player(rt, a.opponent)}
    res = play_match(rt, players, seed=case['seed'], decks=case['decks'], max_ticks=6001)
    tmp = out / f'roots-{a.index:03d}.jsonl.gz.tmp'
    with gzip.open(tmp, 'wt') as fh:
        for r in rows:
            fh.write(json.dumps(r) + '\n')
    tmp.rename(out / f'roots-{a.index:03d}.jsonl.gz')
    print(json.dumps(dict(index=a.index, roots_seen=n[0], kept=len(rows), ticks=res.get('ticks') if isinstance(res, dict) else None)))


if __name__ == '__main__':
    main()
