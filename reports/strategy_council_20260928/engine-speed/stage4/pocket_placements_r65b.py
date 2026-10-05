"""Complete real pocket placement checks with the corrected live exporter."""
import hashlib,json,pickle
from pathlib import Path
import cloudpickle
from c56_gate import PLAN,FOLDER,CARDS,config,resources,pocket_root,placements_at,fingerprint

source=FOLDER/'c56_games_r65.json';output=FOLDER/'c56_pockets_r65b.json'
bridge_path=FOLDER/'area_adapter_requalification.json';bridge=json.loads(bridge_path.read_text())
identity=fingerprint();assert identity==bridge['new_fingerprint']
source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
assert source_sha==bridge['frozen_receipts']['reports/strategy_council_20260928/engine-speed/stage4/c56_games_r65.json']
games=json.loads(source.read_text())['results'];assert len(games)==64 and all(r['ok'] and r['terminal'] for r in games.values())
plan_sha=hashlib.sha256(PLAN.read_bytes()).hexdigest();episodes=json.loads(PLAN.read_text())['episodes'];driver_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
out=dict(mode='real_pockets',fingerprint=identity,plan_sha256=plan_sha,source_games_sha256=source_sha,adapter_requalification_sha256=hashlib.sha256(bridge_path.read_bytes()).hexdigest(),driver_sha256=driver_sha,results={})
if output.exists():
 old=json.loads(output.read_text());assert all(old.get(k)==out[k] for k in out if k!='results');out=old
res=resources();cfg=config(CARDS)
for seat in (0,1):
 if out['results'].get(str(seat),{}).get('ok'):continue
 b,index=pocket_root(seat,episodes,games,res[0],cfg,res)
 tick=b.tick;crowns=b.get_crown_count(seat)
 result,b,native=placements_at(b,cfg,res,seat,pocket=True)
 result.update(source_case=index,root_tick=tick,root_crowns=crowns)
 assert crowns>0 and fingerprint()==identity
 if not result['ok']:
  path=output.with_name(output.stem+f'.seat{seat}.pkl');path.write_bytes(cloudpickle.dumps(b,protocol=pickle.HIGHEST_PROTOCOL));result['root_pickle']=str(path);result['native']=json.loads(native.snapshot())
 else:assert any(p['accepted'] and p['pocket'] for p in result['placements'])
 out['results'][str(seat)]=result
 tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(output)
 print(seat,{'ok':result['ok'],'source_case':index,'root_tick':tick,'accepted':sum(p['accepted'] for p in result.get('placements',[])),'failure':{k:v for k,v in result.items() if k not in ('placements','python','rust','native')} if not result['ok'] else None},flush=True)
 if not result['ok']:raise SystemExit(1)
print('PASS real pocket placements both seats',flush=True)
