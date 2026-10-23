import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='70cc719588df2cf3be9ea7de0b972d84ef8a2bb90be8350020e44314d503564e':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import os,sys,json,hashlib,importlib.util,subprocess,base64,time,signal,types,ctypes
from pathlib import Path
os.setpriority(os.PRIO_PROCESS,0,15)
STAGE=R64_BOOT('stage.py',CTX,PAYLOAD)
ADMIT=R64_BOOT('admission.py',CTX,PAYLOAD)
R37='/mpac/sdicks02/repos/clasher-pv1-lease-1316-995579193e/lease_supervisor.py'
R37_SHA='cf162c7a8d1beddd46bfed5b226ebe91ec4138af451f33a30ac950195bb61872'
# PAYLOAD and STAGE are injected as constants from locally frozen reviewed bytes. The frozen common.py supplies the
# deadline/bounded helpers before staging; staged bytes are verified against the same pins afterwards.
C=types.ModuleType('common');exec(compile(base64.b64decode(json.loads(__import__('zlib').decompress(base64.b64decode(PAYLOAD)))['files']['common.py']),'payload:common.py','exec'),C.__dict__)
CODES={'preflight':10,'stage':11,'prelaunch':12,'gpu':13,'attempt-failed':14,'finalize':15}
phase='preflight';failures=[];admitted={};outs={};observers={};reaped=[];final=None;measured=None;h=size=pid=start=None
base=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r87-fix-20261023/r')
def emit(**kw):print(json.dumps(kw,sort_keys=True),flush=True)
def fail(where,ex):failures.append(dict(phase=where,error=repr(ex),utc=C.utc()));emit(event='failure',phase=where,error=repr(ex))
def admit(name,workers,pss_gb,gpu,command):
 request=json.dumps(dict(name=name,workers=workers,pss_gb=pss_gb,gpu_gb=gpu,grace=120,cwd=m.STATE_ROOT,cmd=command));assert len(request.encode())<=126000,'packed admission argument cap'
 args=['/bin/python3','-B','-c',ADMIT,request]
 admitted[name]=None   # the name is tracked even if the admit CLI times out after spawning
 with C.bounded(30):p=subprocess.run(args,capture_output=True,text=True,timeout=28)
 emit(event='admission',name=name,exit=p.returncode,stdout=p.stdout,stderr=p.stderr)
 assert p.returncode==0,p.stderr
 admitted[name]=json.loads(p.stdout);return admitted[name]
def reap_own():
 """Reap this controller's zombie children. As a subreaper its only children are its own subprocesses and admitted
 roots/descendants orphaned to it, so this never waits on a foreign process."""
 me=os.getpid()
 for n in os.listdir('/proc'):
  if n.isdigit():
   st=m.proc_stat(int(n))
   if st and st[0]=='Z' and st[1]==me:
    try:got,status=os.waitpid(int(n),os.WNOHANG)
    except ChildProcessError:continue
    if got:reaped.append([got,st[4],status])
def handshake(out,owner=None):
 # Observer's pre-probe handshake: exact identity and absolute monotonic terminal; strict before probe release.
 d=json.loads((out/'monitor-ready.json').read_bytes());t=time.monotonic()
 assert d['boot']==m.boot_id() and d['deadline_monotonic']<=t+560,'observer handshake %r'%d
 if owner:x=m.proc_stat(d['pid']);assert x and [x[4],x[1],d['owner'],d['owner_start']]==[d['start'],owner['pid'],owner['pid'],owner['start']] and t<d['deadline_monotonic'],'observer handshake %r'%d
 return d
def drain(name):
 """Finite exact drain of this controller's own admitted job name only, using R37's record identities for that name.
 All non-observer stops (owner's own cleanup, probe-token, other owned) run and are verified while the observer
 samples; then the marker. The observer and its queries are selected only after its exit or retained absolute
 terminal, and alone. No workload signal follows; survivors fail. No other job is ever signalled."""
 sent=[];seen=set();out=outs.get(name);mon=None;obs=set();hs=observers.get(name);herr=None;terminal=None
 if hs is None and out is not None and (out/'monitor-ready.json').exists():
  try:hs=handshake(out)
  except Exception as ex:herr=repr(ex)
 if hs:mon=(hs['pid'],hs['start']);terminal=hs['deadline_monotonic']
 observer=lambda r,p,x:mon is not None and ((p,x['start'])==mon or (p,x['start']) in obs or x['ppid']==mon[0] and x['start']>=mon[1])
 other=lambda r,p,x:not observer(r,p,x)
 def look():
  recs=st.records();r=recs.get(name)
  if r:seen.update((p,s) for p,s in [[r.get('pid'),r.get('start')]]+r.get('procs',[]) if p)   # persisted identities
  j=(m.job_discover(m.host(),recs,m.job_scan(m.host()),m.boot_id()).get(name) or {}) if r else {}
  seen.update((p,x['start']) for p,x in j.items());obs.update((p,x['start']) for p,x in j.items() if observer(r,p,x));return r,j
 def stop(select,sig,span):
  r,j=look()
  for p,x in j.items():
   if select(r,p,x) and m.job_signal(m.host(),p,x['start'],sig):sent.append([name,p,x['start'],int(sig)])
  end=time.monotonic()+span
  while time.monotonic()<end:
   reap_own();r,j=look()
   if not any(select(r,p,x) for p,x in j.items()):break
   time.sleep(.5)
 def exited(ids):
  # Exact identity has exited and been reaped: no /proc entry with that start, not even a zombie.
  return [list(x) for x in sorted(ids) if (lambda q:q is not None and q[4]==x[1])(m.proc_stat(x[0]))]
 r,j=look();before=sorted([p,x['start']] for p,x in j.items())
 if j:
  root=lambda r,p,x:(p,x['start'])==(r['pid'],r['start'])
  probe=lambda r,p,x:other(r,p,x) and b'\0R40_PROBE_TOKEN=' in b'\0'+x.get('env',b'')
  if any(root(r,p,x) for p,x in j.items()):stop(root,signal.SIGTERM,75)   # owner runs its own 60s exact cleanup
  for sig in (signal.SIGTERM,signal.SIGKILL):stop(probe,sig,5)
  for sig in (signal.SIGTERM,signal.SIGKILL):stop(other,sig,5)
 end=time.monotonic()+10
 while True:
  reap_own();r,j=look()
  ids={x for x in seen if x!=mon and x not in obs}   # the monitor and its own query children are drained last
  live=[[p,x['start']] for p,x in j.items() if other(r,p,x)];pending=exited(ids)
  if not live and not pending or time.monotonic()>end:break
  time.sleep(.25)
 marker=dict(verified=not live and not pending,identities=sorted(list(x) for x in ids),live=live,unreaped=pending,observer=mon,observer_terminal=terminal,handshake_error=herr,reaped=list(reaped),utc=C.utc())
 try:
  if out is not None and out.exists():C.write(out/'controller-drained.json',marker)
 except Exception as ex:marker['write_error']=repr(ex)   # the observer still runs to its proof or terminal
 # Late exits are reaped here so the observer can see them; it ends at its own final sample or its absolute terminal.
 while mon is not None and m.job_alive(m.host(),*mon) and time.monotonic()<terminal:reap_own();time.sleep(.25)
 end=time.monotonic()+3
 while mon is not None and m.job_alive(m.host(),*mon) and time.monotonic()<end:reap_own();time.sleep(.25)   # its own terminal exit
 for sig in (signal.SIGTERM,signal.SIGKILL):stop(observer,sig,3)
 end=time.monotonic()+5
 while True:
  reap_own();r,j=look();unreaped=exited(seen)
  if not j and not unreaped or time.monotonic()>end:break
  time.sleep(.25)
 left=sorted([p,x['start']] for p,x in j.items())
 return dict(gone=not left and not unreaped,before=before,signals=sent,left=left,left_alive=[x for x in left if m.job_alive(m.host(),*x)],unreaped=unreaped,drain_marker=marker,observer=mon,observer_terminal=terminal,observer_exit=[x for x in reaped if mon and tuple(x[:2])==mon],observer_terminal_reached=terminal is not None and time.monotonic()>=terminal,state=r and r.get('state'))
C.deadline(960)   # whole controller before finalization; with 600s finalization this stays inside local SSH 1600s
try:
 assert hashlib.sha256(Path(R37).read_bytes()).hexdigest()==R37_SHA
 m=C.load_r37(CTX)
 # Subreaper before any admission: admitted roots and their orphans re-parent here, so their exit is reaped and verified.
 assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'subreaper unavailable'
 assert os.sched_getaffinity(0)<=set(range(32))
 assert m.under(os.readlink('/proc/self/cwd'),m.ALLOWED_ROOTS),'controller cwd not R37-classified clasher'
 # Exact launcher identities, bound into every admitted child's environment and charged on every admission check.
 wrappers=C.wrapper_chain(m);os.environ['R40_WRAPPERS']=json.dumps(wrappers)
 h=m.host();assert h=='127x14';size='M';pid,start,boot=C.WATCH[h]
 assert m.boot_id()==boot and m.job_alive(m.host(),pid,start)
 cmd=Path('/proc/%d/cmdline'%pid).read_bytes();assert R37.encode() in cmd and b'supervise' in cmd
 st=C.state(m)
 assert st.supervisor_live() and not Path(st.halt).exists() and not Path(st.release).exists()
 lease,deadline,cap,pss=m.load_lease(m.LEASE_DIR+'/'+h+'.json',h);assert m.lease_ending(lease) is None and deadline-time.time()>2420
 recs=st.records();assert not any(r['state'] in ('uncertain','intent','stopping') for r in recs.values())
 procs=m.job_scan(m.host());jobs=m.job_discover(m.host(),recs,procs,boot);assert not any(v and C.gpu_contract(recs[n])>0 for n,v in jobs.items()),'existing GPU job: defer without displacement'
 sample=m.job_sample(m.host(),recs,procs,jobs);assert cap<=32 and pss<=32 and deadline<=m.parse_utc('2026-10-25T07:53:00Z')
 assert sample['mem']>=36*m.GIB and sample['load']<=90 and sample['pss']+4*m.GIB<=pss*m.GIB and sample['procs']+16<=cap
 assert not base.exists()
 # Readiness is a separate CPU-admitted immutable transfer. Measurement dispatch never installs or reuses another environment.
 assert C.READY.is_dir(),'separate reviewed CPU environment transfer not complete'
 # A temporary in-memory BASE binding permits verification before measurement staging writes.
 plan=json.loads(FILES['ready-plan.json']);assert C.sha(C.READY/'cpu-stage-inventory.json')==plan['inventory_sha256']
 originalbase=C.BASE
 try:C.BASE=C.READY;C.verify_ready(plan)
 finally:C.BASE=originalbase
 assert not Path('/mpac/sdicks02/repos/clasher-M-host14-source-20261023').exists()
 emit(event='preflight',host=h,sample=sample,watcher=C.WATCH[h],wrappers=wrappers)
 phase='stage'
 with C.bounded(8):pre=C.admission(m,workers=6,pss_gb=2)
 emit(event='stage_admission_check',admission=pre)
 stage_admit=admit('M-host14-stage-20261023',6,2,0,['/bin/python3','-B','-c',STAGE])
 end=time.monotonic()+200
 while not (base/'stage-receipt.json').exists():
  assert time.monotonic()<end,'CPU staging timeout'
  assert m.job_alive(m.host(),stage_admit['pid'],stage_admit['start']),'CPU staging failed without receipt'
  time.sleep(.25)
 end=time.monotonic()+10
 while m.job_alive(m.host(),stage_admit['pid'],stage_admit['start']):assert time.monotonic()<end,'CPU staging root did not exit';time.sleep(.1)
 reap_own()
 phase='prelaunch'
 assert hashlib.sha256((base/'common.py').read_bytes()).hexdigest()==hashlib.sha256(base64.b64decode(json.loads(__import__('zlib').decompress(base64.b64decode(PAYLOAD)))['files']['common.py'])).hexdigest()
 pins=C.verify_inputs(size)
 with C.bounded(8):fresh=C.admission(m,workers=12,pss_gb=4)
 assert not fresh['jobs'].get('M-host14-stage-20261023'),'staging tree still alive'
 C.write(base/'prelaunch.json',dict(pins=pins,admission=fresh,wrappers=wrappers,controller_pid=os.getpid(),controller_start=m.proc_stat(os.getpid())[4],utc=C.utc()))
 # Positive GPU reservation avoids R37's CPU-only CUDA mask. The one-second guard enforces physical 8GiB headroom.
 phase='gpu'
 out=base/(h+'-'+size+'-attempt1');g='M-host14-measure-20261023-once';outs[g]=out
 gpu_admit=admit(g,12,4,38,['/bin/python3','-B',str(base/'run.py'),size])
 announced=False;end=time.monotonic()+600
 while not (out/'exit-receipt.json').exists():
  assert time.monotonic()<end,'probe owner failed to publish finite receipt'
  if g not in observers and (out/'monitor-ready.json').exists():
   # Retained and acknowledged before run.py creates any probe.
   observers[g]=handshake(out,gpu_admit);C.write(out/'controller-observer.json',dict(observer=observers[g],controller=os.getpid(),utc=C.utc()));emit(event='observer_retained',observer=observers[g])
  if (out/'attempt-receipt.json').exists() and not announced:
   emit(event='probe_started',host=h,receipt=json.loads((out/'attempt-receipt.json').read_bytes()),path=str(out/'attempt-receipt.json'));announced=True
  if not m.job_alive(m.host(),gpu_admit['pid'],gpu_admit['start']):
   time.sleep(.5);assert (out/'exit-receipt.json').exists(),'probe owner exited without receipt'
  time.sleep(.25)
 end=time.monotonic()+10
 while m.job_alive(m.host(),gpu_admit['pid'],gpu_admit['start']):assert time.monotonic()<end,'probe owner did not exit after receipt';time.sleep(.1)
 reap_own()
 final=json.loads((out/'exit-receipt.json').read_bytes())
 measured=json.loads((out/'monitor-result.json').read_bytes())
 phase='attempt-failed'
 assert final['status']=='pass' and final['probe_reaped'] is True and final['probe_exit']==0 and final['monitor_exit']==0,'attempt exit receipt failed'
 assert measured['status']=='pass','monitor result failed'
 phase=None
except BaseException as ex:fail(phase or 'attempt-failed',ex)
# Bounded finalization on every path: drain proof, R37 logs, raw artifacts, final physical, unchanged watcher.
# 600s: the observer's absolute terminal (<=560s on), its stop/reap and final verify 14s, GPU queries 10s, artifacts 15s.
C.deadline(600)
report=dict(event='final',host=h,size=size,payload_sha256=hashlib.sha256(PAYLOAD.encode()).hexdigest(),stage_sha256=hashlib.sha256(STAGE.encode()).hexdigest(),r37_sha256=R37_SHA,archive_sha256=C.ARCHIVE_SHA,aggregate_sha256=C.AGG,script_sha256=C.SCRIPT_SHA,anchor_sha256=C.ANCHORS.get(size),admitted=admitted,exit_receipt=final,monitor=measured)
def finalize(name,fn,by=None):
 try:
  if by is None:report[name]=fn()
  else:
   with C.bounded(max(.01,by-time.monotonic())):report[name]=fn()
 except BaseException as ex:report.setdefault(name,None);fail('finalize:'+name,ex)
finalize('admitted_drain',lambda:{n:drain(n) for n in admitted})
report['admitted_job_gone']=report['admitted_drain'] is not None and all(d['gone'] for d in report['admitted_drain'].values())
report['reaped_children']=reaped
report['host_release_refused']=not report['admitted_job_gone']   # survivors: failed, host is not released
if not report['admitted_job_gone']:fail('finalize:admitted_job_gone',AssertionError(report['admitted_drain']))
def r37_logs():
 got={}
 for n,a in admitted.items():
  if a and a.get('log'):
   data=Path(a['log']).read_bytes()[-32*1024*1024:]
   emit(event='artifact',name='r37-logs/'+Path(a['log']).name,data=base64.b64encode(data).decode());got[n]=a['log']
 return got
art=time.monotonic()+13
finalize('monitor_after_drain',by=art,fn=lambda:{n:json.loads((o/'monitor-result.json').read_bytes()) for n,o in outs.items() if (o/'monitor-result.json').exists()})
finalize('r37_logs',r37_logs,art)
def artifacts():
 names=[]
 if base.exists():
  for p in sorted(base.rglob('*')):
   rel=p.relative_to(base)
   if p.is_file() and p.suffix in ('.json','.jsonl','.stdout','.stderr') and not {'anchors','tmp','cuda-cache','inductor-cache','triton-cache'}&set(rel.parts):
    data=p.read_bytes()[:32*1024*1024]
    emit(event='artifact',name=str(rel),data=base64.b64encode(data).decode());names.append([str(rel),hashlib.sha256(data).hexdigest()])
 return names
finalize('artifacts',artifacts,art)
def physical():
 q={}
 for k,a in [('device','--query-gpu=uuid,driver_version,memory.total,memory.free,memory.used'),('processes','--query-compute-apps=gpu_uuid,pid,used_gpu_memory')]:
  p=subprocess.run(['nvidia-smi',a,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
  q[k]=dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr,utc=C.utc())
 report['final_physical']=q
 assert all(q[k]['returncode']==0 and not q[k]['stderr'].strip() for k in q),'final GPU query failed'
 rows=[x for x in q['device']['stdout'].splitlines() if x.strip()];assert len(rows)==1,'final query not one device'
 d=[x.strip() for x in rows[0].split(',')];assert len(d)==5
 q.update(gpu_uuid=d[0],driver=d[1],total_mib=int(d[2]),free_mib=int(d[3]),used_mib=int(d[4]))
 q['compute_rows']=[x.strip() for x in q['processes']['stdout'].splitlines() if x.strip()]
 dev=(measured or {}).get('device')
 q['device_identity_matches_monitor']=dev is not None and (dev['uuid'],dev['driver'],dev['total_mib'])==(d[0],d[1],q['total_mib'])
 q['free_returned_to_43_5_gib']=q['free_mib']>=44544
 q['full_free_handoff']=q['free_returned_to_43_5_gib'] and not q['compute_rows'] and (dev is None or q['device_identity_matches_monitor'])
 assert dev is None or q['device_identity_matches_monitor'],'final device identity differs from monitored device'
 assert not q['compute_rows'],'compute processes remain on GPU'
 assert q['free_returned_to_43_5_gib'],'GPU free did not return to 43.5 GiB'
 return q
finalize('final_physical',physical)
def watcher():
 assert m.job_alive(m.host(),pid,start) and hashlib.sha256(Path(R37).read_bytes()).hexdigest()==R37_SHA
 w=json.loads(Path(st.dir+'/supervisor.json').read_bytes());assert (w['pid'],w['start'],w['boot'])==C.WATCH[h]
 return dict(host=h,watcher=C.WATCH[h],r37_sha256=R37_SHA,supervisor=w)
finalize('watcher_unchanged',watcher,time.monotonic()+2)
code=CODES[failures[0]['phase'].split(':')[0]] if failures else 0
report.update(status='pass' if not failures else 'failed',code=code,failures=failures,utc=C.utc())
signal.setitimer(signal.ITIMER_REAL,0)
emit(**report)
sys.exit(code)
