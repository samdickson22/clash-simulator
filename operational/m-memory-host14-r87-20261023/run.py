import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
sys.dont_write_bytecode=True
import hashlib
from pathlib import Path
R64_GATE_BYTES=(Path(__file__).resolve().parent/'gate.py').read_bytes()
if hashlib.sha256(R64_GATE_BYTES).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 gate pin mismatch')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
R64_DISK('run.py',__file__)
_,FILES=R64_CHECK(R64_CONTEXT,(Path(__file__).resolve().parent/'payload.b64').read_text())
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import os,sys,json,time,subprocess,signal,ctypes,uuid
from pathlib import Path
import types
C=types.ModuleType('common');C.__file__=str(Path(__file__).resolve().parent/'common.py');exec(compile(FILES['common.py'],C.__file__,'exec'),C.__dict__)
m=C.load_r37();size=sys.argv[1];assert (m.host(),size) in [('127x14','M')]
OUT=C.BASE/(m.host()+'-'+size+'-attempt1');OUT.mkdir(exist_ok=False)
C.deadline(480)
assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'subreaper unavailable'
started=time.monotonic();me=os.getpid();self_start=m.proc_stat(me)[4];child=None;child_start=None;monitor=None;monitor_start=None;identity=None
owned=set();adopted=[];events=(OUT/'guard.jsonl').open('x',buffering=1);failure=None;rc=None;reaped=False;released=False;cleanup_error=None
token=uuid.uuid4().hex   # per-probe token, in addition to the unchanged CLASHER_LEASE_JOB lease token
TOK=b'\0R40_PROBE_TOKEN='+token.encode()+b'\0'
def event(**kw):kw.update(utc=C.utc(),monotonic=time.monotonic());events.write(json.dumps(kw,sort_keys=True)+'\n');events.flush()
def interrupted(*_):raise C.Deadline('lease or operator signal')
for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,interrupted)

def kids():
 """Every /proc child of this owner, including zombies: {pid:stat}."""
 out={}
 for n in os.listdir('/proc'):
  if n.isdigit():
   st=m.proc_stat(int(n))
   if st and st[1]==me:out[int(n)]=st
 return out

def discover_probe():
 """Live probe-owned processes: retained identities, probe token, probe session, descendants and subreaper-adopted children.
 The owner itself and the separately owned monitor are never included."""
 allp=m.job_scan(m.host());have={}
 for p,s in owned:
  if p in allp and allp[p]['start']==s:have[p]=allp[p]
  elif m.job_alive(m.host(),p,s):st=m.proc_stat(p);have[p]=dict(ppid=st[1],sid=st[2],start=s)   # scan omission is not exit
 for p,x in allp.items():
  if p==me or monitor is not None and p==monitor.pid:continue
  if TOK in b'\0'+x['env']+b'\0' or x['ppid']==me or identity is not None and x['sid']==identity['sid'] and x['start']>=identity['start']:have[p]=x
 growing=True
 while growing:
  growing=False
  for p,x in allp.items():
   if p not in have and p!=me and x['ppid'] in have and x['start']>=have[x['ppid']]['start']:have[p]=x;growing=True
 for p,x in have.items():assert p!=me and (monitor is None or p!=monitor.pid);owned.add((p,x['start']))
 return have

def reap_adopted():
 # Popen owns waits for the direct probe and monitor children; everything else here is an adopted descendant.
 for p,st in kids().items():
  if st[0]=='Z' and p not in (child.pid if child else None,monitor.pid if monitor else None):
   try:got,status=os.waitpid(p,os.WNOHANG)
   except ChildProcessError:continue
   if got:adopted.append([got,st[4],status])
 if child is not None:child.poll()

def cleanup_probe():
 global rc,reaped
 if reaped:return
 if child is not None and child.stdin and not child.stdin.closed:
  child.stdin.close()   # an unreleased gate reads EOF and exits 125 before exec
 for sig,span in [(signal.SIGTERM,5),(signal.SIGKILL,5)]:
  live=discover_probe()
  if not live:break
  for p,x in live.items():
   if m.job_signal(m.host(),p,x['start'],sig):event(signal=int(sig),pid=p,start=x['start'])
  end=time.monotonic()+span
  while time.monotonic()<end and discover_probe():reap_adopted();time.sleep(.1)
 if child is not None:rc=child.wait(timeout=2)
 end=time.monotonic()+3
 while True:
  reap_adopted();left={p:st for p,st in kids().items() if monitor is None or p!=monitor.pid}
  if not left or time.monotonic()>end:break
  time.sleep(.1)
 assert not discover_probe(),'probe-owned processes survived exact cleanup'
 assert not [x for x in owned if m.job_alive(m.host(),*x)],'owned identity still live'
 assert not left,'unreaped owner children %r'%left
 reaped=True
 if child is not None:C.write(OUT/'probe-reaped.json',dict(pid=child.pid,start=child_start,identity=identity,released=released,exit=rc,utc=C.utc(),descendants=sorted(owned),reaped_adopted=adopted))

def finish_cleanup():
 # Monitor traces through this marker, then takes one final post-reap sample and exits.
 if not (OUT/'cleanup-finished.json').exists():C.write(OUT/'cleanup-finished.json',dict(reaped=reaped,error=cleanup_error,probe=identity,utc=C.utc(),monotonic=time.monotonic()))

def monitor_failed():return (OUT/'monitor-failed.json').exists()
try:
 assert os.environ.get('CUDA_VISIBLE_DEVICES')!='','GPU admission retained CPU mask'
 C.lease_check();pins=C.verify_inputs(size)
 with C.bounded(8):admission=C.admission(m)
 env=os.environ.copy()
 env.update(PYTHONHOME=str(C.READY/'python'),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TORCH_HOME=str(OUT/'torch-cache'),XDG_CACHE_HOME=str(OUT/'xdg-cache'))
 # Fresh attempt-local scratch/cache paths, so pinned Python, CUDA and any compiler caches write only under allowed roots.
 for var,name in [('TMPDIR','tmp'),('CUDA_CACHE_PATH','cuda-cache'),('TORCHINDUCTOR_CACHE_DIR','inductor-cache'),('TRITON_CACHE_DIR','triton-cache')]:
  (OUT/name).mkdir(exist_ok=False);env[var]=str(OUT/name)
 # Runtime/package identity is verified by the pinned existing readiness receipt and a fresh CPU-only import.
 checkenv=env.copy();checkenv['CUDA_VISIBLE_DEVICES']=''
 python=str(C.READY/'python/bin/python3.12')
 source_boot=R64_BOOT('source_boot.py',R64_CONTEXT,(C.BASE/'payload.b64').read_text())
 check=subprocess.run([python,'-B','-c',source_boot,'check'],env=checkenv,capture_output=True,text=True,timeout=60)
 event(environment_check_exit=check.returncode,stdout=check.stdout,stderr=check.stderr);assert check.returncode==0
 # Independent monitor starts before the GPU Python process exists. Its Popen handle is the exact cleanup handle.
 monitor=subprocess.Popen(['/bin/python3','-B',str(C.BASE/'monitor.py'),str(OUT),str(me),str(self_start),token],env=os.environ.copy(),stdout=(OUT/'monitor.stdout').open('xb'),stderr=(OUT/'monitor.stderr').open('xb'))
 monitor_start=m.proc_stat(monitor.pid)[4]
 end=time.monotonic()+15
 while not (OUT/'monitor-ready.json').exists():
  assert monitor.poll() is None,'monitor failed before readiness'
  assert time.monotonic()<end,'monitor readiness timeout';time.sleep(.1)
 assert not monitor_failed(),'independent monitor latched failure before probe'
 # Exact observer handshake with its absolute terminal; the controller retains this exact handshake before any probe exists.
 ready=json.loads((OUT/'monitor-ready.json').read_bytes());t=time.monotonic()
 assert [ready[k] for k in ('pid','start','boot','owner','owner_start')]==[monitor.pid,monitor_start,m.boot_id(),me,self_start] and t<ready['deadline_monotonic']<=t+560,'monitor handshake %r'%ready
 end=time.monotonic()+10
 while not (OUT/'controller-observer.json').exists():assert time.monotonic()<end,'controller did not retain monitor handshake';time.sleep(.1)
 assert json.loads((OUT/'controller-observer.json').read_bytes())['observer']==ready,'controller retained another handshake'
 command=[python,'-B','-c',source_boot,'probe','--size',size,'--anchor',str(C.BASE/'anchors'/size/'anchor.pt'),'--microbatch','128','--test-only','--out',str(OUT/'result.json')]
 # The shell waits for an explicit gate, then exec preserves PID/start/session. The unreaped Popen child is the
 # exact cleanup handle from here on; identity inspection/publication failures are cleaned through it and the token.
 child=subprocess.Popen(['/bin/sh','-c','read gate; test "$gate" = GO || exit 125; exec "$@"','r64-M-gate']+command,stdin=subprocess.PIPE,stdout=(OUT/'probe.stdout').open('xb'),stderr=(OUT/'probe.stderr').open('xb'),cwd=str(C.SOURCE),env=dict(env,R40_PROBE_TOKEN=token),start_new_session=True)
 st=m.proc_stat(child.pid);assert st and st[1]==me and st[2]==child.pid
 child_start=st[4];owned.add((child.pid,child_start))
 identity=dict(pid=child.pid,start=child_start,sid=st[2],boot=m.boot_id(),utc=C.utc(),owner_pid=me,owner_start=self_start,monitor_pid=monitor.pid,monitor_start=monitor_start,probe_token=token)
 C.write(OUT/'probe-identity.json',identity)
 with C.bounded(8):entry=C.admission(m)
 C.write(OUT/'attempt-receipt.json',dict(identity=identity,pins=pins,admission=admission,entry=entry,command=command,lease_stop_file=env['CLASHER_LEASE_STOP_FILE'],lease_stop_by_utc=env['CLASHER_LEASE_STOP_BY_UTC'],nice=os.getpriority(os.PRIO_PROCESS,0),cuda_visible_devices=env.get('CUDA_VISIBLE_DEVICES'),scratch={k:env[k] for k in ('TMPDIR','CUDA_CACHE_PATH','TORCHINDUCTOR_CACHE_DIR','TRITON_CACHE_DIR')},timeout_seconds=480,deadline_remaining_seconds=C.remaining()))
 assert monitor.poll() is None and not monitor_failed() and time.monotonic()-float((OUT/'heartbeat').read_text())<3
 child.stdin.write(b'GO\n');child.stdin.flush();child.stdin.close();released=True;event(probe_released=identity)
 while child.poll() is None:
  C.lease_check();assert monitor.poll() is None,'independent monitor exited'
  assert not monitor_failed(),'independent monitor latched failure'
  assert time.monotonic()-float((OUT/'heartbeat').read_text())<3,'independent monitor stale'
  with C.bounded(5):resources=C.admission(m)
  event(resources=resources,probe_tree={p:x['start'] for p,x in discover_probe().items()},deadline_remaining_seconds=C.remaining());time.sleep(.25)
 cleanup_probe();finish_cleanup()
 assert rc==0,'probe nonzero exit %r'%rc
 result=json.loads((OUT/'result.json').read_bytes())
 assert result['status']=='pass' and len(result['optimizer_steps'])==2 and result['source']['source_sha256']==C.AGG and result['anchor_sha256']==C.ANCHORS[size]
 assert result['microbatch']==128 and result['dtype']=='float64'
 assert monitor.wait(timeout=20)==0,'monitor did not pass through reap'
 measured=json.loads((OUT/'monitor-result.json').read_bytes());assert measured['status']=='pass'
except BaseException as ex:
 failure=repr(ex)
 try:event(failure=failure)
 except BaseException:pass
finally:
 # Cleanup has its own finite deadline; later lease signals are recorded without aborting exact cleanup.
 C.deadline(60)
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda n,_:event(signal_during_cleanup=n))
 try:cleanup_probe()
 except BaseException as ex:cleanup_error=repr(ex);failure=(failure or '')+'; cleanup: '+cleanup_error
 try:finish_cleanup()
 except BaseException as ex:failure=(failure or '')+'; cleanup marker: '+repr(ex)
 if monitor is not None and not reaped:
  # Unverified probe cleanup: the monitor keeps tracing until the controller's verified drain, so it is not stopped here.
  failure=(failure or '')+'; monitor left observing for controller-verified drain'
 elif monitor is not None:
  try:
   try:monitor.wait(timeout=20)
   except subprocess.TimeoutExpired:
    failure=(failure or '')+'; monitor did not finish through reap'
    st=m.proc_stat(monitor.pid)   # unreaped child: the PID cannot be reused
    if st:m.job_signal(m.host(),monitor.pid,st[4],signal.SIGTERM)
    try:monitor.wait(timeout=3)
    except subprocess.TimeoutExpired:
     st=m.proc_stat(monitor.pid)
     if st:m.job_signal(m.host(),monitor.pid,st[4],signal.SIGKILL)
     monitor.wait(timeout=2)
  except BaseException as ex:failure=(failure or '')+'; monitor cleanup: '+repr(ex)
 try:
  reap_adopted()   # orphaned monitor queries are adopted by this subreaper
  left=kids();assert not left,'owner children survived %r'%left
 except BaseException as ex:failure=(failure or '')+'; final children: '+repr(ex)
 if monitor is not None and monitor.returncode!=0 and not failure:failure='monitor exit %r'%monitor.returncode
 signal.setitimer(signal.ITIMER_REAL,0)
 final=dict(status='failed' if failure else 'pass',error=failure,probe=identity,probe_pid=child.pid if child else None,probe_start=child_start,probe_released=released,probe_exit=rc,probe_reaped=reaped,monitor_exit=monitor.returncode if monitor else None,monitor_pid=monitor.pid if monitor else None,monitor_start=monitor_start,utc=C.utc(),elapsed_seconds=time.monotonic()-started,owned_probe_identities=sorted(owned),reaped_adopted=adopted,sampled_physical_peak_only=True)
 C.write(OUT/'exit-receipt.json',final);event(final=final);events.close()
if failure:sys.exit(1)
