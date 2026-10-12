import json,hashlib,sys,collections
L='/mpac/sdicks02/k4s-runner/run-r1';phase=sys.argv[1]
last=json.load(open(L+'/health/last-check.json'));rec=json.load(open(last['out']))
hist=[e for e in json.load(open(L+'/rounds/history.json')) if e['phase']==phase];assert len(hist)==1
raw=open(L+'/dispatch/'+hist[0]['dispatch_file'],'rb').read();assert hashlib.sha256(raw).hexdigest()==hist[0]['dispatch_sha256']
exp=collections.Counter(b['host'] for b in json.loads(raw)['blocks'])
out=dict(schema='clasher.k4s.health-handcheck.v1',health_receipt=last['out'].split('/')[-1],health_sha256=hashlib.sha256(open(last['out'],'rb').read()).hexdigest(),
 health_utc=rec['utc'],phase=phase,dispatch_sha256=hist[0]['dispatch_sha256'],hosts={},note='recorded hand check (coordinator ruling on round r3 audit F1): completed vs dispatch per host + supervisor exit reason')
flag=[]
for h,x in rec['hosts'].items():
  y=x.get('remote',{});comp=int(y.get('COMPLETE','-1'));sx=y.get('SUPEXIT');sp=y.get('SUPPROC')
  reason=None if sx is None else sx.split(':',1)[-1].strip()
  st='running' if sx is None else ('exited reason '+reason)
  ok=(sx is None and comp<=exp[h]) or (reason=='null' and comp==exp[h])
  out['hosts'][h]=dict(expected=exp[h],complete=comp,supervisor_exit=sx,supervisor_proc=sp,state=st,ok=ok)
  if not ok:flag.append(f'{h}: {st} complete {comp}/{exp[h]}')
out['flags']=flag
p=last['out'].replace('.json','-handcheck.json');json.dump(out,open(p,'w'),indent=1)
print(p.split('/')[-1],{h:f"{v['complete']}/{v['expected']} {v['state']}" for h,v in out['hosts'].items()},'FLAGS',flag)
