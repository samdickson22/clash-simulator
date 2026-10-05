import json,glob,sys,os,gzip
sys.path.insert(0,'/tmp/dsweep'); from exact import first_exact
"""cmp3.py VARIANT BASE joblist [--list]: exact-unit toward/away classification of changed branches."""
a,b,jl=sys.argv[1],sys.argv[2],sys.argv[3]
L=[tuple(map(int,l.split())) for l in open(jl) if l.strip()]
idx={(int(v),p['sj']):p for v,ps in json.load(open('/tmp/dsweep/index.json')).items() for p in ps}
cnt=dict(identical=0,toward=0,away=0,neutral=0,missing=0); out=[]; hpg=hpl=sg=sl=0; exg=exl=0
for v,sj in L:
    n='v%d-%05d'%(v,sj)
    fa=f'/tmp/dsweep/runs/{a}/{n}/summary.json'; fb=f'/tmp/dsweep/runs/{b}/{n}/summary.json'
    if not (os.path.exists(fa) and os.path.exists(fb)): cnt['missing']+=1; continue
    A=json.load(open(fa)); B=json.load(open(fb))
    da=gzip.open(f'/tmp/dsweep/runs/{a}/{n}/decisions.jsonl.gz').read(); db=gzip.open(f'/tmp/dsweep/runs/{b}/{n}/decisions.jsonl.gz').read()
    if da==db: cnt['identical']+=1; continue
    rj=idx[(v,sj)]['rj']
    ea=first_exact(a,v,sj,rj); eb=first_exact(b,v,sj,rj)
    xa=ea[0] or 10**6; xb=eb[0] or 10**6
    k='toward' if xa>xb else 'away' if xa<xb else 'neutral'
    cnt[k]+=1
    if A['hp_eq_native'] and not B['hp_eq_native']: hpg+=1
    if B['hp_eq_native'] and not A['hp_eq_native']: hpl+=1
    if A['score']==A['native'][0] and B['score']!=B['native'][0]: sg+=1
    if B['score']==B['native'][0] and A['score']!=A['native'][0]: sl+=1
    if ea[0] is None and eb[0] is not None: exg+=1
    if eb[0] is None and ea[0] is not None: exl+=1
    out.append((k,n,A['fam'],A['role'][:8],A['cond'],'exactdiv',eb[0],'->',ea[0],'hp',(B['own'],B['en']),'->',(A['own'],A['en']),'N',A['native'][1:],'gates',A.get('gates')))
print(f'{a} vs {b} [{jl}]: {cnt} frame-exact +{exg}/-{exl} hp_exact +{hpg}/-{hpl} score_eq +{sg}/-{sl}')
if '--list' in sys.argv:
    for o in sorted(out): print(' ',*o)
json.dump(out,open(f'/tmp/dsweep/cmp3_{a}_{b}_{os.path.basename(jl)}.json','w'))
