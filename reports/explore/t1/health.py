"""Health-only projection; never compute or emit wins/losses/winner identities."""
import argparse,collections,json,math
from pathlib import Path
from common import read,write,sha,utc,plan

def health(root,validate=False):
 counts=collections.Counter();errors=[];timing=collections.Counter();seen=set()
 for p in sorted(Path(root).glob('*/complete.json')):
  r=read(p);d=r['descriptor'];pop=d['population'];counts[pop+'_local_complete']+=1
  if r['host']!='127x01' and not (p.parent/'hub-ack.json').exists():continue
  if d['id'] in seen:errors.append('duplicate block:'+d['id']);continue
  seen.add(d['id']);counts[pop+'_hub_complete']+=1;counts['games']+=len(r['games']);counts['interfered_blocks']+=bool(r.get('interference',{}).get('interfered'))
  if len(r['games'])!=8:errors.append('arm count:'+d['id'])
  for name,h in r['games'].items():
   f=p.parent/'games'/name
   if not f.exists() or sha(f)!=h:errors.append('raw hash:'+d['id']+':'+name);continue
   if not validate:continue
   raw=read(f);m=raw['metadata'];s=raw['search_ab'];arm=raw['cohort'];spec=plan()['arms'][arm]
   # Only this explicit projection is used. Loss and winner fields are never accessed.
   if not m['terminal'] or m['cell']!=d['cell'] or m['seat']!=d['seat'] or m['seed']!=d['seed']:errors.append('metadata:'+d['id'])
   if s['nice']!=10 or s['scheduler']!=0 or s['worker_affinity']!=r['slot_cores'][:1 if spec['threads']==1 else spec['threads']+1]:errors.append('core scheduling:'+d['id'])
   if any(e['during_decision'] for e in s['gc_maintenance']):errors.append('GC in decision:'+d['id'])
   if spec['policy']!='v1-unmodified' and s['policy_cache_counts']['forward']!=s['policy_cache_counts']['fallback']:errors.append('forward caching:'+d['id'])
   stats=s['deadline_stats'];lat=s['latency_seconds']
   if len(stats)!=len(lat):errors.append('decision length:'+d['id'])
   for wall,v in zip(lat,stats):
    expected=max(0.,wall-spec['deadline_seconds'])
    if v['overrun_seconds']!=expected or v['delayed_ticks']!=math.ceil(expected*20):errors.append('honest lateness:'+d['id'])
    if any(k not in v for k in ('unpruned_candidate_count','own_elixir','fallback_action','threads','coarse_horizon','default_source')):errors.append('C17 fields:'+d['id'])
    timing['decisions']+=1;timing['cutoffs']+=bool(v['hit']);timing['fallbacks']+=bool(v['fallback']);timing['overruns']+=expected>0
 return dict(utc=utc(),sealed=True,counts=dict(counts),health_counts=dict(timing),errors=errors,passed=not errors)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--validate',action='store_true');a=p.parse_args();r=health(a.root,a.validate);write(a.out,r);print(json.dumps(r));assert r['passed']
if __name__=='__main__':main()
