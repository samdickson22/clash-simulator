"""Outcome-independent SHA-priority sampling stratified by elixir/legal play count."""
import argparse,bisect,collections,gzip,hashlib,json,pickle,copy
from pathlib import Path
from common import plan,read,write,sha,utc

def stratum(elixir,legal):
 c=plan()['corpus_selection'];return (bisect.bisect_right(c['elixir_bins'],elixir),bisect.bisect_right(c['legal_play_count_bins'],legal))
def priority(row):return hashlib.sha256(f"{row['tier']}/{row['seed']}/{row['info'].tick}".encode()).hexdigest()
def quotas(counts,n):
 assert counts and n>=len(counts)
 total=sum(counts.values());keys=sorted(counts);q=dict.fromkeys(keys,1);left=n-len(keys)
 raw={k:left*counts[k]/total for k in keys}
 for k in keys:q[k]+=int(raw[k])
 for k in sorted(keys,key=lambda k:(-(raw[k]-int(raw[k])),k))[:n-sum(q.values())]:q[k]+=1
 assert sum(q.values())==n
 return q

def committed_belief(belief):
 # The registered complete no-deadline decision discards private suspended work.
 # Seal the committed public posterior without the non-pickleable generator.
 clone=copy.copy(belief);clone._pending=None
 return copy.deepcopy(clone)

class Reservoir:
 def __init__(self):self.counts=collections.Counter();self.rows=collections.defaultdict(list);self.cap=plan()['corpus_selection']['reservoir_per_stratum'];self.health=collections.Counter()
 def add(self,row,deadline_cut=False):
  s=stratum(row['strata']['elixir'],row['strata']['legal_play_count']);self.counts[s]+=1
  assert list(s)==row['strata']['bins']
  self.health['eligible_search_opportunities']+=1;self.health['deadline_cut']+=int(deadline_cut);self.health['suspended_transaction']+=int(row['belief_had_suspended_transaction'])
  bucket=self.rows[s];bucket.append((priority(row),row));bucket.sort(key=lambda x:x[0])
  del bucket[self.cap:]
 def dump(self,path):
  with gzip.open(path,'wb') as f:pickle.dump(dict(counts=dict(self.counts),rows=dict(self.rows),health=dict(self.health)),f,protocol=5)

def select(paths,n=300):
 counts=collections.Counter();pools=collections.defaultdict(list)
 for path in sorted(paths):
  with gzip.open(path,'rb') as f:r=pickle.load(f)
  counts.update(r['counts'])
  for s,rows in r['rows'].items():pools[s].extend(rows)
 q=quotas(counts,n);chosen=[]
 for s in sorted(q):
  rows=sorted(pools[s],key=lambda x:x[0]);assert len(rows)>=q[s],('insufficient occupied stratum',s,len(rows),q[s])
  chosen.extend(row for _,row in rows[:q[s]])
 chosen.sort(key=lambda r:r['id']);assert len(chosen)==n and len({r['id'] for r in chosen})==n
 return chosen,counts,q

def main():
 p=argparse.ArgumentParser();p.add_argument('--captures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 all_rows=[];summary={}
 for tier in ('K0c','S','K2','K4'):
  paths=sorted(a.captures.glob(f'corpus-{tier}-*/capture.pkl.gz'))
  paths=[p for p in paths if (p.parent/'local-complete.json').exists() and read(p.parent/'descriptor.json')['index'] not in plan()['corpus_selection']['excluded_indices']]
  assert paths,tier
  health=collections.Counter()
  for p in paths:
   proof=read(p.parent/'local-complete.json');descriptor=read(p.parent/'descriptor.json')
   assert descriptor['phase']=='corpus' and descriptor['game_class']=='qualification' and proof['capture_sha256']==sha(p)
   with gzip.open(p,'rb') as f:health.update(pickle.load(f)['health'])
  rows,counts,q=select(paths);assert all(r['tier']==tier and plan()['seed_ranges']['corpus']['base']<=r['seed']<plan()['seed_ranges']['corpus']['base']+64 for r in rows)
  target=a.out/f'{tier}-states.pkl';target.write_bytes(pickle.dumps(rows,protocol=5));all_rows.extend(rows)
  summary[tier]=dict(states=len(rows),state_inventory=[dict(id=r['id'],sha256=hashlib.sha256(pickle.dumps(r,protocol=5)).hexdigest()) for r in rows],capture_health=dict(health),deadline_cut_fraction=health['deadline_cut']/health['eligible_search_opportunities'],suspended_transaction_fraction=health['suspended_transaction']/health['eligible_search_opportunities'],selected_suspended_transaction_states=sum(r['belief_had_suspended_transaction'] for r in rows),sha256=sha(target),counts={str(k):v for k,v in counts.items()},selected_stratum_counts={str(k):v for k,v in q.items()},source_capture_shas={str(p):sha(p) for p in paths})
 (a.out/'states.pkl').write_bytes(pickle.dumps(all_rows,protocol=5))
 write(a.out/'corpora.json',dict(utc=utc(),selection_rule=plan()['corpus_selection'],selection_script_sha256=sha(__file__),seed_bank=plan()['seed_ranges']['corpus'],tiers=summary,combined_sha256=sha(a.out/'states.pkl'),outcomes_read=False))
 print(json.dumps(dict(tiers={k:r['states'] for k,r in summary.items()},states_sha256=sha(a.out/'states.pkl'),outcomes_read=False)))
if __name__=='__main__':main()
