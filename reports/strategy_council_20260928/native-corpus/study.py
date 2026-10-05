"""Bounded independent corpus reconstruction experiment; no training outputs."""
import collections,copy,gzip,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts'),str(ROOT/'reports/strategy_council_20260928/m0/human-prior-scan')]
from card_map import SLUG_TO_GAMEDATA,base_slug
from clasher.data import CardDataLoader
from clasher.rl.native_probe_transport import PersistentProbeSession
from smoke_reference_battle import request
PORT=26791
SOURCE=ROOT/'artifacts/worktree-data/clasher-event-policy/reports/external_reel_DdMGvYLsyL_20260913/sample-part-000000.parquet'
TEMPLATE=ROOT/'artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0/plan.json'
loader=CardDataLoader(ROOT/'gamedata.json')
IDS={s:loader.get_card(n)._raw_entry['id'] for s,n in SLUG_TO_GAMEDATA.items()}
IDS['spirit-empress']=28000025
TOWERS={'tower-princess':159000000,'cannoneer':159000001,'dagger-duchess':159000002,'royal-chef':159000004}

def dump(name,value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def features(p):
 decks=[c['card_key'] for side in ['team','opponent'] for c in p['battle'][side]['players'][0]['deck']]
 towers=[p['battle'][s]['players'][0].get('tower_card',{}).get('card_key') for s in ['team','opponent']]
 return set(decks+towers)
def prepare():
 import pyarrow.parquet as pq
 rows=pq.read_table(SOURCE,columns=['replay_tag','payload_json']).to_pylist()
 pool=[]; allkeys=collections.Counter(); kinds=collections.Counter(); forms=collections.Counter(); top=collections.Counter(); dates=[]
 for i,r in enumerate(rows):
  p=json.loads(r['payload_json']);top.update(p.keys())
  if any(len(p['battle'][s]['players'])!=1 for s in ['team','opponent']):continue
  pool.append({'index':i,'tag':r['replay_tag'],'payload':p})
  allkeys.update(features(p)); kinds.update(e['kind'] for e in p['events']);forms.update(str(e.get('form_at_play')) for e in p['events'])
 # Twenty uniformly spaced examples plus thirty greedy coverage additions.
 selected=[pool[round(i*(len(pool)-1)/19)] for i in range(20)]
 seen=set().union(*(features(r['payload']) for r in selected)); used={r['index'] for r in selected}
 for _ in range(30):
  r=max((r for r in pool if r['index'] not in used),key=lambda r:(len(features(r['payload'])-seen),-r['index']))
  selected.append(r);used.add(r['index']);seen|=features(r['payload'])
 with gzip.open(OUT/'sample50.jsonl.gz','wt') as f:
  for r in selected:f.write(json.dumps(r,separators=(',',':'))+'\n')
 dump('sample-inventory.json',{'source':str(SOURCE),'sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'rows':len(rows),'eligible_1v1':len(pool),'sampling':'20 uniformly spaced row indices + 30 greedy new card/form/tower coverage, tie earliest index; not prevalence sample','sample_indices':[r['index'] for r in selected],'sample_features':sorted(seen),'source_features':dict(allkeys),'event_kinds':dict(kinds),'form_at_play':dict(forms),'top_keys':dict(top)})
 print('prepared',len(selected),'features',len(seen),flush=True)
def config_for(p):
 c=copy.deepcopy(json.load(open(TEMPLATE))['config']);b=c['battle'];c['rndSeed']=1;c['endTick']=7200
 # Explicit experimental assumptions: no recorded king level, shuffle seed,
 # active evo slots, or native per-card serializer values are in the payload.
 levels=[v['level'] for s in ['team','opponent'] for v in p['battle'][s]['players'][0]['deck']]
 level=collections.Counter(levels).most_common(1)[0][0];b['lvlcap']=level;b['cardlvlmin']=level
 for owner,side in enumerate(['team','opponent']):
  pl=p['battle'][side]['players'][0]
  b[f'deck{owner}']['sp']=[dict(d=IDS[base_slug(v['card_key'])[0]],el={'base':0,'evo':1,'hero':2}[base_slug(v['card_key'])[1]]) for v in pl['deck']]
  b[f'deck{owner}']['sc'][0]['d']=TOWERS[pl['tower_card']['card_key']]
  b['hbd'][owner]['kt']=pl['tower_card']['level'];b[f'avatar{owner}']['expLevel']=pl['tower_card']['level']
 return c

def schedule(call,p):
 seq=[];rejects=[]
 for e in p['events']:
  owner={'team':0,'opponent':1}[e['side']];tick=e['replay_tick_20hz']
  if e['kind']=='play_card':
   pos=e['coordinates']['native_world_units'];cmd=f"replay-schedule-card {owner} {IDS[base_slug(e['card_key'])[0]]} {pos['x']} {pos['y']} {tick}"
  elif e['kind']=='activate_ability':cmd=f'replay-schedule-ability {owner} - {tick}'
  else:rejects.append({'index':e['source_index'],'error':'unsupported event kind'});continue
  try:seq.append((e['source_index'],call(cmd)['sequence']))
  except ValueError as er:rejects.append({'index':e['source_index'],'error':str(er)})
 return seq,rejects

def towers(frame):return [{k:o[k] for k in ['nativeObjectId','owner','x','y','hp','maxHp']} for o in frame['objects'] if o['nativeObjectId'] in range(5000000,5000006)]
def run_one(row,cadence=20,rich=False,session=True,prefix='sample',save_frames=False,config_override=None):
 p=row['payload'];result={'index':row['index'],'tag':row['tag'],'cadence':cadence,'rich':rich,'session':session,'features':sorted(features(p))};t=time.perf_counter()
 config=config_for(p) if config_override is None else config_override
 try:result['configured']=request(PORT,'configure '+json.dumps(config,separators=(',',':')))
 except Exception as e:result['failure']=str(e);return result
 result['configure_s']=time.perf_counter()-t
 transport=PersistentProbeSession(PORT) if session else None
 if transport:transport.open()
 call=transport if session else lambda c:request(PORT,c)
 stream=gzip.open(OUT/f'{prefix}-{row["index"]}-frames.jsonl.gz','wt') if save_frames else None
 try:
  result['initial_observe']=call('observe')
  initial_rich=call('observe-rich');result['initial_rich_players']=initial_rich['players'];result['initial_rich_towers']=initial_rich['objects']
  seq,result['schedule_rejections']=schedule(call,p);result['scheduled']=len(seq)
  result['setup_s']=time.perf_counter()-t
  start=time.perf_counter(); n=0;bytes_seen=0;step_s=0;observe_s=0;seen_ids=set();kill_intervals=[];prev=None;tick=0
  recorded_tick=round(p['replay']['duration']['timeline_seconds']*20)
  target=7200;recorded_frame=None
  while tick<target:
   delta=min(cadence,target-tick)
   if tick<recorded_tick<tick+delta:delta=recorded_tick-tick
   ts=time.perf_counter();step=call(f'step {delta}');step_s+=time.perf_counter()-ts
   ts=time.perf_counter();f=call('observe-rich' if rich else 'observe');observe_s+=time.perf_counter()-ts
   tick=f['tick'];n+=1;raw=json.dumps(f,separators=(',',':'));bytes_seen+=len(raw)
   if stream:stream.write(raw+'\n')
   seen_ids.update((o.get('cardId'),o.get('dataGlobalId')) for o in f['objects'])
   current={v['nativeObjectId']:v['hp'] for v in towers(f)}
   if prev:
    kill_intervals += [{'tower':i,'after':prev[0],'by':tick} for i,hp in prev[1].items() if hp>0 and current.get(i,0)<=0]
   prev=tick,current
   if tick==recorded_tick:recorded_frame={'tick':tick,'towers':towers(f),'crownsRaw':f.get('crownsRaw')}
   if step.get('ended') or f.get('ended'):break
  result.update({'loop_s':time.perf_counter()-start,'observations':n,'response_bytes':bytes_seen,'step_s':step_s,'observe_s':observe_s,'last_tick':tick,'recorded_tick':recorded_tick,'at_recorded_end':recorded_frame,'native_tower_kill_intervals':kill_intervals,'observed_card_data_ids':sorted(seen_ids,key=str)})
  final=call('observe');result['final']={k:final[k] for k in ['tick','ended','finalized','winner','crownsRaw']};result['final']['towers']=towers(final)
  result['action_receipts']=[{'source_index':i,**call(f'replay-schedule-status {s}')} for i,s in seq]
  result['recorded']={s:{'crowns':p['battle'][s]['crowns'],'towers':p['battle'][s]['players'][0]['final_tower_hitpoints']} for s in ['team','opponent']}
  result['total_s']=time.perf_counter()-t
 except Exception as e:result['failure']=f'{type(e).__name__}: {e}'
 finally:
  if stream:stream.close()
  if transport:transport.close()
 return result

if __name__=='__main__':
 if sys.argv[1]=='prepare':prepare()
 elif sys.argv[1]=='run':
  rows=[json.loads(l) for l in gzip.open(OUT/'sample50.jsonl.gz','rt')]
  limit=int(sys.argv[2]) if len(sys.argv)>2 else 50
  with (OUT/f'results-terminal-{limit}.jsonl').open('w') as f:
   for row in rows[:limit]:
    r=run_one(row,save_frames=limit==1);f.write(json.dumps(r)+'\n');f.flush();print(row['index'],r.get('failure'),r.get('total_s'),r.get('final'),flush=True)
