"""Validate imports from completed game receipts while later games run."""
import hashlib,json,pickle,time
from pathlib import Path
import cloudpickle
from c56_gate import PLAN,FOLDER,CARDS,config,resources,run_imports,fingerprint

source=FOLDER/'c56_games_r65.json';output=FOLDER/'c56_imports_r65b.json'
bridge_path=FOLDER/'area_adapter_requalification.json'
bridge=json.loads(bridge_path.read_text());bridge_sha=hashlib.sha256(bridge_path.read_bytes()).hexdigest()
identity=fingerprint();assert identity==bridge['new_fingerprint']
assert hashlib.sha256(source.read_bytes()).hexdigest()==bridge['frozen_receipts']['reports/strategy_council_20260928/engine-speed/stage4/c56_games_r65.json']
plan_sha=hashlib.sha256(PLAN.read_bytes()).hexdigest()
driver_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();episodes=json.loads(PLAN.read_text())['episodes']
out=dict(mode='imports',fingerprint=identity,plan_sha256=plan_sha,stream_driver_sha256=driver_sha,adapter_requalification_sha256=bridge_sha,source_game_fingerprint=bridge['old_fingerprint'],results={})
if output.exists():
 old=json.loads(output.read_text());assert all(old.get(k)==out[k] for k in ('mode','fingerprint','plan_sha256','stream_driver_sha256'));out=old
res=resources();cfg=config(CARDS)
for index,ep in enumerate(episodes):
 if out['results'].get(str(index),{}).get('ok'):continue
 while True:
  data=json.loads(source.read_text())
  assert data['fingerprint']==bridge['old_fingerprint'] and data['plan_sha256']==plan_sha
  if str(index) in data['results']:
   record=data['results'][str(index)];assert record['ok'] and record['terminal'];break
  done=FOLDER/'c56_qualification_r65.exit'
  assert not done.exists(), f'producer stopped before case {index}'
  print('waiting for game',index,flush=True);time.sleep(10)
 result,b,native=run_imports(ep,record,cfg,res)
 result['game_record_sha256']=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
 assert fingerprint()==identity and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==driver_sha
 if not result['ok']:
  path=output.with_name(output.stem+f'.case{index}.tick{b.tick}.pkl');path.write_bytes(cloudpickle.dumps(b,protocol=pickle.HIGHEST_PROTOCOL));result['root_pickle']=str(path)
  if native is not None:result['native']=json.loads(native.snapshot())
 out['results'][str(index)]=result
 tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(output)
 print(index,{'ok':result['ok'],'roots':len(result.get('roots',[])),'max_clone_us':max((r['clone_us'] for r in result.get('roots',[])),default=0),'failure':{k:v for k,v in result.items() if k not in ('roots','python','rust','native')} if not result['ok'] else None},flush=True)
 if not result['ok']:raise SystemExit(1)
assert sum(len(r['roots']) for r in out['results'].values())>=1000
print('PASS live imports',sum(len(r['roots']) for r in out['results'].values()),flush=True)
