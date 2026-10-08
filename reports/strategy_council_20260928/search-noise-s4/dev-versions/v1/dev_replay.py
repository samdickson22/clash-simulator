"""Matched public-trace development replay; all truth is scoring-only."""
import bootstrap
from bootstrap import HERE
import copy,gzip,json,time
from types import SimpleNamespace
from collections import Counter
from tracker_v3 import TrackerV3
from tracker_v2 import TrackerV2
from elt import ELT,Candidate
from derived_public_state import DerivedPublicState,PublicEvent
from evaluate import write
LEVELS={'T2-N97':(.97,.97),'T2-N90':(.90,.90),'T2-N64':(180/280,180/270)}
def hand_summary(b):
 d=b.distribution()
 if isinstance(b,ELT):
  masses=Counter()
  for state,w in zip(b.projected(),b.weights):
   h=state.derived()['hand']
   if h is not None:masses[tuple(h)]+=float(w)
  h,m=max(masses.items(),key=lambda x:x[1],default=(None,0.));return d,h,m
 if isinstance(b,TrackerV3):return d,d['best_hand'],d['hand90_mass']
 masses=Counter()
 for state,w in b._hands:
  x=b._clone_hand(state);x.advance(b.tick);known=sorted(x.revealed-set(x.queue))
  if len(known)==8-len(x.queue):masses[tuple(known+[None]*(4-len(known)))]+=w
 h,m=max(masses.items(),key=lambda x:x[1],default=(None,0.));return d,h,m

def run(index,round_name):
 cpu=time.process_time()
 with gzip.open(HERE/f'dev-traces/{index:03d}.json.gz','rt') as f:data=json.load(f)
 prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());selection=json.loads((HERE/'runtime/support/selection.json').read_text())
 radii=json.loads((HERE/'calibration.json').read_text())
 body_cards={int(k):tuple(tuple(x) for x in v) for k,v in data['body_cards'].items()}
 initial=DerivedPublicState(prior,data['costs']);beliefs={};samples={};last={};exact={};hist={};position={}
 for seat in (0,1):
  exact[seat]=copy.copy(initial);exact[seat].events=[];hist[seat]=[];position[seat]=0
  for level,(q,p) in LEVELS.items():
   key=(seat,level);beliefs[key]={name:cls(prior,data['costs'],recall=q,precision=p,body_cards=body_cards,calibration=radii[level]) for name,cls in [('T3',TrackerV3),('T2',TrackerV2)]}
   beliefs[key]['ELT']=ELT(prior,data['costs'],initial=copy.copy(initial),missed_rate=selection['missed_rate']);samples[key]=[];last[key]=0
 for row in data['rows']:
  seat=row['seat'];key=(seat,row['variant']);events=[SimpleNamespace(**e) for e in row['events']]
  source=data['public'][1-seat]
  while position[seat]<len(source) and source[position[seat]]['tick']<=row['tick']:
   e=source[position[seat]];hist[seat].append(PublicEvent(e['tick'],e['kind'],e['name'],e['amount']));position[seat]+=1
  exact[seat].update(row['tick'],hist[seat])
  for name,b in beliefs[key].items():
   if name!='ELT':b.update_public(row['tick'],events,row['bodies'])
   else:
    precision=LEVELS[key[1]][1]
    for e in events:
     estimate=max(last[key],e.tick-2,0);q=selection['event_probabilities'].get(e.name,.5);odds=(precision/(1-precision))/2.;q=q*odds/(1-q+q*odds)
     b.observe(Candidate(estimate,((e.name,1.),),q,kind=e.kind,amount=e.amount));last[key]=estimate
    b.advance(row['tick'])
  if row['tick']%20!=10:continue
  truth=sorted(row['truth_hand'],key=lambda x:x or '');out={}
  for name,b in beliefs[key].items():
   d,h,m=hand_summary(b);lo,hi=d['elixir_interval_90']
   out[name]=dict(mass=m,correct=h is not None and sorted(h,key=lambda x:x or '')==truth,mae=abs(d['elixir_mean']-row['truth_elixir']),covered=lo<=row['truth_elixir']<=hi,width=hi-lo)
  h=exact[seat].derived()['hand'];out['R-derived']=dict(mass=float(h is not None),correct=h is not None and sorted(h,key=lambda x:x or '')==truth,mae=abs(exact[seat].elixir-row['truth_elixir']),covered=abs(exact[seat].elixir-row['truth_elixir'])<1e-8,width=0.)
  samples[key].append(dict(tick=row['tick'],metrics=out))
 out=HERE/f'dev-{round_name}';out.mkdir(exist_ok=True)
 write(out/f'{index:03d}.json',dict(index=index,cpu_seconds=time.process_time()-cpu,samples={f'{s}-{v}':x for (s,v),x in samples.items()}))
 print(json.dumps(dict(index=index,complete=True,cpu_seconds=time.process_time()-cpu)),flush=True)
