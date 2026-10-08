"""Score exact public derivation at the pre-action trace boundary (< tick)."""
import bootstrap
from bootstrap import HERE
import copy,gzip,json,socket,time
from derived_public_state import DerivedPublicState,PublicEvent
from evaluate import write
host=socket.gethostname().split('.')[0];assert host in ('127x04','127x08')
prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());folder=HERE/'dev-exact-control';folder.mkdir(exist_ok=True)
initial=None
for index in range(56):
 if index%2!=(host=='127x08'):continue
 cpu=time.process_time()
 with gzip.open(HERE/f'dev-traces/{index:03d}.json.gz','rt') as f:data=json.load(f)
 if initial is None:initial=DerivedPublicState(prior,data['costs'])
 states={s:copy.copy(initial) for s in (0,1)}
 for b in states.values():b.events=[]
 hist={s:[] for s in (0,1)};positions={s:0 for s in (0,1)};samples={}
 for row in data['rows']:
  if row['tick']%20!=10:continue
  seat=row['seat'];tick=row['tick'];key=f'{seat}-{tick}'
  if key in samples:continue
  source=data['public'][1-seat]
  while positions[seat]<len(source) and source[positions[seat]]['tick']<tick:
   e=source[positions[seat]];hist[seat].append(PublicEvent(e['tick'],e['kind'],e['name'],e['amount']));positions[seat]+=1
  b=states[seat];b.update(tick,hist[seat]);h=b.derived()['hand'];correct=h is not None and sorted(h,key=lambda x:x or '')==sorted(row['truth_hand'],key=lambda x:x or '')
  assert abs(b.elixir-row['truth_elixir'])<1e-8,(index,seat,tick,b.elixir,row['truth_elixir'])
  assert h is None or correct,(index,seat,tick,h,row['truth_hand'])
  samples[key]=dict(mass=float(h is not None),correct=correct,mae=abs(b.elixir-row['truth_elixir']),covered=True,width=0.)
 write(folder/f'{index:03d}.json',dict(index=index,boundary='public event tick < pre-action observation tick',samples=samples,cpu_seconds=time.process_time()-cpu))
 print(json.dumps(dict(index=index,exact_samples=len(samples),errors=0)),flush=True)
