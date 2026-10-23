import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
sys.dont_write_bytecode=True
import hashlib
from pathlib import Path
R64_GATE_BYTES=(Path(__file__).resolve().parent/'gate.py').read_bytes()
if hashlib.sha256(R64_GATE_BYTES).hexdigest()!='70cc719588df2cf3be9ea7de0b972d84ef8a2bb90be8350020e44314d503564e':raise RuntimeError('R64 gate pin mismatch')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
R64_DISK('monitor.py',__file__)
_,FILES=R64_CHECK(R64_CONTEXT,(Path(__file__).resolve().parent/'payload.b64').read_text())
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import os,sys,json,time,subprocess,signal
from pathlib import Path
import types
C=types.ModuleType('common');C.__file__=str(Path(__file__).resolve().parent/'common.py');exec(compile(FILES['common.py'],C.__file__,'exec'),C.__dict__)
m=C.load_r37();OUT=Path(sys.argv[1]);owner=int(sys.argv[2]);owner_start=int(sys.argv[3]);TOK=('R40_PROBE_TOKEN='+sys.argv[4]).encode();began=time.monotonic()
LEASE=('CLASHER_LEASE_JOB='+os.environ['CLASHER_LEASE_JOB']).encode()
def expired(*_):raise C.Deadline('monitor signalled')
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,expired)
C.deadline(560);TERMINAL=C.LIMITS[0]
trace=(OUT/'physical.jsonl').open('x',buffering=1);seen=False;last=None;peak=0;minimum=None;samples=0;failure=None;identity=None;device=None
first_identity=None;errors=0;query_failures=0;max_gap=0;final=None;end_reason=None;tracked=set();unverified_cleanup=False
unverified_drain=False
lifetime=C.ProbeLifetime(m,TOK,LEASE)
def log(kind,obj):trace.write(json.dumps({kind:obj},sort_keys=True)+'\n');trace.flush()
def latch(stage,ex,rec):
 global failure,errors
 msg='%s: %r'%(stage,ex);errors+=1;rec['errors'].append(msg)
 if failure is None:
  failure=msg
  try:C.write(OUT/'monitor-failed.json',dict(error=msg,utc=C.utc(),monotonic=time.monotonic()))
  except BaseException as e:rec['errors'].append('failure marker: %r'%e)
def query(args):
 global query_failures
 q=dict(utc=C.utc(),wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),argv=args)
 try:
  p=subprocess.run(['nvidia-smi']+args,capture_output=True,text=True,timeout=2)
  q.update(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,finished_ns=time.time_ns())
 except BaseException as ex:
  query_failures+=1;q.update(error=repr(ex),finished_ns=time.time_ns());log('query_failure',q);raise
 log('query',q)
 if q['returncode']!=0 or q['stderr'].strip():query_failures+=1;raise AssertionError('query failed',q['returncode'],q['stderr'])
 return [s.strip() for s in q['stdout'].strip().splitlines() if s.strip()]
def attribute(pid,row):lifetime.attribute(pid,identity,row)
def gone(p,s):
 st=m.proc_stat(p);return st is None or st[4]!=s
def probe_tree():
 """Probe-owned tree each sample: probe token, probe session/root and their descendants, plus every exact identity
 seen earlier (tree or owned GPU row) that has not exited and been reaped. Excludes this monitor and its queries."""
 me=os.getpid();procs=m.job_scan(m.host());have={}
 for p,x in procs.items():
  if p==me or x['ppid']==me:continue
  if b'\0'+TOK+b'\0' in b'\0'+x['env']+b'\0' or identity is not None and x['sid']==identity['sid'] and x['start']>=identity['start']:have[p]=x['start']
 grow=True
 while grow:
  grow=False
  for p,x in procs.items():
   if p not in have and p!=me and x['ppid'] in have and x['start']>=have[x['ppid']]:have[p]=x['start'];grow=True
 if identity is not None:tracked.add((identity['pid'],identity['start']))
 tracked.update(have.items())
 for p,s in tracked:
  if p not in have and not gone(p,s):have[p]=s
 return have
def step(stage,rec,fn):
 try:return fn()
 except C.Deadline:raise
 except BaseException as ex:latch(stage,ex,rec)
try:
 next_sample=time.monotonic()
 while True:
  now=time.monotonic();rec=dict(utc=C.utc(),wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),errors=[],gap_seconds=None if last is None else now-last)
  done=step('cleanup marker',rec,lambda:json.loads((OUT/'cleanup-finished.json').read_bytes()) if (OUT/'cleanup-finished.json').exists() else None)
  drained=step('drain marker',rec,lambda:json.loads((OUT/'controller-drained.json').read_bytes()) if (OUT/'controller-drained.json').exists() else None)
  if last is not None:
   max_gap=max(max_gap,now-last)
   if now-last>3:latch('cadence',AssertionError('monitor gap %.3fs exceeded 3s'%(now-last)),rec)
  last=now
  owner_live=m.job_alive(m.host(),owner,owner_start)
  if not owner_live:latch('owner',AssertionError('timeout owner disappeared'),rec)
  step('lease',rec,C.lease_check)
  def admit():
   with C.bounded(5):return C.admission(m)
  rec['resources']=step('admission',rec,admit)
  if (OUT/'probe-identity.json').exists() and identity is None:
   identity=step('identity',rec,lambda:json.loads((OUT/'probe-identity.json').read_bytes()));first_identity=now
  def pre_query_drain():
   ids=drained.get('identities',[])+drained.get('live',[])+drained.get('unreaped',[])
   return all(gone(*x) for x in ids) and probe_tree()=={}
  drain_clear_before_queries=step('pre-query drain proof',rec,pre_query_drain) is True if drained is not None else False
  dev=step('device query',rec,lambda:query(['--query-gpu=uuid,driver_version,memory.total,memory.free,memory.used','--format=csv,noheader,nounits']))
  free=used=uuid=None
  def parse_device():
   global device,minimum
   assert len(dev)==1,'ambiguous device'
   d=[x.strip() for x in dev[0].split(',')];assert len(d)==5
   u,driver=d[:2];total,f,us=map(int,d[2:])
   if device is None:
    assert samples==0,'device unreadable on entry sample'
    assert f>=44544,'entry free less than 43.5 GiB'
    device={'uuid':u,'driver':driver,'total_mib':total}
   assert device=={'uuid':u,'driver':driver,'total_mib':total},'device identity changed'
   minimum=f if minimum is None else min(minimum,f)
   assert total>=44544 and f>=8192,'physical free below 8 GiB'
   return u,f,us
  if dev is not None:uuid,free,used=step('device',rec,parse_device) or (None,None,None)
  rows=step('process query',rec,lambda:query(['--query-compute-apps=gpu_uuid,pid,used_gpu_memory','--format=csv,noheader,nounits']))
  apps=[];owned_rows=[]
  for row in rows or []:
   def one():
    a=[x.strip() for x in row.split(',')];assert len(a)==3,'bad compute row'
    assert device is not None and a[0]==device['uuid'],'GPU row UUID mismatch'
    x=dict(uuid=a[0],pid=int(a[1]),used_mib=int(a[2]));apps.append(x);attribute(x['pid'],x)
    return x
   step('attribution',rec,one)
  if len({a['pid'] for a in apps})!=len(apps):latch('attribution',AssertionError('duplicate process attribution'),rec)
  def bind():
   global seen,peak
   ps=m.proc_stat(identity['pid']);live=ps is not None and ps[0] not in 'ZX'
   if live:assert ps[4]==identity['start'] and ps[2]==identity['sid'],'probe identity changed'
   matching=[a for a in apps if a['pid']==identity['pid']]
   if matching:
    assert len(matching)==1 and matching[0].get('attributed') is True and matching[0].get('start')==identity['start'] and matching[0]['uuid']==device['uuid'],'unbound probe GPU row'
    seen=True;peak=max(peak,matching[0]['used_mib'])
   elif live and seen:raise AssertionError('live probe GPU attribution missing')
   elif live:assert now-first_identity<45,'GPU attribution never appeared within 45s'
   return live
  rec['probe_live']=step('probe binding',rec,bind) if identity is not None else None
  for a in apps:
   ours=a.get('probe_token') or a.get('lease_token') or identity is not None and a.get('sid')==identity['sid']
   exact=identity is not None and a['pid']==identity['pid'] and a.get('start')==identity['start']
   if ours:owned_rows.append(a)
   if not exact:latch('attribution',AssertionError('unexpected CUDA process outside exact probe %r'%a),rec)
  tracked.update((a['pid'],a['start']) for a in owned_rows if 'start' in a)
  tree=step('probe tree',rec,probe_tree)
  clean=tree=={} and not owned_rows
  waiting=not owner_live or done is not None and not (done.get('reaped') is True and clean)
  if waiting and done is not None and not unverified_cleanup:
   unverified_cleanup=True;latch('cleanup',AssertionError('cleanup marker without verified reap and empty probe tree'),rec)
  pending=None
  if waiting and drained is not None:
   if drained.get('verified') is not True and not unverified_drain:
    unverified_drain=True;latch('drain',AssertionError('controller drain not verified %r'%drained),rec)
   pending=['identity %r live or unreaped'%x for x in drained.get('identities',[])+drained.get('live',[])+drained.get('unreaped',[]) if not gone(*x)]
   if tree is None or tree:pending.append('probe tree %r'%tree)
   if owned_rows:pending.append('owned GPU rows')
   if uuid is None or free is None or used is None:pending.append('device sample unavailable')
  rec.update(device=device,free_mib=free,used_mib=used,gpu_uuid=uuid,processes=apps,owned_rows=owned_rows,probe=identity,cleanup=done,probe_tree=None if tree is None else sorted(tree.items()),drain=drained,drain_pending=pending,drain_clear_before_queries=drain_clear_before_queries,observation_finished_monotonic_ns=time.monotonic_ns())
  samples+=1;log('sample',rec)
  hb=OUT/'heartbeat.tmp';hb.write_text(str(time.monotonic()));os.replace(str(hb),str(OUT/'heartbeat'))
  if not (OUT/'monitor-ready.json').exists():C.write(OUT/'monitor-ready.json',dict(pid=os.getpid(),start=m.proc_stat(os.getpid())[4],boot=m.boot_id(),owner=owner,owner_start=owner_start,deadline_monotonic=TERMINAL,device=device,utc=C.utc()))
  if done is not None and not waiting:
   def verify():
    assert done.get('reaped') is True,'owner cleanup did not verify reap'
    if identity is not None:
     assert not m.job_alive(m.host(),identity['pid'],identity['start']),'probe live after cleanup'
     end=json.loads((OUT/'probe-reaped.json').read_bytes());assert end['pid']==identity['pid'] and end['start']==identity['start']
     assert seen,'no attributed CUDA sample'
    else:raise AssertionError('probe identity never published')
    assert uuid is not None and free is not None and used is not None,'final device sample unavailable'
    assert not owned_rows and not rec['errors'],'final sample has owned GPU rows or errors'
   step('final',rec,verify)
   final=dict(utc=rec['utc'],gpu_uuid=uuid,free_mib=free,used_mib=used,owned_gpu_rows=owned_rows,processes=apps,errors=rec['errors'],free_returned_to_43_5_gib=free is not None and free>=44544)
   end_reason='cleanup finished';break
  if waiting and drained is not None and not pending and drain_clear_before_queries:
   final=dict(utc=rec['utc'],gpu_uuid=uuid,free_mib=free,used_mib=used,owned_gpu_rows=owned_rows,processes=apps,errors=rec['errors'],free_returned_to_43_5_gib=free is not None and free>=44544,drain=drained)
   end_reason='controller drain verified' if drained.get('verified') is True else 'controller drain unverified; exit and reap observed';break
  next_sample=max(next_sample+1,time.monotonic());time.sleep(max(0,next_sample-time.monotonic()))
except BaseException as ex:
 failure=(failure+'; ' if failure else '')+'terminal: '+repr(ex);end_reason=repr(ex)
finally:
 lifetime.close()
 signal.setitimer(signal.ITIMER_REAL,0)
 if final is None and failure is None:failure='no final through-reap sample'
 log('end',dict(utc=C.utc(),failure=failure,reason=end_reason));os.fsync(trace.fileno());trace.close()
 C.write(OUT/'monitor-result.json',dict(identity_protocol=C.MONITOR_IDENTITY_PROTOCOL,status='failed' if failure else 'pass',error=failure,errors=errors,query_failures=query_failures,samples=samples,max_gap_seconds=max_gap,attributed_cuda_sample=seen,peak_process_mib=peak,minimum_device_free_mib=minimum,device=device,probe=identity,final_sample=final,end_reason=end_reason,nominal_interval_seconds=1,highwater_bound=False,utc=C.utc()))
if failure:sys.exit(1)
