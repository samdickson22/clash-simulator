"""r3 paired stratified bootstrap. Outcomes inaccessible without coordinator release."""
import argparse,itertools,json
from fractions import Fraction
from collections import Counter
from pathlib import Path
import numpy as np
from common import plan,read,write,sha,utc,ROOT
from schedule import ARMS,COUNTS,CELLS
from barrier import outcome_release


BONFERRONI=Fraction(59,60)

def stratified_counts(matrix,cells,reps,rng):
 assert np.all(matrix==np.asarray(matrix,dtype=np.int64))
 matrix=np.asarray(matrix,dtype=np.int64);out=np.zeros((reps,matrix.shape[1]),np.int64)
 for c in sorted(set(cells)):
  indices=np.flatnonzero(np.asarray(cells)==c);draw=rng.integers(0,len(indices),size=(reps,len(indices)))
  out+=matrix[indices[draw]].sum(axis=1)
 return out

def stratified_bootstrap(matrix,cells,reps,rng):
 return stratified_counts(matrix,cells,reps,rng)/len(matrix)

def interval(x,confidence):
 tail=100*(1-float(confidence))/2
 return [float(v) for v in np.percentile(x,[tail,100-tail])]

def exact_interval(counts,confidence,n):
 # Linear percentiles, with the index and interpolation weight computed rationally.
 ordered=np.sort(np.asarray(counts,dtype=np.int64));tail=(1-confidence)/2
 def bound(q):
  position=(len(ordered)-1)*q;i=position.numerator//position.denominator
  weight=position-i;j=min(i+1,len(ordered)-1)
  value=Fraction(int(ordered[i]))+weight*int(ordered[j]-ordered[i])
  return value*100/n
 return [bound(tail),bound(1-tail)]

def pack_exact(bounds):return [[v.numerator,v.denominator] for v in bounds]
def upper(record,key):
 # Published decimal values are display only. The rational result governs every gate.
 return Fraction(*record['exact'][key][1])

def population_stats(rows,rng,reps):
 matrix=np.array([[row['loss'][a] for a in ARMS] for row in rows],dtype=np.int64)
 assert all(row['loss'][a] in (0,1) for row in rows for a in ARMS)
 n=len(rows);boot=stratified_counts(matrix,[r['cell'] for r in rows],reps,rng)
 counts=matrix.sum(0);stats={};contrasts={}
 def bounds(record,values,keys):
  record['exact']={}
  for key,level in keys:
   exact=exact_interval(values,level,n);record[key]=[float(v) for v in exact];record['exact'][key]=pack_exact(exact)
  return record
 for j,a in enumerate(ARMS):
  stats[a]=bounds(dict(losses=int(counts[j]),draws=sum(r['draw'][a] for r in rows),wins=sum(r['win'][a] for r in rows),loss_pct=float(Fraction(100*int(counts[j]),n))),boot[:,j],[('ci95_pct',Fraction(19,20)),('ci9833_pct',BONFERRONI)])
 for l,r in itertools.permutations(range(8),2):
  contrasts[ARMS[l]+' minus '+ARMS[r]]=bounds(dict(point_count_diff=int(counts[l]-counts[r]),mean_pp=float(Fraction(100*int(counts[l]-counts[r]),n))),boot[:,l]-boot[:,r],[('ci95_pp',Fraction(19,20)),('ci975_pp',Fraction(39,40)),('ci9833_pp',BONFERRONI)])
 return dict(n=n,stratum_counts=dict(Counter(r['cell'] for r in rows)),arms=stats,contrasts=contrasts)


def select(stats,mac,validity_approved=False):
 primary,guard=stats['primary'],stats['guard'];control_bad=not 36*primary['n']<=100*primary['arms']['K0c-200']['losses']<=54*primary['n']
 if control_bad and not validity_approved:return dict(status='SUSPENDED',reason='K0c@1.0 outside [36%,54%]; independent receipts-only review required before selection')
 feas=mac['feasibility'];speed=mac['speed'];dead=mac['deadline_equivalence']
 c=dead['K0c']['cell'];control_gates=feas['K0c']['gates'];c=c if all(control_gates[k] is True for k in ('1_speed','2_perception','3_exactness')) else None
 assert c in (None,1.,.8)
 control='K0c-'+str(200 if c is None or c==1. else 160);admissible=[];gates={}
 for tier in ('S','K2','K4'):
  f=feas[tier];cell=f['cell'];arm=tier+'-'+str(200 if cell==1. else 160)
  v1=upper(primary['contrasts'][arm+' minus '+control],'ci9833_pp')<=-10
  v2=upper(primary['arms'][arm],'ci9833_pct')<=40
  g1=upper(guard['contrasts'][arm+' minus '+control],'ci95_pp')<0
  gates[tier]=dict(Mac=f['feasible'],V1=v1,V2=v2,G1=g1,cell=cell,arm=arm)
  if f['feasible'] and v1 and v2 and g1:admissible.append(tier)
 checks={};chosen='F0'
 for tier in admissible:
  left=gates[tier]['arm'];checks[tier]={}
  for other in admissible[admissible.index(tier)+1:]:
   right=gates[other]['arm'];checks[tier][other]=dict(NI=upper(primary['contrasts'][left+' minus '+right],'ci975_pp')<=5,G2=upper(guard['contrasts'][left+' minus '+right],'ci95_pp')<=10)
  if all(v['NI'] and v['G2'] for v in checks[tier].values()):chosen=tier;break
 return dict(status='PROVISIONAL (emulator-off)',selected=chosen,control=control,control_full_speed_fallback=c is None,admissible=admissible,gates=gates,candidate_checks=checks,live_deadline_ms=200,program_kill=not admissible and all(mac['speed'][t]['r']>=1. and dead[t]['cell']==1. for t in ('S','K2','K4')))

def load_blocks(root,ledger):
 excluded={r['lost']['id'] for r in ledger};by_pop={p:{} for p in ('primary','guard','descriptive')};source={}
 replacements={r['replacement']['id']:r['replacement'] for r in ledger if r['replacement'] is not None}
 for f in sorted(root.glob('*/complete.json')):
  proof=read(f);d=proof['descriptor'];pop=d['population'];identity=d['id']
  if pop not in by_pop or identity in excluded:continue
  if proof['host']!='127x01':assert (f.parent/'hub-ack.json').exists(),'completed block not durable on hub'
  logical=d.get('replaces') or identity
  if d.get('replaces'):assert identity in replacements and d['cell']==replacements[identity]['cell'] and d['replaces']==replacements[identity]['replaces']
  index=int(logical.rsplit('-',1)[1]);assert 0<=index<COUNTS[pop] and d['cell']==index%CELLS[pop]
  assert logical not in by_pop[pop],'duplicate logical block'
  assert len(proof['games'])==8
  row=dict(id=logical,seed=d['seed'],cell=d['cell'],complete_sha256=sha(f),interference=proof.get('interference',{}),source_host=proof['host'],loss={},draw={},win={},timing={});decks=[]
  for name,h in proof['games'].items():
   p=f.parent/'games'/name;assert sha(p)==h;source[str(p)]=h
   r=read(p);m=r['metadata'];a=r['cohort'];assert m['terminal'] and m['seed']==d['seed'] and m['cell']==d['cell'] and m['seat']==d['seat']
   assert r['loss'] in (0,1);row['loss'][a]=int(r['loss']);assert row['loss'][a]==int(m['winner'] is not None and m['winner']!=m['seat'])
   row['draw'][a]=m['winner'] is None;row['win'][a]=m['winner']==m['seat'];decks.append((m['own_deck'],m['opponent_deck'],m['seat']))
   row['timing'][a]=r['search_ab']
  assert set(row['loss'])==set(ARMS) and all(d==decks[0] for d in decks)
  by_pop[pop][logical]=row
 assert len(by_pop['primary'])==2400 and len(by_pop['guard'])==600
 return {p:[v for k,v in sorted(rows.items())] for p,rows in by_pop.items()},source

def timing_stats(rows,rng,reps):
 out={};cells=[r['cell'] for r in rows]
 for arm in ARMS:
  ds=[r['timing'][arm]['deadline_stats'] for r in rows];den=np.array([len(d) for d in ds]);assert den.sum()>0
  mat=np.array([[sum(d['hit'] for d in g),sum(d['fallback'] for d in g),sum(d['wall_overrun'] for d in g),len(g)] for g in ds],float)
  boot=stratified_bootstrap(mat,cells,reps,rng);rates=boot[:,:3]/boot[:,3,None]
  walls=np.array([d['wall_seconds'] for g in ds for d in g]);over=np.array([d['overrun_seconds'] for g in ds for d in g if d['wall_overrun']]);gc=[x for r in rows for x in r['timing'][arm]['gc_maintenance']]
  out[arm]=dict(decisions=int(den.sum()),cutoff_pct=float(100*mat[:,0].sum()/den.sum()),fallback_pct=float(100*mat[:,1].sum()/den.sum()),overrun_pct=float(100*mat[:,2].sum()/den.sum()),rate_ci95_pct={k:interval(100*rates[:,i],.95) for i,k in enumerate(('cutoff','fallback','overrun'))},wall_ms=dict(zip(('p50','p95','p99','max'),map(float,np.percentile(1000*walls,[50,95,99,100])))),positive_overrun_ms=None if not len(over) else dict(zip(('p50','p95','p99','max'),map(float,np.percentile(1000*over,[50,95,99,100])))),overrun_ticks=dict(Counter(str(d['delayed_ticks']) for g in ds for d in g)),gc_count=len(gc),gc_seconds=sum(x['seconds'] for x in gc),gc_during_decision=sum(x['during_decision'] for x in gc))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--release',type=Path,required=True);p.add_argument('--mac-summary',type=Path);p.add_argument('--ledger',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 # Must happen before touching the block directory or any raw game file.
 release=outcome_release(ROOT,a.release)
 if a.mac_summary:assert release.get('mac_summary_sha256')==sha(a.mac_summary),'Mac selection requires authorized committed bytes'
 ledger=read(a.ledger)['events'] if a.ledger else []
 rows,source=load_blocks(a.root,ledger);cfg=plan();rng=np.random.default_rng(cfg['bootstrap']['seed']);stats={p:population_stats(r,rng,cfg['bootstrap']['reps']) for p,r in rows.items() if r}
 if a.mac_summary:
  assert release.get('mac_summary_sha256')==sha(a.mac_summary),'Mac selection requires authorized committed bytes'
  mac=read(a.mac_summary);assert not mac.get('dry_run',True),'Linux dry-run cannot select a tier'
 selection=select(stats,mac) if a.mac_summary else dict(status='DESCRIPTIVE_ONLY',reason='coordinator released without a committed Mac measurement')
 result=dict(utc=utc(),sealed=False,release=release,bootstrap=cfg['bootstrap'],populations=stats,selection=selection,replacements=ledger,file_shas=source,plan_sha256=sha(Path(__file__).parent/'plan.json'))
 result['disclosure']=dict(interfered_blocks={p:sum(bool(v['interference'].get('interfered')) for v in r) for p,r in rows.items()},idle_service_rule=cfg['compute']['idle_service_exception'],perception_io_rule=cfg['compute']['perception_io_exception'])
 result['timing']={p:timing_stats(r,rng,cfg['bootstrap']['reps']) for p,r in rows.items() if r}
 from ssh_sensitivity import health_ledger,analyze
 sensitivity_ledger=health_ledger(a.root,ledger,sha(a.ledger) if a.ledger else None)
 ledger_path=a.out.with_name(a.out.name+'.ssh-sensitivity-ledger.json');write(ledger_path,sensitivity_ledger)
 result['ssh_sensitivity']=analyze(rows,sensitivity_ledger,cfg['bootstrap']['reps'],cfg['bootstrap']['seed'],population_stats,np.random.default_rng)
 result['ssh_sensitivity']['ledger_sha256']=sha(ledger_path)
 result['disclosure']['ssh_flagged_blocks']={p:v['excluded'] for p,v in result['ssh_sensitivity']['populations'].items()}
 write(a.out,result);print(json.dumps(dict(utc=result['utc'],completed=True,selection=selection)))
if __name__=='__main__':main()
