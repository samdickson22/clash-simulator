import copy,gzip,json,time,statistics
from study import OUT,PORT,TEMPLATE,request,dump
rows=[json.loads(l) for l in gzip.open(OUT/'sample50.jsonl.gz','rt')]
results=[]
for r in rows[:3]:
 raw=json.dumps(r['payload'],separators=(',',':'))
 if len(raw)>=65536:results.append({'index':r['index'],'bytes':len(raw),'result':'not sent: exceeds 64KiB command limit'});continue
 try:x=request(PORT,'configure '+raw)
 except Exception as e:x={'error':str(e)}
 results.append({'index':r['index'],'bytes':len(raw),'result':x})
c=copy.deepcopy(json.load(open(TEMPLATE))['config']);c['cmd']=[{'t':1}]
try:x=request(PORT,'configure '+json.dumps(c,separators=(',',':')))
except Exception as e:x={'error':str(e)}
results.append({'case':'native template with nonempty command stream','result':x})
c=copy.deepcopy(json.load(open(TEMPLATE))['config']);request(PORT,'configure '+json.dumps(c,separators=(',',':')))
for cmd in ['observe-rich-since 0 0 0 0 0 0 0','observe-atomic-levels','observe-atomic']:
 try:
  t=time.perf_counter();v=request(PORT,cmd);x={'keys':list(v),'seconds':time.perf_counter()-t}
 except Exception as e:x={'error':str(e)}
 results.append({'command':cmd,'result':x})
for val in [1,9]:
 c=copy.deepcopy(json.load(open(TEMPLATE))['config']);c['battle']['lvlcap']=0;c['battle']['cardlvlmin']=0
 for owner in [0,1]:
  for card in c['battle'][f'deck{owner}']['sp']:card['l']=val
 request(PORT,'configure '+json.dumps(c,separators=(',',':')));f=request(PORT,'observe')
 pl=f['players'][0];card=next(v for v in pl['hand'] if v['cardId']//1000000==26)
 ack=request(PORT,f"replay-schedule-card 0 {card['cardId']} 3500 10500 20")
 request(PORT,'step 45');after=request(PORT,'observe');s=request(PORT,f"replay-schedule-status {ack['sequence']}")
 results.append({'case':'per-card l experiment, no level clamp','l':val,'card':card,'initial_towers':f['objects'],'spawned':[o for o in after['objects'] if o['nativeObjectId']>=5000006],'receipt':s})
dump('diagnostics.json',results)
print(json.dumps(results,indent=2))
