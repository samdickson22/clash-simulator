"""Research public-field projection timing, not an admitted public adapter."""
import gzip,json,time
from study import OUT,PORT,config_for,request,schedule,PersistentProbeSession
row=json.loads(next(gzip.open(OUT/'sample50.jsonl.gz','rt')))
with (OUT/'public-benchmark.jsonl').open('w') as log:
 for cadence in [20,5]:
  t=time.perf_counter();request(PORT,'configure '+json.dumps(config_for(row['payload']),separators=(',',':')))
  with PersistentProbeSession(PORT) as call,gzip.open(OUT/f'public-{cadence}.jsonl.gz','wt') as output:
   seq,rej=schedule(call,row['payload']);print('started',cadence,flush=True);n=0;observe_s=step_s=project_s=0;tick=0
   while tick<7200:
    ts=time.perf_counter();s=call(f'step {cadence}');step_s+=time.perf_counter()-ts
    ts=time.perf_counter();a=call('observe-atomic');observe_s+=time.perf_counter()-ts
    ts=time.perf_counter();basic=a['ordinary'];rich=a['rich'];tick=a['tick'];n+=1
    perspectives=[]
    for owner in [0,1]:
     entities=[]
     for o in rich['objects']:
      if o['owner']!=owner and (o.get('invisibleCount') is None or o['invisibleCount']>0):continue
      entities.append({k:o[k] for k in ['nativeObjectId','owner','cardId','dataGlobalId','x','y','hp','maxHp','shield']})
     own=next(v for v in basic['players'] if v['owner']==owner)
     perspectives.append({'owner':owner,'hand':[{k:v[k] for k in ['handIndex','cardId','commandCardId','cost']} for v in own['hand']],'elixir':own['elixir'],'nextCard':own['nextCard'],'entities':entities})
    output.write(json.dumps({'tick':tick,'perspectives':perspectives},separators=(',',':'))+'\n');project_s+=time.perf_counter()-ts
    if n%100==0:print('progress',cadence,tick,flush=True)
    if s.get('ended') or basic['ended']:break
   r={'index':row['index'],'cadence':cadence,'total_s':time.perf_counter()-t,'observations':n,'last_tick':tick,'observe_s':observe_s,'step_s':step_s,'project_s':project_s,'ended':basic['ended'],'note':'own HUD plus rich entity fields; enemy invisible or visibility-unknown bodies omitted, owner-relative visibility unvalidated, public play-history extraction and variable body levels not implemented'}
  r['gzip_bytes']=(OUT/f'public-{cadence}.jsonl.gz').stat().st_size;log.write(json.dumps(r)+'\n');log.flush();print(r,flush=True)
