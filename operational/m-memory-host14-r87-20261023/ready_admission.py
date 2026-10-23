import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
if len(sys.argv)>1 and len(sys.argv[1].encode())>126000:raise RuntimeError('packed admission argument cap')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
R77_ARGUMENTS(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import types,json,os,time,signal,subprocess
from pathlib import Path
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
L=types.ModuleType('cpu_lifetime');exec(compile(FILES['cpu_lifetime.py'],'cpu_lifetime.py','exec'),L.__dict__)
L.interruptions();L.subreaper()
m=C.load_r37(CTX)
assert m.host()=='127x14'
a=types.SimpleNamespace(**json.loads(sys.argv[1]))
R77_READY_PERMIT(CTX)
os.environ['R40_WRAPPERS']=json.dumps(C.wrapper_chain(m))
assert (a.name,a.workers,a.pss_gb,a.gpu_gb,a.grace,a.cwd)==('M-host14-ready-stage-20261023',6,2,0,120,m.STATE_ROOT)
assert a.cmd==['/bin/python3','-B','-c',R64_BOOT('ready_stage.py',CTX,PAYLOAD)]
st=C.state(m)
class ExclusiveAdmission:
 def __getattr__(self,n):return getattr(st,n)
 def lock(self,name,block=True):
  lk=st.lock(name,block)
  if name not in ('state.lock','generation.lock'):return lk
  try:
   R77_READY_PERMIT(CTX)  # Both locks, before native intent or spawn.
   C.admission(m,workers=a.workers,pss_gb=a.pss_gb)
   recs=st.records();assert not any(r['state'] in ('intent','uncertain','stopping') for r in recs.values())
   jobs=m.job_discover(m.host(),recs,m.job_scan(m.host()),m.boot_id())
   assert not any(v and C.gpu_contract(recs[n])>0 for n,v in jobs.items()),'BC/other GPU admission won; defer without exposure'
   assert not jobs.get('M-host14-stage-20261023'),'own stage must be exactly gone before next admission'
   return lk
  except BaseException:
   if lk is not None:lk.close()
   raise
# Keep this exact wrapper chain alive until all CPU children have exited and been reaped.
owner=L.OwnedCPU(m);failure=None;cleanup=None;release_r,release_w=os.pipe()
resultdir=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r77-stage-20261023');result_created=False
original_subprocess=m.subprocess
class Capture:
 def __getattr__(self,n):return getattr(original_subprocess,n)
 def Popen(self,*args,**kw):
  assert not owner.handles,'CPU owner permits one native root only'
  limits=kw['preexec_fn'];parent=os.getpid()
  def prepare():limits();L.parent_death(parent)
  kw['preexec_fn']=prepare;kw['pass_fds']=(release_r,)
  kw['env']=dict(kw['env'],R78_CPU_RELEASE_FD=str(release_r),R78_CPU_OWNER=json.dumps(dict(pid=parent,start=m.proc_stat(parent)[4],boot=m.boot_id())))
  return owner.capture(original_subprocess.Popen(*args,**kw))
C.deadline(1830)  # <=30s admission plus unchanged <=1800s CPU work; cleanup is separate.
try:
 with C.bounded(30):
  R77_READY_PERMIT(CTX);C.admission(m,workers=a.workers,pss_gb=a.pss_gb)
  L.fresh_dir(resultdir);result_created=True
  m.subprocess=Capture()
  try:m.admit(a,ExclusiveAdmission(),m.LEASE_DIR+'/127x14.json')
  finally:m.subprocess=original_subprocess
  assert len(owner.handles)==1,'native CPU root not captured'
  R77_READY_PERMIT(CTX)
  os.write(release_w,b'READY\n');os.close(release_w);release_w=None
  os.close(release_r);release_r=None
 sys.stdout.flush()
 child=next(iter(owner.handles.values()))
 while child.poll() is None:
  owner.reap()
  with C.bounded(8):C.admission(m)
  time.sleep(.25)
 assert owner.exit(child)==0,'CPU stage failed %r'%child.returncode
except BaseException as ex:failure=repr(ex)
finally:
 L.cleanup_signals();C.deadline(50)
 for fd in (release_r,release_w):
  if fd is not None:os.close(fd)
 try:
  cleanup=owner.drain(35)
  if not cleanup['gone']:raise RuntimeError('CPU stage owned survivors %r'%cleanup)
 except BaseException as ex:
  cleanup=getattr(ex,'receipt',cleanup);failure=(failure or '')+'; cleanup: '+repr(ex)
 try:
  if result_created:C.write(resultdir/'ready-owner-result.json',dict(status='failed' if failure else 'CPU-owner-pass',error=failure,owner=dict(pid=owner.me,start=m.proc_stat(owner.me)[4],boot=owner.epoch),wrappers=json.loads(os.environ['R40_WRAPPERS']),drain=cleanup,utc=C.utc()))
 except BaseException as ex:failure=(failure or '')+'; owner receipt: '+repr(ex)
 signal.setitimer(signal.ITIMER_REAL,0)
if failure:raise RuntimeError(failure)

