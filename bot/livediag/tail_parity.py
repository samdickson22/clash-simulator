"""Identical-action parity between two tail_profile outputs: every reduce call's (tick, best) per battle."""
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
tot = diff = 0
for run in a:
    ra, rb = a[run]['reduce'], b[run]['reduce']
    sa = [(r['tick'], r['best'], r['candidates']) for r in ra]; sb = [(r['tick'], r['best'], r['candidates']) for r in rb]
    d = sum(x != y for x, y in zip(sa, sb)) + abs(len(sa) - len(sb))
    tot += max(len(sa), len(sb)); diff += d
    print(run, len(sa), len(sb), 'differ', d, 'errors', len(a[run]['errors']), len(b[run]['errors']), 'cutoffs', a[run]['cutoffs'], b[run]['cutoffs'])
print('TOTAL', tot, 'differ', diff)
