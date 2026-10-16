"""Write a scratch gamedata.json with stat-value corrections applied (stand-in for the live16402 overlay).

Usage: apply_stats.py IN_GAMEDATA SPEC.json OUT_GAMEDATA
SPEC rows: {"card": <card name or "*">, "body": <nested object name>, "field": <key>, "value": <int>}.
Every dict named `body` inside the matching card entry (base form only: evolved/hero payloads are skipped) gets
field=value. Output stays outside git (derived stat tables are never committed).
"""
import json, sys

src, spec, out = sys.argv[1:4]
data = json.load(open(src))
rows = json.load(open(spec))
hits = {i: 0 for i in range(len(rows))}


def walk(o, card):
    if isinstance(o, dict):
        for i, r in enumerate(rows):
            if r['card'] in ('*', card) and o.get('name') == r['body'] and r['field'] in o:
                o[r['field']] = r['value']; hits[i] += 1
        for k, v in o.items():
            if k not in ('evolvedSpellsData', 'heroData'):
                walk(v, card)
    elif isinstance(o, list):
        for v in o:
            walk(v, card)


for entry in data['items']['spells']:
    walk(entry, entry.get('name'))
missing = [rows[i] for i, n in hits.items() if n == 0]
if missing:
    sys.exit(f'rows matched nothing: {missing}')
json.dump(data, open(out, 'w'))
print({f"{r['card']}/{r['body']}.{r['field']}": hits[i] for i, r in enumerate(rows)})
