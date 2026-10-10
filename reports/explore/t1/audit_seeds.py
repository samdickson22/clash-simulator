"""T1 audit historical frozen interval evidence and every helper offset."""
import itertools,json
from pathlib import Path
from common import ROOT,HERE,read,write,sha,utc,plan
OFFSETS=(0,13,100000,100001,100002,100003,271828,271829)
def main():
 cfg=plan();prior=[];sources=[];echoes=[]
 # S1's exhaustive frozen audit supplies historical ranges, including source provenance.
 for name in ('reports/explore/s1/seed-audit.json','reports/explore/k2/seed-audit.json'):
  p=ROOT/name;r=read(p);sources.append(dict(path=name,sha256=sha(p)));prior.extend(r['prior_ranges']);prior.extend(dict(base=v['base'],count=v['count'],source_names=[name+':'+k]) for k,v in r['proposed_ranges'].items())
 prior.extend(dict(base=b,count=c,source_names=[n]) for n,b,c in [('R1 round2 full allocation',4503599727370496,10_000_000),('G full reserved range',4503601607370496,3_000_000),('G 03 reserved range',4503601611370496,1_000_000),('S1 abandoned R1',4503602607370496,600),('S1 smoke',4503602617370496,8),('S1 R2',4503602707370496,600)])
 own={(v['base'],v['count']) for v in cfg['seed_ranges'].values()}
 def walk(x,label):
  if isinstance(x,dict):
   if isinstance(x.get('base'),int) and isinstance(x.get('count'),int) and x['count']>0:
    if (x['base'],x['count']) in own:
     echoes.append(dict(path=label,base=x['base'],count=x['count'],declaration=x.get('name',x.get('source_names',''))))
    else:prior.append(dict(base=x['base'],count=x['count'],source_names=[label]))
   for k,v in x.items():walk(v,label+':'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):walk(v,label+':'+str(i))
 paths=set()
 for root in ('reports','imitation'):
  for pattern in ('**/*seed*audit*.json','**/*freeze*.json','**/*FREEZE*.json','**/plan.json'):
   paths.update((ROOT/root).glob(pattern))
 for p in sorted(paths):
  if HERE in p.parents:continue
  sources.append(dict(path=str(p.relative_to(ROOT)),sha256=sha(p)));walk(read(p),str(p.relative_to(ROOT)))
 unique={}
 for r in prior:
  unique.setdefault((r['base'],r['count']),set()).update(r.get('source_names',[r.get('name','historical')]))
 checks=[]
 for name,v in cfg['seed_ranges'].items():
  for off in OFFSETS:
   lo=v['base']+off;hi=lo+v['count']
   for (b,n),labels in unique.items():
    for oldoff in OFFSETS:
     assert hi<=b+oldoff or b+n+oldoff<=lo,(name,off,b,n,oldoff,sorted(labels))
   checks.append(dict(range=name,offset=off,start=lo,stop_exclusive=hi))
 # Adjacent replacement bank belongs to its original population reservation.
 grouped=[('primary',cfg['seed_ranges']['primary']['base'],2880),('guard',cfg['seed_ranges']['guard']['base'],720)]+[(k,v['base'],v['count']) for k,v in cfg['seed_ranges'].items() if k not in ('primary','guard','primary_replacements','guard_replacements')]
 for (a,b,n),(c,d,m) in itertools.combinations(grouped,2):
  for x,y in itertools.product(OFFSETS,repeat=2):assert b+n+x<=d+y or d+m+y<=b+x,(a,c,x,y)
 write(HERE/'seed-audit.json',dict(utc=utc(),status='DRAFT-PASS',proposed_ranges=cfg['seed_ranges'],helper_offsets=OFFSETS,sources=sources,prior_ranges=[dict(base=b,count=n,source_names=sorted(s)) for (b,n),s in sorted(unique.items())],own_reservation_echoes=echoes,checks=checks,intersections=[]))
 print(json.dumps(dict(ranges=len(cfg['seed_ranges']),historical_intervals=len(unique),checks=len(checks),overlaps=0)))
if __name__=='__main__':main()
