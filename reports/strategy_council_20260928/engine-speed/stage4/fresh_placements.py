"""Run the gate's independent fresh-placement cases before full games finish."""
import hashlib,json,pickle
from pathlib import Path
import cloudpickle
from c56_gate import PLAN,FOLDER,CARDS,battle,config,resources,placements_at,fingerprint

output=FOLDER/'c56_placements_r65.json'
identity=fingerprint();plan_sha=hashlib.sha256(PLAN.read_bytes()).hexdigest()
driver_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
out=dict(mode='placements',fingerprint=identity,plan_sha256=plan_sha,fresh_driver_sha256=driver_sha,results={})
if output.exists():
 old=json.loads(output.read_text())
 assert all(old.get(k)==out[k] for k in ('mode','fingerprint','plan_sha256','fresh_driver_sha256'))
 out=old
res=resources();cfg=config(CARDS)
for index in range(14):
 if out['results'].get(str(index),{}).get('ok'):continue
 deck=list(CARDS[index*4:index*4+4])+list(CARDS[((index+1)%14)*4:((index+1)%14)*4+4])
 b=battle(dict(seed=630056+index,decks=[deck,deck]),res[0].loader)
 for player in b.players:player.elixir=10
 result=dict(ok=True,placements=[])
 for seat in (0,1):
  r,p,n=placements_at(b,cfg,res,seat)
  if not r['ok']:
   result=r
   path=output.with_name(f'fresh-placement-{index}-{seat}.pkl')
   path.write_bytes(cloudpickle.dumps(p,protocol=pickle.HIGHEST_PROTOCOL));result['root_pickle']=str(path)
   result['native']=json.loads(n.snapshot());break
  result['placements']+=r['placements']
 assert fingerprint()==identity and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==driver_sha
 out['results'][str(index)]=result
 tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(output)
 print(index,{'ok':result['ok'],'accepted':sum(p['accepted'] for p in result.get('placements',[])),'failure':{k:v for k,v in result.items() if k not in ('placements','python','rust','native')} if not result['ok'] else None},flush=True)
 if not result['ok']:raise SystemExit(1)
print('PASS fresh placement cases',len(out['results']),flush=True)
