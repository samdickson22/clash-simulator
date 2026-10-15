"""Markdown table from totality-{pinned,total}[-scrub].json in DIR."""
import collections
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
R = {t: json.loads((d / f'totality-{t}.json').read_text()) for t in ('pinned-scrub', 'total-scrub', 'pinned', 'total')}


def cnt(s):
    return collections.Counter(v.split(':')[0] for x in s['failures'].values() for v in x.values())


print('| scenario | cut states × probes | pinned panics (scrub / no-scrub) | patched panics (scrub / no-scrub) | patched ValueError (scrub / no-scrub) |')
print('|---|---|---|---|---|')
tot = collections.Counter()
for n in R['pinned']['scenarios']:
    c = {t: cnt(R[t]['scenarios'][n]) for t in R}
    s = R['pinned-scrub']['scenarios'][n]
    print(f"| {n} | {s['cuts']} × {s['probes'] // s['cuts']} | {c['pinned-scrub']['PanicException']} / {c['pinned']['PanicException']} "
          f"| {c['total-scrub']['PanicException']} / {c['total']['PanicException']} "
          f"| {c['total-scrub']['ValueError']} / {c['total']['ValueError']} |")
    tot['probes'] += s['probes']
    for t in R:
        tot[t + ' panic'] += c[t]['PanicException']
        tot[t + ' ValueError'] += c[t]['ValueError']
print()
print(json.dumps(dict(tot)))
