"""Own interval/formula audit, including every K/K-v2/K2/X/descriptive/G bank."""
import hashlib,json,resource,subprocess,time
from pathlib import Path
OFFSETS=(0,13,100000,100001,100002,100003,271828,271829)
PROPOSED={'reporting':(4503601907370496,600),'smoke':(4503601917370496,8),'regret_helpers':(4503601927370496,65536)}
KNOWN=[('K',4503601407370496,600),('K smoke',4503601417370496,8),('X h2h',4503601507370496,256),('X S-default',4503601517370496,600),('X smoke',4503601527370496,32),('G04',4503601607370496,1000000),('G01',4503601609370496,1000000),('G03',4503601611370496,1000000),('X DAgger full decimal bank',4503601707370496,10000000),('K-v2',4503601807370496,600),('K-v2 smoke',4503601817370496,8),('X descriptive coordinator04:05Z',4503602007370496,600),('X descriptive qualification',4503602017370496,32),('K2',4503602307370496,600),('K2 smoke',4503602317370496,8),('noise ceiling',4503609917370496,2**18)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    start=time.monotonic();j=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r1');root=j/'provenance';sources=[];ranges=list(KNOWN);own_declarations=[]
    def walk(x,label):
        if isinstance(x,dict):
            base=x.get('base',x.get('start'));count=x.get('count',x.get('pairs'))
            if isinstance(base,int) and count is None and isinstance(x.get('stop_exclusive'),int):count=x['stop_exclusive']-base
            if isinstance(base,int) and isinstance(count,int) and count>0:
                if base in {b for b,c in PROPOSED.values()}:
                    own_declarations.append(dict(path=label,base=base,count=count,reason='peer audit records new R3 reservation; declaration only'))
                else:ranges.append((label,base,count))
            for k,v in x.items():walk(v,label+':'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,label+':'+str(i))
    for p in sorted(root.rglob('*.json')):
        label=str(p.relative_to(root));sources.append(dict(path=label,sha256=sha(p)));walk(json.loads(p.read_text()),label)
    # Historical exact literal/formula evidence is inherited by pinned R1/R2 inventories.
    assert any('exit-r2/receipts/seed-audit.json' in s['path'] for s in sources)
    assert any('k-v2/seed-audit.json' in s['path'] for s in sources)
    assert any('k2/plan.json' in s['path'] for s in sources)
    assert any('exit-g-topup/FREEZE.json' in s['path'] for s in sources)
    intersections=[];checks=[]
    for n,(b,c) in PROPOSED.items():
        for off in OFFSETS:
            lo=b+off;hi=lo+c
            for label,old,count in ranges:
                for oldoff in OFFSETS:
                    a=old+oldoff;z=a+count
                    if lo<z and a<hi:intersections.append(dict(proposed=n,prior=label,offset=off,prior_offset=oldoff))
            checks.append(dict(name=n,offset=off,start=lo,stop_exclusive=hi))
    for a,(b,c) in PROPOSED.items():
        for z,(old,count) in PROPOSED.items():
            if a==z:continue
            for off in OFFSETS:
                for oldoff in OFFSETS:assert b+off+c<=old+oldoff or old+oldoff+count<=b+off
    u=resource.getrusage(resource.RUSAGE_SELF)
    result=dict(schema='clasher.exit-r3.seed-audit.v1',utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),passed=not intersections,sources=sources,prior_ranges=[dict(name=n,base=b,count=c) for n,b,c in ranges],ranges={n:dict(base=b,count=c) for n,(b,c) in PROPOSED.items()},helper_offsets=OFFSETS,checks=checks,intersections=intersections,own_new_declarations=own_declarations,train_seed=2026101013,bootstrap_seed=80991013,cpu_seconds=u.ru_utime+u.ru_stime,wall_seconds=time.monotonic()-start,interpretation='Own full-bank and helper-offset interval audit; pinned historical exact inventories and formula reviews retained. R1 heldout64 reused deliberately for exploratory calibration/evaluation. Peer references to new R3 reservations are declarations, not consumed games. Descriptive20/201 supplied by coordinator before freeze.')
    (j/'seed-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ('utc','passed','intersections','cpu_seconds')}));assert result['passed']
if __name__=='__main__':main()
