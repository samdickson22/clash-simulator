import json,gzip,sys
CN={int(k):v for k,v in json.load(open('/tmp/dsweep/cardnames.json')).items()}
p=sys.argv[1]; lo,hi=map(int,sys.argv[2].split('-')); ids=set(int(i) for i in sys.argv[3].split(',')) if len(sys.argv)>3 and sys.argv[3] else None
full=len(sys.argv)>4
for l in gzip.open(p):
    j=json.loads(l)
    if not lo<=j['tick']<=hi: continue
    ro={o['nativeObjectId']:o for o in j.get('rich',{}).get('objects',[])}
    for o in j['ordinary']['objects']:
        if ids and o['nativeObjectId'] not in ids: continue
        r=ro.get(o['nativeObjectId'],{}); tk=r.get('targetEntityKey'); pr=r.get('phaseRuntime') or {}
        n='TOWER' if o['cardId']==-1 else CN.get(o['cardId'],o['cardId'])
        print(j['tick'],o['nativeObjectId'],n,(o['x'],o['y']),'d',(o['x']-o['targetX'],o['y']-o['targetY']),'hp',o['hp'],'tgt',tk[2] if tk else None,'tl',pr.get('attackTimelineMs'),'load',pr.get('loadRemainingMs'),'dep',pr.get('deployRemainingMs'),'mv',pr.get('movementDelta'))
        if full: print('   ',json.dumps({k:v for k,v in r.items() if k not in ('components',)})[:3000])
