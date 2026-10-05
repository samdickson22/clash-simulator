"""Join disjoint, actually replayed rows; require full admitted identity."""
import json
from pathlib import Path
import sys
C=Path(__file__).resolve().parent
sys.path.insert(0,str(C.parent))
from broad_identity import provenance
base=json.loads((C.parent/'recorded_identity_baseline_admitted.json').read_text())
prefix=json.loads((C/'recorded_workspace_prefix.json').read_text())
tail=json.loads((C/'recorded_workspace_tail.json').read_text())
assert not prefix['mismatches'] and not tail['mismatches']
assert prefix['provenance'] == tail['provenance'] == provenance()
assert set(tail['results']) == {'0','1','2'}
rows={str(i):prefix['results'][str(i)] for i in range(5)}
rows.update({str(i+5):tail['results'][str(i)] for i in range(3)})
assert rows == base['results']
prefix['results']=rows
p=C/'recorded_workspace.merged.tmp'
p.write_text(json.dumps(prefix,indent=2)+'\n')
p.replace(C/'recorded_workspace.json')
(C/'recorded_merge.json').write_text(json.dumps({'prefix_indices':[0,1,2,3,4],'tail_indices':[5,6,7],'checked':8,'mismatches':[]},indent=2)+'\n')
print('All 8 actually replayed workspace rows equal the admitted baseline.')
