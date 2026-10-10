from collections import Counter
import pytest
from schedule import blocks,block,replacement,ARMS

def test_balanced_cells_dispatch_and_descriptive_last():
 r=blocks();assert len(r)==3072
 for i in range(600):assert [x['population'] for x in r[5*i:5*i+5]]==['primary']*4+['guard']
 assert all(x['population']=='descriptive' for x in r[3000:])
 assert Counter(x['cell'] for x in r if x['population']=='primary')==Counter(dict.fromkeys(range(50),48))
 assert sorted(Counter(x['cell'] for x in r if x['population']=='guard').values())==[33]*12+[34]*6
 assert Counter(x['cell'] for x in r if x['population']=='descriptive')==Counter(dict.fromkeys(range(18),4))
 assert len({(x['seat'],x['own_index'],x['opponent_index']) for x in r if x['population']=='primary'})==50
 assert len({(x['seat'],x['own_index'],x['opponent_index']) for x in r if x['population']=='guard'})==18
 assert all(set(x['order'])==set(ARMS) and len(x['order'])==8 for x in r)

def test_guard_replacement_keeps_original_cell_even_when_index_mod_differs():
 lost=block('guard',0);r=replacement(lost,[])
 assert r['index']==600 and r['index']%18==6 and r['cell']==0
 assert (r['seat'],r['own_index'],r['opponent_index'],r['order'])==(lost['seat'],lost['own_index'],lost['opponent_index'],lost['order'])
 ledger=[dict(lost=lost,replacement=r)]
 next_=replacement(r,ledger);assert next_['index']==618 and next_['cell']==0 and next_['replaces']==lost['id']
 with pytest.raises(AssertionError):replacement(lost,ledger)

def test_cell_bank_exhaustion_and_descriptive_not_replaced():
 for pop,max_k in [('primary',8),('guard',5)]:
  ledger=[];lost=block(pop,0)
  for k in range(max_k+1):
   r=replacement(lost,ledger);ledger.append(dict(lost=lost,replacement=r));lost=r
  with pytest.raises(AssertionError,match='exhausted'):replacement(lost,ledger)
 assert replacement(block('descriptive',0),[]) is None

def test_population_replacement_cap():
 for pop,n,limit in [('primary',50,240),('guard',18,60)]:
  ledger=[dict(lost=block(pop,i),replacement=dict(id=f'replaced-{i}')) for i in range(limit)]
  with pytest.raises(AssertionError,match='population'):replacement(block(pop,limit),ledger)


def test_each_cell_visits_every_host_balanced_for_two_or_three_hosts():
 from schedule import assign_hosts
 for hosts in [('127x01','127x03'),('127x01','127x03','127x08')]:
  rows=assign_hosts(blocks(),hosts)
  for pop,cells in [('primary',50),('guard',18),('descriptive',18)]:
   for c in range(cells):
    counts=Counter(r['host'] for r in rows if r['population']==pop and r['cell']==c)
    assert set(counts)==set(hosts) and max(counts.values())-min(counts.values())<=1
   counts=Counter((r['seat'],r['host']) for r in rows if r['population']==pop)
   for seat in (0,1):
    assert max(counts[seat,h] for h in hosts)-min(counts[seat,h] for h in hosts)<=2
