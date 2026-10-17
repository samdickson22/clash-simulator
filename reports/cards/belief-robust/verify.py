"""Compare gate.sh outputs: python verify.py BEFORE AFTER [AFTER...] -> per-row command hashes, PASS/FAIL.

Rows: k4l/ and k4cw/ (bot.eval.headline games-*.jsonl, keyed by candidate/opponent/index) and fp.jsonl (res_check,
keyed by name/index). PASS iff every arm has the same row set as BEFORE, every row is terminal / error-free, and every
command_sha256 equals BEFORE's.
"""
import glob
import json
import sys
from pathlib import Path


def rows(d):
    out = {}
    for f in sorted(glob.glob(f'{d}/k4l/games-*.jsonl') + glob.glob(f'{d}/k4cw/games-*.jsonl')):
        for line in open(f):
            r = json.loads(line)
            out[('headline', r['candidate'], r['opponent'], r['index'])] = r
    fp = Path(d) / 'fp.jsonl'
    if fp.exists():
        for line in fp.read_text().splitlines():
            r = json.loads(line)
            out[('LIVE-AB1', r['name'], 'R3a', r['index'])] = r
    return out


def main(base, *arms):
    b = rows(base)
    ok = bool(b)
    for arm in arms:
        a = rows(arm)
        same = [k for k in b if k in a and a[k]['command_sha256'] == b[k]['command_sha256']]
        bad = [k for k, r in {**b, **a}.items() if r.get('error') or r.get('terminal') is False]
        ok &= len(same) == len(b) == len(a) and not bad
        print(f'{arm}: {len(same)}/{len(b)} identical ({len(a)} rows), bad rows {bad}')
    for k in sorted(b, key=str):
        print(' | '.join(map(str, k)), b[k]['command_sha256'][:16],
              *[rows(x).get(k, {}).get('command_sha256', '-')[:16] for x in arms])
    print('VERIFY_PASS' if ok else 'VERIFY_FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
