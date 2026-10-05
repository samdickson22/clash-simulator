import collections,gzip,json,statistics,sys
from study import OUT,dump,base_slug
name=sys.argv[1] if len(sys.argv)>1 else 'results-terminal-50.jsonl'
rs=[json.loads(l) for l in open(OUT/name)]
summary={'n':len(rs),'configured':sum('configured' in r for r in rs),'ended':sum(r.get('final',{}).get('ended',False) for r in rs),'exceptions':collections.Counter(r.get('failure') for r in rs)}
acts=[a for r in rs for a in r.get('action_receipts',[])];summary['schedule_states']=dict(collections.Counter(a['state'] for a in acts));summary['schedule_errors']=dict(collections.Counter(a['error'] for a in acts));summary['all_scheduled_injected']=sum(all(a['state']=='succeeded' for a in r['action_receipts']) and not r['schedule_rejections'] for r in rs)
summary['matches_by_action_problem']={k:sum(any(a['error']==k for a in r['action_receipts']) for r in rs) for k in set(a['error'] for a in acts)}
summary['matches_pending']=sum(any(a['state']=='pending' for a in r['action_receipts']) for r in rs)
summary['crown_pair_exact']=sum(r['final']['crownsRaw']==[r['recorded'][s]['crowns'] for s in ['team','opponent']] for r in rs)
summary['winner_exact']=sum((r['final']['crownsRaw'][0]>r['final']['crownsRaw'][1])-(r['final']['crownsRaw'][0]<r['final']['crownsRaw'][1]) == (r['recorded']['team']['crowns']>r['recorded']['opponent']['crowns'])-(r['recorded']['team']['crowns']<r['recorded']['opponent']['crowns']) for r in rs)
hp_exact=0;errors=[]
for r in rs:
 eq=True
 for owner,side in enumerate(['team','opponent']):
  obj={o['nativeObjectId']:o['hp'] for o in r['final']['towers']};base=5000000+3*owner
  # Corpus princess fields are survivor-first, not reliable lane labels.
  got=[obj.get(base,0),*sorted([obj.get(base+1,0),obj.get(base+2,0)])]
  rec=r['recorded'][side]['towers'];want=[rec['king'],*sorted([rec['princess_left'],rec['princess_right']])]
  eq &= got==want;errors.extend(abs(a-b) for a,b in zip(got,want))
 hp_exact+=eq
summary['all_six_hp_exact_lane_invariant']=hp_exact;summary['hp_mae']=statistics.mean(errors)
summary['total_s']=sum(r['total_s'] for r in rs);summary['duration_s_mean']=statistics.mean(r['recorded_tick']/20 for r in rs);summary['native_ticks_mean']=statistics.mean(r['last_tick'] for r in rs)
summary['observations']=sum(r['observations'] for r in rs);summary['loop_s']=sum(r['loop_s'] for r in rs)
summary['early_terminal_before_recorded_end']=sum(r['last_tick']<r['recorded_tick'] for r in rs)
summary['early_terminal_before_recorded_end_minus91']=sum(r['last_tick']<r['recorded_tick']-91 for r in rs)
dump('summary-levelled.json' if name=='levelled-order.jsonl' else ('summary-inferred.json' if name=='inferred-order.jsonl' else 'summary.json'),summary);print(json.dumps(summary,indent=2))
