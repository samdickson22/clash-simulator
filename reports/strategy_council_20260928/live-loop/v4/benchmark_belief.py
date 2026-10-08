"""Fleet-only attribution of final fast belief tail, public train logs only."""
import gc,gzip,json,sys,time
from pathlib import Path
from clasher.live.belief import Belief
from clasher.live.contracts import Frame,Observation
from clasher.live.runtime import quantiles
from clasher.rl.live_inference_contract import parse_public_vision_frame,LIVE_VISION_SCHEMA_VERSION
path=Path(sys.argv[1]);config=json.loads(path.with_name('config.json').read_text())
assert config['source']['split']=='train'
b=Belief(config['belief'])
parts={};gc_start=0

def callback(phase,info):
    global gc_start
    if phase=='start':gc_start=time.perf_counter_ns()
    else:parts['gc']=parts.get('gc',0)+(time.perf_counter_ns()-gc_start)/1e6

gc.callbacks.append(callback)
for key in ('_transition','_resource_event','_hands_event','distribution','sample'):
    original=getattr(b.tracker,key)
    def measured(*args,_original=original,_key=key,**kw):
        start=time.perf_counter_ns();result=_original(*args,**kw)
        parts[_key]=parts.get(_key,0)+(time.perf_counter_ns()-start)/1e6
        return result
    setattr(b.tracker,key,measured)
rows=[]
with gzip.open(path,'rt') as stream:
    for line in stream:
        row=json.loads(line)
        if row['metric']!='processed':continue
        raw=dict(row['public']);outer={k:raw.pop(k) for k in ('episode_id','frame_id','timestamp_ms')}
        public=parse_public_vision_frame(dict(outer,schema_version=LIVE_VISION_SCHEMA_VERSION,public=raw))
        frame=Frame(public.episode_id,row['sequence'],row['produced_at'],row['produced_at'],row['timestamp_ms'],None)
        obs=Observation(frame,public,tuple(row['event_candidates']),row['phase'],0.)
        parts={};start=time.perf_counter_ns();b.update(obs);elapsed=(time.perf_counter_ns()-start)/1e6
        rows.append(dict(sequence=row['sequence'],total=elapsed,**parts))
print(json.dumps(dict(timing=quantiles([r['total'] for r in rows]),
                     parts={k:quantiles([r.get(k,0) for r in rows]) for k in ('gc','_transition','_resource_event','_hands_event','distribution','sample')},
                     slowest=sorted(rows,key=lambda r:-r['total'])[:30]),indent=2))
