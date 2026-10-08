"""Independent complete-barrier aggregation and paired-bootstrap recomputation."""
from pathlib import Path
from collections import Counter
import hashlib,json,socket
import numpy as np
HERE=Path(__file__).resolve().parent
assert socket.gethostname().split('.')[0]=='127x01'
manifest=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
status=HERE/'collected-status'
for host in ('127x04','127x08'):assert (status/f'supervisor-{host}.exit').read_text().strip()=='0'
for i in range(152):
 assert (status/f'worker-{i}.exit').read_text().strip()=='0'
 d=json.loads((status/f'worker-{i}-done.json').read_text());assert d['complete'] and d['manifest']==manifest
cells=['T3-N97','ELT-N97','Full-N97','R-derived','T3-N90','Full-N90']
schedule=json.loads((HERE/'schedule.json').read_text())['pairs']
paths=sorted((HERE/'confirmation').glob('*.json'));assert len(paths)==1536
aggregate=hashlib.sha256();counts=Counter();cpu=Counter();bounds=[];values=np.full((128,6,2),np.nan)
for i,p in enumerate(paths):
 r=json.loads(p.read_text());pair=i//12;cell=(i%12)//2;seat=i%2;ep=schedule[pair]
 assert r['job']==i and r['terminal'] and r['manifest']==manifest
 for k,v in [('pair',pair),('variant',cells[cell]),('seat',seat),('seed',ep['seed']),('noise_seed',ep['noise_seed']),('family',ep['family']),('style',ep['style']),('mode','scripts')]:assert r[k]==v,(i,k)
 assert r['host']['nice']>=10 and r['host']['native_threads']==1
 assert r['host']['hostname'].split('.')[0]==('127x04' if i%152%2==0 else '127x08')
 want=.5 if r['winner'] is None else float(r['winner']==seat);assert r['score']==want
 values[pair,cell,seat]=want;counts[r['variant']]+=1;cpu[r['host']['hostname']]+=r['cpu_seconds'];bounds.append((r['started'],r['started']+r['elapsed']))
 aggregate.update(p.name.encode()+hashlib.sha256(p.read_bytes()).digest())
assert set(counts.values())=={256} and not np.isnan(values).any()
result=json.loads((HERE/'result.json').read_text());assert result['manifest']==manifest and aggregate.hexdigest()==result['receipt_aggregate']
means=values.mean(axis=2);indices=np.random.default_rng(9771100003).integers(0,128,(10000,128))
for j,c in enumerate(cells):
 assert means[:,j].mean()==result['scores'][c]['point']
 np.testing.assert_array_equal(np.quantile(means[indices,j].mean(axis=1),[.025,.975]),result['scores'][c]['ci95'])
for name,a,b in [('primary',0,2),('secondary_elt',0,1),('secondary_n90',4,5),('ceiling_gap',3,0)]:
 delta=means[:,a]-means[:,b];got=result['contrasts'][name]
 assert delta.mean()==got['point'];np.testing.assert_array_equal(np.quantile(delta[indices].mean(axis=1),[.025,.975]),got['ci95'])
 if name!='ceiling_gap':assert got['pass']==(got['ci95'][0]>0)
out=dict(games=len(paths),counts=counts,manifest=manifest,receipt_aggregate=aggregate.hexdigest(),independent_scores_and_all_bootstrap_intervals_match=True,all_nice_at_least_10=True,all_native_threads_one=True,game_cpu_hours_by_host={h:v/3600 for h,v in cpu.items()},wall_span_minutes=(max(b for a,b in bounds)-min(a for a,b in bounds))/60)
(HERE/'completion-audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
