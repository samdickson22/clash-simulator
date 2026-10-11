"""PREREG-K4S outcome-blind block allocation and cell-preserving replacement ledger (r3 §3.1, §3.4).

Delta vs T1 schedule.py: 8 core arm-cells rotated by rho = floor(L/50) mod 8 (primary) or
floor(L/18) mod 8 (guard), L = logical original index; two subsample arms (K4-140, K4-120) inserted
after rotated core positions 3 and 6 for primary L < 600 and guard L < 300; 10:3 primary:guard
dispatch; replacement index 3000+50k+c / 900+18k+c with caps 300/90 and k <= 11/9.
assign_hosts (T1 B2 balancer) is unchanged.
"""
import argparse
from collections import Counter
from common import plan,read,write,utc
CORE=('K4-200','K4S-200','K4-180','K4S-180','K4-160','K4S-160','K4S-140','K4S-120')
SUBSAMPLE=('K4-140','K4-120')
ARMS=CORE+SUBSAMPLE
CELLS={'primary':50,'guard':18,'smoke':50}
COUNTS={'primary':3000,'guard':900,'smoke':8}
SUB_LIMIT={'primary':600,'guard':300}
REPLACEMENT={'primary':dict(first=3000,stride=50,max_k=11,cap=300),'guard':dict(first=900,stride=18,max_k=9,cap=90)}

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

def rotation(pop,logical):
 if pop=='smoke':return logical%8
 return (logical//(50 if pop=='primary' else 18))%8

def order_for(rho,subsample):
 r=list(CORE[rho:]+CORE[:rho])
 return r[:3]+[SUBSAMPLE[0]]+r[3:6]+[SUBSAMPLE[1]]+r[6:] if subsample else r

def expected_order(d):
 return order_for(d['rotation'],d['subsample'])

def block(pop,index,*,cell=None,replaces=None,logical=None,replacement_k=None):
 cfg=plan();cell=index%CELLS[pop] if cell is None else cell
 assert 0<=cell<CELLS[pop]
 logical=index if logical is None else logical
 rho=rotation(pop,logical);sub=pop=='smoke' or logical<SUB_LIMIT[pop]
 return dict(id=f'{pop}-{index:04d}',population=pop,index=index,seed=cfg['seed_ranges'][pop]['base']+index,cell=cell,seat=cell%2,own_index=cell%5 if pop in ('primary','smoke') else (cell//2)%3,opponent_index=(cell//5)%5 if pop in ('primary','smoke') else cell//6,rotation=rho,subsample=sub,order=order_for(rho,sub),replaces=replaces,replacement_k=replacement_k)

def blocks(smoke=False):
 if smoke:return [block('smoke',i) for i in range(8)]
 rows=[]
 for g in range(300):
  rows.extend(block('primary',i) for i in range(10*g,10*g+10));rows.extend(block('guard',i) for i in range(3*g,3*g+3))
 return rows

def replacement(lost,ledger):
 pop=lost['population'];c=lost['cell']
 assert not any(r['lost']['id']==lost['id'] for r in ledger),'duplicate replacement assignment'
 assert pop in ('primary','guard')
 original=lost
 # Preserve the logical original even when a replacement itself is lost.
 while original.get('replaces'):
  original=next(r['lost'] for r in ledger if r['replacement'] and r['replacement']['id']==original['id'])
 rule=REPLACEMENT[pop]
 assert sum(r['lost']['population']==pop for r in ledger)<rule['cap'],'population replacement cap; stop and amend'
 k=sum(r['lost']['population']==pop and r['lost']['cell']==c for r in ledger)
 assert k<=rule['max_k'],'cell bank exhausted; stop and amend'
 i=rule['first']+rule['stride']*k+c
 assert i<COUNTS[pop]+plan()['seed_ranges'][pop+'_replacements']['count']
 return block(pop,i,cell=c,replaces=original['id'],logical=original['index'],replacement_k=k)

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--hosts',nargs='+',required=True);p.add_argument('--smoke',action='store_true');a=p.parse_args()
 assert set(a.hosts)<=set(plan()['compute']['hosts']);assert len(a.hosts)>=2 or a.smoke
 rows=blocks(a.smoke)
 if a.smoke:
  # r3 §4.1: >= 8 smoke blocks on every host; the same 8 excluded smoke seeds on each host.
  rows=[dict(r,host=h,dispatch=n) for n,(h,r) in enumerate((h,r) for h in a.hosts for r in rows)]
 else:assign_hosts(rows,a.hosts)
 write(a.out,dict(utc=utc(),arms=ARMS,hosts=a.hosts,blocks=rows,population_counts=dict(Counter(r['population'] for r in rows))))
if __name__=='__main__':main()
