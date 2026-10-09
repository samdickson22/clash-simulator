"""Check direct tower joins agree with the diagnostic's duplicate safeguards."""
from collections import defaultdict, Counter
import json
from pathlib import Path
import sys
from extract import rows, ANCHORS

source,manifest,output = map(Path,sys.argv[1:])
study = json.loads(manifest.read_text())
counts = Counter()
for ep in study['fit']+study['dev']:
    receipt = json.loads((source/ep/'receipt.json').read_text())
    if receipt['split'] != 'train':
        raise ValueError('Forbidden membership')
    grouped = defaultdict(list)
    for row in rows(source/ep/'rich-objects.jsonl.gz'):
        grouped[row['tick']].append({o['nativeObjectId']:o for o in row['objects']})
    for snapshots in grouped.values():
        if len(snapshots) < 2:
            continue
        counts['repeated_rich_ticks'] += 1
        for identity in set().union(*(set(s) for s in snapshots)):
            objects = [s.get(identity) for s in snapshots]
            if not any(o is not None and o.get('cardId') == -1 for o in objects):
                continue
            def signature(o):
                if o is None:
                    return None
                return tuple(o.get(k) for k in ['owner','cardId','dataGlobalId','x','y','hp','maxHp','visibilityState'])+((o.get('phaseRuntime') or {}).get('deployRemainingMs'),)
            counts['conflicting_repeated_towers'] += any(signature(o) != signature(objects[0]) for o in objects)
    for row in rows(source/ep/'objects.jsonl.gz'):
        for s,(owner,x,y) in enumerate(ANCHORS):
            candidates = [o for o in row['objects'] if (o.get('owner'),o.get('card_id'),o.get('x'),o.get('y'),o.get('max_hp')) ==
                          (owner,-1,int(x*1000),int(y*1000),4824 if s%3 == 0 else 3052)]
            counts['duplicate_ordinary_towers'] += len(candidates) > 1
    counts['matches'] += 1
result = dict(counts=counts,diagnostic_tower_join_equivalent=not counts['conflicting_repeated_towers'] and not counts['duplicate_ordinary_towers'],
              validation_payloads_opened=False,heldout_payloads_opened=False)
output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
