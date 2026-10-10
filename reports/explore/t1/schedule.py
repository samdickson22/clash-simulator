"""Outcome-blind r3 block allocation and cell-preserving replacement ledger."""
import argparse
from collections import Counter
from common import plan,read,write,utc
ARMS=tuple(f'{t}-{d}' for t in ('K0c','S','K2','K4') for d in (200,160))
CELLS={'primary':50,'guard':18,'descriptive':18,'smoke':50}
COUNTS={'primary':2400,'guard':600,'descriptive':72,'smoke':8}

def assign_hosts(rows,hosts,history=()):
 assert len(hosts)>=2 and len(set(hosts))==len(hosts)
 cells=Counter();seats=Counter();totals=Counter()
 for r in history:
  h=r.get('host')
  if h in hosts:
   cells[r['population'],r['cell'],h]+=1;seats[r['population'],r['seat'],h]+=1;totals[h]+=1
 for n,r in enumerate(rows):
  # Each cell first visits its least-used host. Seat and total load break ties.
  h=min(hosts,key=lambda h:(cells[r['population'],r['cell'],h],seats[r['population'],r['seat'],h],totals[h],hosts.index(h)))
  r.update(dispatch=n,host=h)
  cells[r['population'],r['cell'],h]+=1;seats[r['population'],r['seat'],h]+=1;totals[h]+=1
 return rows

def block(pop,index,*,cell=None,replaces=None,rotation=None):
 cfg=plan();cell=index%CELLS[pop] if cell is None else cell
 assert 0<=cell<CELLS[pop]
 shift=(index if rotation is None else rotation)%len(ARMS)
 return dict(id=f'{pop}-{index:04d}',population=pop,index=index,seed=cfg['seed_ranges'][pop]['base']+index,cell=cell,seat=cell%2,own_index=cell%5 if pop in ('primary','smoke') else (cell//2)%3,opponent_index=(cell//5)%5 if pop in ('primary','smoke') else cell//6,order=list(ARMS[shift:]+ARMS[:shift]),replaces=replaces)

def blocks(smoke=False):
 if smoke:return [block('smoke',i) for i in range(8)]
 rows=[]
 for g in range(600):
  rows.extend(block('primary',i) for i in range(4*g,4*g+4));rows.append(block('guard',g))
 rows.extend(block('descriptive',i) for i in range(72))
 return rows

def replacement(lost,ledger):
 pop=lost['population'];c=lost['cell']
 assert not any(r['lost']['id']==lost['id'] for r in ledger),'duplicate replacement assignment'
 if pop=='descriptive':return None
 assert pop in ('primary','guard')
 original=lost
 # Preserve the logical original even when a replacement itself is lost.
 while original.get('replaces'):
  original=next(r['lost'] for r in ledger if r['replacement'] and r['replacement']['id']==original['id'])
 cap=240 if pop=='primary' else 60
 assert sum(r['lost']['population']==pop for r in ledger)<cap,'population replacement cap; stop and amend'
 k=sum(r['lost']['population']==pop and r['lost']['cell']==c for r in ledger)
 assert k<=(8 if pop=='primary' else 5),'cell bank exhausted; stop and amend'
 i=COUNTS[pop]+CELLS[pop]*k+c
 assert i<COUNTS[pop]+plan()['seed_ranges'][pop+'_replacements']['count']
 return block(pop,i,cell=c,replaces=original['id'],rotation=original['index'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--hosts',nargs='+',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
 assert set(a.hosts)<=set(plan()['compute']['hosts']);assert len(a.hosts)>=2
 rows=blocks(a.smoke)
 assign_hosts(rows,a.hosts)
 write(a.out,dict(utc=utc(),arms=ARMS,hosts=a.hosts,blocks=rows,population_counts=dict(Counter(r['population'] for r in rows))))
if __name__=='__main__':main()
