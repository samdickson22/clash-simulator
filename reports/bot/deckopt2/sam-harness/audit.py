"""Final whole-bank integrity audit, without constructing a Runtime or game."""
import argparse,json
from collections import Counter
from sam_common import ROOT,OLD,sha,utc,dump
from fullpool_clean import problems
def audit(stage,partial=False):
 d=ROOT/stage;bank=json.loads((d/'validation/bank.json').read_text());meta=json.loads((d/'manifest.json').read_text());digest=sha(d/'validation/bank.json')
 assert sha(d/'manifest.json')==bank['manifest_sha256']
 assert all(sha(ROOT/name)==value for name,value in meta['helper_sha256'].items())
 cases={c['id']:c for c in bank['cases']}
 rows=[json.loads(p.read_text()) for p in (d/'validation/rows').glob('*.json')]
 keys=[(r['id'],r['candidate'],r['player']) for r in rows]
 expected={(c,n,p) for c in cases for n in bank['candidates'] for p in bank['players']}
 assert len(keys)==len(set(keys))
 assert (set(keys)<=expected if partial else set(keys)==expected),(stage,len(keys),len(expected))
 assert Counter(c['opponent'] for c in cases.values())=={p:bank['cases_per_policy'] for p in meta['opponents']}
 drops=Counter();searches=0
 for row in rows:
  assert row['bank_sha256']==digest and not problems(row)
  case=cases[row['id']];seat=row['seat'];result=row['result']
  for field in ('seed','seat','source_index','opponent','opponent_deck','opponent_levels','own_permutation'):assert row[field]==case[field],(row['id'],field)
  assert result['terminal'] and row['win']==int(result['winner']==seat)
  assert not row['failures'] and not any(row['live_errors'].values())
  assert not result['channels'][str(seat)]['rejected']
  own=[meta['candidates'][row['candidate']][i] for i in case['own_permutation']]
  assert result['decks'][seat]==own and result['decks'][1-seat]==case['opponent_deck']
  assert row['truth_levels'][seat]==meta['candidate_plans'][row['candidate']]['levels']
  assert row['truth_levels'][1-seat]==case['opponent_levels']
  assert row['truth_tower_levels']==[meta['tower_level']]*2
  own_diag=result['public_diagnostics'][str(seat)];config=own_diag['start_config']
  assert config['belief_class']=='FullPoolBelief' and config['name']==row['player']
  assert config['fast_path'].endswith('/fits/f1a2/step-001200.pt')
  assert config['native_threads']==1 and config['pool_size']==0 and config['chunks']==4
  assert all(config[k] is None for k in ('deadline_seconds','effective_deadline_seconds','search_deadline_seconds'))
  assert own_diag['cutoff_hits']==0;searches+=own_diag['search_decisions']
  if row['opponent']=='LIVE-K4CW-r16':
   strong=result['public_diagnostics'][str(1-seat)]['start_config']
   assert strong['belief_class']=='LiveBelief' and strong['runtime_belief']=='c56'
   assert strong['fast_path'].endswith('/students/it5s2-step001200.pt') and strong['fast_threshold']==.5375
  drops.update(row['unmapped'])
 assert set(drops)<={'unmapped_unit:SpearGoblin_Dummy'}
 preserved=0
 snapshot=ROOT/'rows-at-coordinator-audit.json'
 if snapshot.exists():
  for relative,value in json.loads(snapshot.read_text())['rows'].items():
   if relative.startswith(stage+'/'):assert sha(ROOT/relative)==value;preserved+=1
 seeds={c['seed'] for c in cases.values()}
 assert len(seeds)==len(cases)
 for other in ('upgrades','max','current'):
  if other!=stage:assert not seeds&{c['seed'] for c in json.loads((ROOT/other/'validation/bank.json').read_text())['cases']}
 for old in ('fullpool/validation','screen','new-cards/screen','final-validation/validation'):
  assert not seeds&{c['seed'] for c in json.loads((OLD/old/'bank.json').read_text())['cases']}
 result=dict(utc=utc(),stage=stage,passed=True,complete=not partial,games=len(rows),expected_games=len(expected),cases=len(cases),cases_per_policy=bank['cases_per_policy'],bank_sha256=digest,
  genuine_failures=0,cutoff_hits=0,search_decisions=searches,drop_counters=dict(drops),preserved_row_hashes=preserved,
  host_games=dict(Counter(r['host'] for r in rows)),same_case_single_host_and_worker=all(len({(r['host'],r['block']['worker_pid']) for r in rows if r['id']==case})==1 for case in {r['id'] for r in rows}))
 assert result['same_case_single_host_and_worker']
 dump(d/('partial-integrity-audit.json' if partial else 'integrity-audit.json'),result);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=('upgrades','max','current'));p.add_argument('--partial',action='store_true');a=p.parse_args();audit(a.stage,a.partial)
