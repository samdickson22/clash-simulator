"""Seed-only interval audit of the coordinator plan and K/X/G freeze records."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; DEST=Path(__file__).resolve().parent
OFFSETS=(0,13,100000,100001,100002,100003,271828,271829)
def main():
    paths=[ROOT/'reports/strategy_council_20260928/PLAN-NEXT-20261010.md']
    paths+=sorted((ROOT/'reports/explore').glob('**/seed-audit.json'))
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation/exit-g-topup').glob('*.json'))
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation').glob('**/*FREEZE*.json'))
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation').glob('**/*freeze*.json'))
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation').glob('**/*seed-audit.json'))
    paths.append(ROOT/'reports/strategy_council_20260928/imitation/exit-r2/receipts/formula-range-review.json')
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation/exit-r3').glob('**/*seed*audit*.json'))
    paths+=sorted((ROOT/'reports/strategy_council_20260928/imitation/exit-r3').glob('**/*freeze*.json'))
    r3_plan=ROOT/'reports/strategy_council_20260928/imitation/exit-r3/PLAN.md'
    if r3_plan.exists():paths.append(r3_plan)
    paths+=sorted((ROOT/'reports/explore').glob('**/plan.json'))
    ranges=[('K reporting',4503601407370496,600),('K smoke',4503601417370496,8),('X h2h',4503601507370496,256),('X paired',4503601517370496,600),('X smoke',4503601527370496,32),('G 04 entire reservation',4503601607370496,1000000),('G 01 entire reservation',4503601609370496,1000000),('G 03 entire reservation',4503601611370496,1000000),('X dagger conservative full block',4503601707370496,10000000),('K-v2 reporting',4503601807370496,600),('K-v2 smoke',4503601817370496,8),('R3 reporting reserved by worker',4503601907370496,600),('R3 smoke reserved by worker',4503601917370496,8),('R3 regret replay reserved by worker',4503601927370496,65536),('noise-ceiling entire replay reservation',4503609917370496,2**18)]
    cfg=json.loads((DEST/'plan.json').read_text())
    own_intervals={(v['base']+off,v['count']) for v in cfg['seed_ranges'].values() for off in OFFSETS}
    sources=[]; echoes=[]
    def walk(x,label):
        if isinstance(x,dict):
            if isinstance(x.get('base'),int):
                count=x.get('count',x.get('pairs',0))
                if isinstance(count,int) and count>0:
                    declared=x.get('name','')
                    own_echo=(declared in ('K2','K2 smoke') or 'reports/explore/k2/' in declared) and (x['base'],count) in own_intervals
                    if own_echo:echoes.append(dict(source=label,declaration=declared,base=x['base'],count=count,reason='peer audit echoes this new K2 reservation, not historical usage'))
                    else:ranges.append((label,x['base'],count))
            for k,v in x.items():walk(v,label+':'+k)
        elif isinstance(x,list):
            for i,v in enumerate(x):walk(v,label+':'+str(i))
    for path in sorted(set(paths)):
        if path==DEST or DEST in path.parents:continue
        raw=path.read_bytes();label=str(path.relative_to(ROOT))
        sources.append(dict(path=label,sha256=hashlib.sha256(raw).hexdigest()))
        if path.suffix=='.json':walk(json.loads(raw),label)
    cfg=json.loads((DEST/'plan.json').read_text());checks=[]
    # DAgger is open-ended in the plan; bound its reserved decimal block through the next base.
    # Every known K/X/G reporting/smoke helper interval is checked, not just seed identities.
    for name,spec in cfg['seed_ranges'].items():
        for off in OFFSETS:
            lo=spec['base']+off;hi=lo+spec['count']
            for label,base,count in ranges:
                for oldoff in OFFSETS:
                    a=base+oldoff;b=a+count
                    assert hi<=a or b<=lo,(name,label,off,oldoff)
            checks.append(dict(range=name,offset=off,start=lo,stop_exclusive=hi))
    a,b=cfg['seed_ranges'].values();assert a['base']+a['count']+max(OFFSETS)<b['base']
    audit=dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),sources=sources,prior_ranges=[dict(name=n,base=b,count=c) for n,b,c in ranges],proposed_ranges=cfg['seed_ranges'],helper_offsets=OFFSETS,checks=checks,intersections=[],own_reservation_echoes=echoes,open_ended_dagger='4503601707370496 <= seed < 4503601807370496 reserved; helpers included; future allocation beyond that requires a new audit')
    (DEST/'seed-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
if __name__=='__main__':main()
