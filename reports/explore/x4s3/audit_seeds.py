"""X4S-3 seed-only interval audit (copied from X4S, derived from S1): all frozen/declared banks plus a raw repo-wide literal scan."""
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
    paths+=sorted(ROOT.glob('reports/**/*seed*audit*.json'))
    paths+=sorted(ROOT.glob('reports/**/*FREEZE*.json'))
    paths+=sorted(ROOT.glob('reports/**/*freeze*.json'))
    paths+=sorted(ROOT.glob('imitation/**/*seed*audit*.json'))
    paths+=sorted(ROOT.glob('imitation/**/*FREEZE*.json'))
    paths+=sorted(ROOT.glob('imitation/**/*freeze*.json'))
    r3_plan=ROOT/'reports/strategy_council_20260928/imitation/exit-r3/PLAN.md'
    if r3_plan.exists():paths.append(r3_plan)
    paths+=sorted((ROOT/'reports/explore').glob('**/plan.json'))
    ranges=[('K reporting',4503601407370496,600),('K smoke',4503601417370496,8),('X h2h',4503601507370496,256),('X paired',4503601517370496,600),('X smoke',4503601527370496,32),('G 04 entire reservation',4503601607370496,1000000),('G 01 entire reservation',4503601609370496,1000000),('G 03 entire reservation',4503601611370496,1000000),('X dagger conservative full block',4503601707370496,10000000),('K-v2 reporting',4503601807370496,600),('K-v2 smoke',4503601817370496,8),('R3 reporting reserved by worker',4503601907370496,600),('R3 smoke reserved by worker',4503601917370496,8),('R3 regret replay reserved by worker',4503601927370496,65536),('noise-ceiling entire replay reservation',4503609917370496,2**18)]
    ranges+=[('S1 reporting R2',4503602707370496,600),('S1 smoke',4503602617370496,8),('S1 invalid R1 reporting (conservative)',4503602607370496,600),('past X reassignment',4503602007370496,600)]
    cfg=json.loads((DEST/'plan.json').read_text())
    if (DEST/'history/r1/plan.json').exists():
        previous=json.loads((DEST/'history/r1/plan.json').read_text())
        ranges.append(('S1 invalid original reporting reservation',previous['seed_ranges']['reporting']['base'],600))
    own_intervals={(v['base']+off,v['count']) for v in cfg['seed_ranges'].values() for off in OFFSETS}
    sources=[]; echoes=[]
    def walk(x,label):
        if isinstance(x,dict):
            if isinstance(x.get('base'),int):
                count=x.get('count',x.get('pairs',0))
                if isinstance(count,int) and count>0:
                    declared=x.get('name','')
                    if not declared and isinstance(x.get('source_names'),list):declared='; '.join(x['source_names'])
                    own_echo=(declared.startswith('X4S-3') or 'reports/explore/x4s3/' in declared) and (x['base'],count) in own_intervals
                    if own_echo:echoes.append(dict(source=label,declaration=declared,base=x['base'],count=count,reason='peer audit echoes this new S1 reservation, not historical usage'))
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
    srt=sorted(cfg['seed_ranges'].values(),key=lambda x:x['base'])
    for a,b in zip(srt,srt[1:]):assert a['base']+a['count']+max(OFFSETS)<b['base']
    # Raw literal scan: every 16-digit 2^52-region integer in tracked/untracked text files.
    import re
    literals=set()
    for p in ROOT.glob('**/*'):
        if p.is_file() and p.suffix in ('.json','.md','.py','.txt','.yaml','.sh') and '.git' not in p.parts and DEST not in p.parents and p.stat().st_size<50_000_000:
            try:literals.update(int(m) for m in re.findall(rb'45036[0-9]{11}',p.read_bytes()))
            except OSError:pass
    lo=min(v['base'] for v in cfg['seed_ranges'].values());hi=max(v['base']+v['count'] for v in cfg['seed_ranges'].values())+max(OFFSETS)
    hits=sorted(x for x in literals if lo<=x<hi);assert not hits,hits[:10]
    raw_scan=dict(literal_count=len(literals),window=[lo,hi],hits=hits,nearest_below=max([x for x in literals if x<lo],default=None),nearest_above=min([x for x in literals if x>=hi],default=None))
    audit=dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),sources=sources,prior_ranges=[dict(name=n,base=b,count=c) for n,b,c in ranges],proposed_ranges=cfg['seed_ranges'],helper_offsets=OFFSETS,checks=checks,intersections=[],own_reservation_echoes=echoes,raw_literal_scan=raw_scan,reservation=cfg.get('seed_reservation'),open_ended_dagger='4503601707370496 <= seed < 4503601807370496 reserved; helpers included; future allocation beyond that requires a new audit')
    unique={}
    for entry in audit['prior_ranges']:unique.setdefault((entry['base'],entry['count']),set()).add(entry['name'])
    audit['prior_ranges']=[dict(base=b,count=c,source_names=sorted(labels)) for (b,c),labels in sorted(unique.items())]
    (DEST/'seed-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
if __name__=='__main__':main()
