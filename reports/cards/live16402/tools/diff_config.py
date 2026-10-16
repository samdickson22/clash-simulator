"""Compare two dump_config.py dumps (base vs live16402) against the overlay receipt: which changed cards reach the
engine config / native metadata, and which do not (masked by engine overrides or unused fields). Prints names and
counts only.

    python -I diff_config.py BASE.json LIVE.json LIVE16402-RECEIPT.json [OUT.json]
"""
import json
import sys


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            walk(a.get(k), b.get(k), f'{path}/{k}', out)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f'{path}[{i}]', out)
    elif a != b:
        out.append(path)


base, live, receipt = (json.load(open(p)) for p in sys.argv[1:4])
changed_cards = set(receipt['changes_by_card'])
out = {}
for table in sorted(set(base['config']) | set(live['config'])):
    a, b = base['config'].get(table, {}), live['config'].get(table, {})
    for card in sorted(set(a) | set(b)):
        d = []
        walk(a.get(card), b.get(card), '', d)
        if d:
            out.setdefault(card, {})[f'config.{table}'] = d
for table in ('cards', 'bodies'):
    a, b = base['meta'].get(table, {}), live['meta'].get(table, {})
    for card in sorted(set(a) | set(b)):
        d = []
        walk(a.get(card), b.get(card), '', d)
        if d:
            out.setdefault(card, {})[f'meta.{table}'] = d
other = []
walk({k: v for k, v in base['meta'].items() if k not in ('cards', 'bodies')},
     {k: v for k, v in live['meta'].items() if k not in ('cards', 'bodies')}, '', other)
costs = []
walk(base['costs'], live['costs'], '', costs)
reached = sorted(c for c in changed_cards if c in out)
silent = sorted(c for c in changed_cards if c not in out)
unexpected = sorted(c for c in out if c not in changed_cards)
res = dict(cards_with_overlay=len(changed_cards), reached_engine=reached, no_engine_change=silent,
           engine_change_without_card_overlay=unexpected, meta_other_paths=other[:50], costs_paths=costs[:50],
           paths=out)
print(json.dumps({k: v for k, v in res.items() if k != 'paths'}, indent=1))
if len(sys.argv) > 4:
    json.dump(res, open(sys.argv[4], 'w'), indent=1, sort_keys=True)
