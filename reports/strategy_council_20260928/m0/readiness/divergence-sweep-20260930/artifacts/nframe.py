import json,gzip,glob,sys
CN={int(k):v for k,v in json.load(open('/tmp/dsweep/cardnames.json')).items()}
def frames(v,rj,ticks):
    f=glob.glob(f'/Users/sam/Desktop/code/clasher/reports/strategy_council_20260928/m0/readiness/tier-a-fresh-v{v}/branches-reference-*/job-{rj:05d}/decisions.jsonl.gz')
    f=[x for x in f if json.load(open(x.replace('decisions.jsonl.gz','claim.json')))] 
    out={}
    for x in f:
        if not glob.os.path.exists(x.replace('decisions.jsonl.gz','result.json')): continue
        for l in gzip.open(x):
            j=json.loads(l)
            if j['tick'] in ticks: out[j['tick']]=j
    return out
def show(fr,ids=None,rich=False):
    ro={o['nativeObjectId']:o for o in fr['native_frame']['rich']['objects']}
    for o in fr['native_frame']['ordinary']['objects']:
        if ids and o['nativeObjectId'] not in ids: continue
        r=ro.get(o['nativeObjectId'],{})
        n='TOWER' if o['cardId']==-1 else CN.get(o['cardId'],o['cardId'])
        tk=r.get('targetEntityKey'); pr=r.get('phaseRuntime') or {}
        p=r.get('projectile')
        s=f"  {o['nativeObjectId']} o{o['owner']} {n} ({o['x']},{o['y']}) prev({o['targetX']},{o['targetY']}) hp{o['hp']} tgt{tk[2] if tk else None} stage{r.get('attackSequenceStage')} tl{pr.get('attackTimelineMs')} load{pr.get('loadRemainingMs')} dep{pr.get('deployRemainingMs')}"
        if p: s+=f" PROJ src{(p.get('sourceEntityKey') or [0,0,None])[2]} tgt{(p.get('targetEntityKey') or [0,0,None])[2]}"
        if r.get('activeEffects'): s+=' fx'+str([(e['name'],e['remainingMs']) for e in r['activeEffects']])
        print(s)
        if rich: print(json.dumps(r)[:2500])
if __name__=='__main__':
    v,rj=int(sys.argv[1]),int(sys.argv[2]); ticks=[int(t) for t in sys.argv[3].split(',')]
    ids=set(int(i) for i in sys.argv[4].split(',')) if len(sys.argv)>4 and sys.argv[4] else None
    F=frames(v,rj,set(ticks))
    for t in ticks:
        print('tick',t,'actions',F[t]['actions']); show(F[t],ids,rich=len(sys.argv)>5)
