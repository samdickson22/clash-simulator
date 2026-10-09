"""Score independently labelled dev crops without changing the frozen model."""
from collections import Counter
import json
from pathlib import Path
import sys

labels = json.loads(Path(sys.argv[1]).read_text())
rows = [json.loads(x) for x in Path(sys.argv[2]).read_text().splitlines()]
predictions = {(r['episode'],r['ordinal'],r['observation']['slot']):r['observation'] for r in rows}
slots = ['opp_king','opp_left','opp_right','own_king','own_left','own_right']
exceptions = {(r['episode'],r['slot']):r['state'] for r in labels['exceptions']}
confusion = {s:{t:Counter() for t in ['alive','destroyed','unknown']} for s in slots}
for sample in labels['samples']:
    ep,i = sample['episode'],sample['ordinal']
    for s,name in enumerate(slots):
        truth = exceptions.get((ep,s),labels['default_state'])
        confusion[name][truth][predictions[ep,i,name]['state']] += 1
out = dict(schema='clasher.public-tower-dev-visual.v1', samples=48,
           confusion={s:{t:dict(c) for t,c in d.items()} for s,d in confusion.items()},
           labels_used_for_fitting=False)
Path(sys.argv[3]).write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
