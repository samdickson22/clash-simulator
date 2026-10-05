import gzip, json, sys, itertools, math
A="/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v6/"
CN={int(k):v for k,v in json.load(open('/tmp/dsweep/cardnames.json')).items()}
def native_bodies(frame):
    rich={o['nativeObjectId']:o for o in frame['rich']['objects']}
    out=[]
    for o in frame['ordinary']['objects']:
        if o['nativeObjectId']>=5000000 and o['hp'] is not None:
            n = 'TOWER' if o['cardId']==-1 else CN.get(o['cardId'],str(o['cardId']))
            r=rich.get(o['nativeObjectId'],{})
            tk=r.get('targetEntityKey')
            out.append(dict(id=o['nativeObjectId'],o=o['owner'],n=n,x=o['x']/1000,y=o['y']/1000,hp=o['hp'],t=tk[2] if tk else None))
    return out
def native_proj(frame):
    out=[]
    for o in frame['rich']['objects']:
        p=o.get('projectile')
        if p:
            out.append(dict(id=o['nativeObjectId'],o=o['owner'],n=CN.get(o['cardId'],o['cardId']),x=o['x']/1000,y=o['y']/1000,
               src=(p.get('sourceEntityKey') or [0,0,None])[2], tgt=(p.get('targetEntityKey') or [0,0,None])[2], dest=(p.get('destinationX'),p.get('destinationY'))))
    return out
TOWERN={'Tower','KingTower'}
def scalar_bodies(d):
    out=[]
    for e in d['ents']:
        if e['k'] in ('Troop','Building') and e['alive'] and e['hp']>0:
            n='TOWER' if e['n'] in TOWERN else e['n']
            out.append(dict(id=e['id'],o=e['o'],n=n,x=e['x'],y=e['y'],hp=e['hp'],t=e['t']))
    return out
def match(S,N):
    pairs=[];unS=[];unN=list(N)
    for s in sorted(S,key=lambda s:(s['o'],s['n'],s['x'],s['y'])):
        cands=[n for n in unN if n['o']==s['o'] and n['n']==s['n']]
        if not cands: unS.append(s); continue
        n=min(cands,key=lambda n:(n['x']-s['x'])**2+(n['y']-s['y'])**2)
        unN.remove(n); pairs.append((s,n))
    return pairs,unS,unN
