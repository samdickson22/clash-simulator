import json,gzip,sys
sys.path.insert(0,'/tmp/dsweep'); from compare import match,scalar_bodies
SP={'IceSpirits','ElectroSpirit','FireSpirit','HealSpirit'}
_nc={}
def ncache(v,rj):
    k=(v,rj)
    if k not in _nc: _nc[k]={int(t):x for t,x in json.load(gzip.open(f'/tmp/dsweep/ncache/v{v}-{rj:05d}.json.gz')).items()}
    return _nc[k]
def first_exact(tag,v,sj,rj):
    N=ncache(v,rj)
    D={j['tick']:j for j in map(json.loads,gzip.open(f'/tmp/dsweep/runs/{tag}/v{v}-{sj:05d}/ticks.jsonl.gz'))}
    ok=0
    for t in sorted(N):
        if t not in D: continue
        pairs,uS,uN=match(scalar_bodies(D[t]),N[t]['bodies']); uS=[s for s in uS if s['n'] not in SP]
        bad=[(s['n'],s['id']) for s,n in pairs if round(s['x']*1000)!=round(n['x']*1000) or round(s['y']*1000)!=round(n['y']*1000) or round(s['hp'])!=round(n['hp'])]
        if bad or uS or uN: return t,ok,(bad[:2],[s['n'] for s in uS],[n['n'] for n in uN])
        ok+=1
    return None,ok,None
if __name__=='__main__':
    tag=sys.argv[1]; v,sj=int(sys.argv[2]),int(sys.argv[3])
    idx={p['sj']:p for p in json.load(open('/tmp/dsweep/index.json'))[str(v)]}
    print(first_exact(tag,v,sj,idx[sj]['rj']))
