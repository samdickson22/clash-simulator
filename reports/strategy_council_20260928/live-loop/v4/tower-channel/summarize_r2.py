"""Score persistent destruction after frozen replay; apply predeclared OCR gate."""
from collections import Counter
import json
from pathlib import Path
import sys
import numpy as np
from extract import rows,sha
from truth_r2 import towers
root=Path(sys.argv[1]);source=Path(sys.argv[2]);d=json.loads((root/'dev-result.json').read_text());m=json.loads((root/'manifest.json').read_text())
latched=Counter();king_ends=[];hp_eligible=Counter()
for match in d['matches']:
    ep=match['episode'];truth=json.loads((root/(ep+'.truth.json')).read_text());hits={e['slot']:e['confirmed']['ordinal'] for e in match['events'] if e['confirmed']}
    for i,l in enumerate(truth['labels']):
        for s,hp in enumerate(l['hp']):
            if hp is not None and hp > 0:
                family = 'opp_king' if s == 0 else 'own_king' if s == 3 else 'opp_princess' if s < 3 else 'own_princess'
                hp_eligible[family] += 1
        for s,state in enumerate(l['states']):
            if s%3==0 or state is None:continue
            latched[state+'_truth']+=1
            if i>=hits.get(s,float('inf')):latched[state+'_latched_destroyed']+=1
for ep in m['fit']+m['dev']:
    ordinary=rows(source/ep/'objects.jsonl.gz');receipt=json.loads((source/ep/'receipt.json').read_text());terminal=receipt['terminal'];last=towers(ordinary[-1]);missing=[s for s in (0,3) if s not in last]
    if missing:king_ends.append(dict(episode=ep,missing_king_slots=missing,final_tick=ordinary[-1]['tick'],terminal=terminal))
d['persistent_princess']=dict(latched);d['native_king_terminal_audit']=king_ends
for family,n in hp_eligible.items():d['counts'].setdefault(family,{})['hp_eligible']=n
d['scoring_correction']='Recomputed HP eligibility per family from frozen native labels: opponent King has its own denominator and is excluded from own-princess coverage; predictions/acceptance policy unchanged'
model=json.loads((root/'round2-templates.json').read_text());model['number_enabled'].update(d['number_acceptance_policy']);(root/'deployed-templates.json').write_text(json.dumps(model,separators=(',',':'))+'\n')
d['deployment_policy']=dict(candidate_sha256=sha(root/'round2-templates.json'),deployed_sha256=sha(root/'deployed-templates.json'),changes='Only predeclared per-family >=99% acceptance gate; opponent numbers disabled; no source/template/threshold tuning')
(root/'round2-dev-result.json').write_text(json.dumps(d,indent=2)+'\n');print('persistent',dict(latched),'King terminal absences',king_ends,'deployed',d['deployment_policy'],flush=True)
