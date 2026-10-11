"""Health-only projection; never compute or emit wins/losses/winner identities.

K4S delta vs T1: a block has len(descriptor order) games (8 or 10); with --validate (smoke admission) every
decision must carry the r3 §3.6 fields and the r3 §4.1 charge test must hold on every exit path.
"""
import argparse,collections,json,math
from pathlib import Path
from common import read,write,sha,utc,plan

K4S_FIELDS=('cpu_seconds','coarse_complete','coarse_scored','plays','frozen_action','student_default','sd1_default_action','sd1_p_play','coarse_order_sha256','chosen_action','fallback_used','selected_wait_ticks','poll_seconds','scale_sleep_seconds','prep_seconds','scored','positive_overrun_ms','charged_extra_ticks')
CHARGE_TOLERANCE=0.02

def path_of(v):return v.get('preparation_cutoff') or ('scored' if v['scored'] else 'unscored')

def sd1_errors(v,spec):
 """Value/nullability relationships of the r3 §3.6 decision record (outcome-blind)."""
 p=path_of(v);bad=[]
 if spec['default_source']=='SD1':
  if v['sd1_default_action'] is None or v['sd1_p_play'] is None:bad.append('sd1 default/p_play')
  if (v['coarse_order_sha256'] is None)!=(p=='belief'):bad.append('coarse order')
 elif v['sd1_default_action'] is not None or v['sd1_p_play'] is not None or v['coarse_order_sha256'] is not None:bad.append('K4 carries SD1 fields')
 if any((v[k] is None)!=(p!='scored') for k in ('coarse_complete','coarse_scored','plays')):bad.append('scan nullability')
 if v['chosen_action']!=v['action'] or v['fallback_used']!=v['fallback'] or v['charged_extra_ticks']!=v['delayed_ticks'] or abs(v['positive_overrun_ms']-1000*v['overrun_seconds'])>1e-9:bad.append('aliases')
 return ','.join(bad)

def health(root,validate=False):
 counts=collections.Counter();errors=[];timing=collections.Counter();seen=set();charge=collections.defaultdict(list);scored_arms=set();arms_seen=set()
 for p in sorted(Path(root).glob('*/complete.json')):
  r=read(p);d=r['descriptor'];pop=d['population'];counts[pop+'_local_complete']+=1
  if r['host']!='127x01' and not (p.parent/'hub-ack.json').exists():continue
  if d['id'] in seen:errors.append('duplicate block:'+d['id']);continue
  seen.add(d['id']);counts[pop+'_hub_complete']+=1;counts['games']+=len(r['games']);counts['interfered_blocks']+=bool(r.get('interference',{}).get('interfered'));counts['ssh_family_interfered_blocks']+=bool(r.get('interference',{}).get('ssh_family',{}).get('interfered'))
  for kind,n in r.get('interference',{}).get('allowlist_observations',{}).items():counts['allowlist_'+kind]+=n
  if len(r['games'])!=len(d['order']):errors.append('arm count:'+d['id'])
  for name,h in r['games'].items():
   f=p.parent/'games'/name
   if not f.exists() or sha(f)!=h:errors.append('raw hash:'+d['id']+':'+name);continue
   if not validate:continue
   raw=read(f);m=raw['metadata'];s=raw['search_ab'];arm=raw['cohort'];spec=plan()['arms'][arm];arms_seen.add(arm)
   if name!=f"{d['id']}-d27-{arm}.json" or arm not in d['order']:errors.append('game identity:'+d['id']+':'+name)
   # Only this explicit projection is used. Loss and winner fields are never accessed.
   if not m['terminal'] or m['cell']!=d['cell'] or m['seat']!=d['seat'] or m['seed']!=d['seed']:errors.append('metadata:'+d['id'])
   if any(m.get(k)!=spec[k] for k in ('speed_cell','budget_ms','inference_scale','scale_mode','kernel','default_source')) or m.get('block_id')!=d['id'] or m.get('rotation')!=d['rotation']:errors.append('K4S metadata values:'+d['id'])
   if s['nice']!=10 or s['scheduler']!=0 or s['worker_affinity']!=r['slot_cores'][:1 if spec['threads']==1 else spec['threads']+1]:errors.append('core scheduling:'+d['id'])
   if any(e['during_decision'] for e in s['gc_maintenance']):errors.append('GC in decision:'+d['id'])
   if spec['policy']!='v1-unmodified' and s['policy_cache_counts']['forward']!=s['policy_cache_counts']['fallback']:errors.append('forward caching:'+d['id'])
   stats=s['deadline_stats'];lat=s['latency_seconds']
   if not stats:errors.append('no decisions:'+d['id'])
   for v in stats:
    if v.get('scored'):scored_arms.add(arm)
   if len(stats)!=len(lat):errors.append('decision length:'+d['id'])
   for wall,v in zip(lat,stats):
    expected=max(0.,wall-spec['deadline_seconds'])
    if v['overrun_seconds']!=expected or v['delayed_ticks']!=math.ceil(expected*20):errors.append('honest lateness:'+d['id'])
    if any(k not in v for k in ('unpruned_candidate_count','own_elixir','fallback_action','threads','coarse_horizon','default_source')):errors.append('C17 fields:'+d['id'])
    if any(k not in v for k in K4S_FIELDS):errors.append('K4S fields:'+d['id'])
    elif (v['frozen_action'] is None)==bool(v['scored']) or v['default_source']!=spec['default_source'] or v['threads']!=spec['threads']:errors.append('K4S field values:'+d['id'])
    elif sd1_errors(v,spec):errors.append('SD1/scan/alias fields:'+d['id']+':'+sd1_errors(v,spec))
    elif spec['speed_cell']==1.:
     if v['scale_sleep_seconds']!=0.:errors.append('charge at c=1:'+d['id'])
    else:charge[arm,'prep' if v.get('preparation_cutoff') else 'scored' if v['scored'] else 'unscored'].append(v['scale_sleep_seconds']/(v['poll_seconds']+v['scale_sleep_seconds'])-(1-spec['speed_cell']))
    timing['decisions']+=1;timing['cutoffs']+=bool(v['hit']);timing['fallbacks']+=bool(v['fallback']);timing['overruns']+=expected>0
 if validate and arms_seen-scored_arms:errors.append('arms without a scored decision:'+','.join(sorted(arms_seen-scored_arms)))
 # r3 §4.1 charge test: on every exit path, sleep share = (1/c-1)/(1/c) +- 0.02 (mean and every decision).
 charge_summary={f'{k[0]}|{k[1]}':dict(n=len(v),mean_dev=sum(v)/len(v),max_abs_dev=max(map(abs,v))) for k,v in sorted(charge.items())}
 for k,r in charge_summary.items():
  if abs(r['mean_dev'])>CHARGE_TOLERANCE or r['max_abs_dev']>CHARGE_TOLERANCE:errors.append('charge share:'+k)
 return dict(utc=utc(),sealed=True,counts=dict(counts),health_counts=dict(timing),charge=charge_summary,errors=errors,passed=not errors)

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--validate',action='store_true');a=p.parse_args();r=health(a.root,a.validate);write(a.out,r);print(json.dumps(r));assert r['passed']
if __name__=='__main__':main()
