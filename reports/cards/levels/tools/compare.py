"""Compare HEADLINE rows of two output dirs by (candidate, opponent, index): command_sha256 equal, no errors.

    python reports/cards/levels/tools/compare.py BEFORE_DIR AFTER_DIR [--json]
"""
import json
import sys
from pathlib import Path


def rows(d):
    out = {}
    for p in sorted(Path(d).glob('games-*.jsonl')):
        for line in p.read_text().splitlines():
            r = json.loads(line)
            out[(r['candidate'], r['opponent'], r['index'])] = r
    return out


def main():
    a, b = rows(sys.argv[1]), rows(sys.argv[2])
    table = []
    for k in sorted(set(a) | set(b)):
        x, y = a.get(k, {}), b.get(k, {})
        sx, sy = x.get('command_sha256'), y.get('command_sha256')
        table.append(dict(candidate=k[0], opponent=k[1], case=k[2], before=(sx or x.get('error', 'missing'))[:16],
                          after=(sy or y.get('error', 'missing'))[:16], equal=bool(sx) and sx == sy,
                          score=y.get('score')))
    same = sum(r['equal'] for r in table)
    if '--json' in sys.argv:
        print(json.dumps(dict(equal=same, total=len(table), rows=table), indent=1))
        return
    for r in table:
        print(f"{r['candidate']:<22} {r['opponent']:<5} {r['case']:>3}  {r['before']}  {r['after']}  "
              f"{'EQUAL' if r['equal'] else 'DIFF'}")
    print(f'{same}/{len(table)} identical')


if __name__ == '__main__':
    main()
