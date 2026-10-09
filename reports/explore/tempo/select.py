"""Small fixed menu selection using tuning seeds only; no reporting outcomes."""
import argparse,json
from pathlib import Path
from collections import defaultdict
p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--combination',action='store_true');p.add_argument('--prior',type=Path);a=p.parse_args()
rows=defaultdict(dict)
for f in (a.games.glob('*/games/*.json') if a.combination else a.games.glob('*.json')):
 r=json.loads(f.read_text());assert r['role']=='exploration' and r['metadata']['terminal'];rows[r['cohort']][r['metadata']['seed']]=r
expected=['0','EH','EW','HW','EHW'] if a.combination else ['0','Elo','Ehi','H12','H16','Wlo','Whi']
assert set(rows)==set(expected) and all(len(rows[k])==150 and rows[k].keys()==rows['0'].keys() for k in expected)
# First loss count; ties choose the cheaper/weaker intervention. Diagnostic
# economy metrics do not enter selection and are not optimized as surrogate wins.
losses={k:sum(r['loss'] for r in rows[k].values()) for k in expected}
if a.combination:
 result=json.loads(a.prior.read_text());menu=['EW','EH','HW','EHW'];winner=min(menu,key=lambda k:(losses[k],menu.index(k)))
 result.update(combination_arm=winner,combination_tuning=dict(losses=losses,seeds=sorted(rows['0']),selection='fewest losses, then fixed EW/EH/HW/EHW tie order; no reporting outcome access'))
else:
 e=min(['Elo','Ehi'],key=lambda k:(losses[k],['Elo','Ehi'].index(k)));w=min(['Wlo','Whi'],key=lambda k:(losses[k],['Wlo','Whi'].index(k)));h=min(['H12','H16'],key=lambda k:(losses[k],['H12','H16'].index(k)))
 result=dict(elixir_weight=.005 if e=='Elo' else .02,wait_prior=.0025 if w=='Wlo' else .01,combo_horizon=240 if h=='H12' else 320,tuning=dict(losses=losses,seeds=sorted(rows['0']),selected=dict(E=e,W=w,H=h),selection='fewest losses; ties lower weight/shorter horizon; no reporting outcome access'))
a.out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
