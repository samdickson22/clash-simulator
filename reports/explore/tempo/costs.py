"""Reuse A/B case costs with conservative horizon/timed-wait multipliers."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[3];out=root/'reports/explore/tempo/case-costs.json'
prior=json.loads((root/'reports/explore/search-ab/case-costs.json').read_text());result=dict(prior)
factors={'E':1.05,'H12':1.5,'H16':2.,'W':1.25,'EH':1.6,'EW':1.3,'HW':2.,'EHW':2.1,'BEST':2.1}
for key,v in prior.items():
 if key.endswith('|0'):
  for arm,factor in factors.items():result[key[:-1]+arm]=float(v)*factor
for arm,factor in factors.items():result[arm]=60*factor
result['0']=60.
out.write_text(json.dumps(result)+'\n')
