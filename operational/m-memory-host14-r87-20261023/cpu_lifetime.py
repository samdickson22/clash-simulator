import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import os,time,signal,ctypes,json
from pathlib import Path

class Interrupted(BaseException):pass

def interruptions():
 def stop(n,_):raise Interrupted('CPU stage signal %d'%n)
 for n in (signal.SIGTERM,signal.SIGINT):signal.signal(n,stop)

def cleanup_signals():
 # Repeated TERM/INT cannot interrupt the finite cleanup or replace its original error.
 for n in (signal.SIGTERM,signal.SIGINT):signal.signal(n,lambda *_:None)

def subreaper():
 assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0,'CPU subreaper unavailable'

def parent_death(parent):
 # Called after native R37 child_limits, before exec. Close the parent-death race.
 assert ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGTERM,0,0,0)==0,'CPU PDEATHSIG unavailable'
 if os.getppid()!=parent:os._exit(125)

def proc(pid):
 try:s=Path('/proc/%d/stat'%pid).read_text()
 except (FileNotFoundError,ProcessLookupError):return None
 a=s[s.rindex(')')+2:].split();return a[0],int(a[1]),int(a[3]),int(a[16]),int(a[19])

def boot():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def children(pid):
 try:return [int(p) for p in Path('/proc/%d/task/%d/children'%(pid,pid)).read_text().split()]
 except (FileNotFoundError,ProcessLookupError):return []

class CleanupError(RuntimeError):
 def __init__(self,receipt):
  self.receipt=receipt
  super().__init__('CPU cleanup incomplete: '+repr(receipt))

class OwnedCPU:
 """This subreaper's children only. No token, session, name or global process-table ownership."""
 def __init__(self,m):
  self.m=m;self.me=os.getpid();self.epoch=m.boot_id();self.seen={};self.handles={};self.reaped=[];self.direct={};self.errors=[];self.sent=[]
 def error(self,where,ex):
  value=where+': '+repr(ex)
  if value not in self.errors:self.errors.append(value)
 def direct_signal(self,p,sig):
  d=self.direct[p.pid];key=[p.pid,self.seen.get(p.pid),int(sig)]
  if d['pidfd'] is None or key in self.sent:return
  libc=ctypes.CDLL(None,use_errno=True)
  if libc.syscall(424,d['pidfd'],int(sig),None,0)!=0:
   err=ctypes.get_errno()
   if err!=3:raise OSError(err,'direct child pidfd_send_signal')
  else:self.sent.append(key)
 def cooperate(self,p):
  # Per-handle hooks only. Popen's POSIX poll and both wait modes already hold
  # _waitpid_lock around these exact pidfd waits. Retain raw success BEFORE decode.
  d=self.direct[p.pid]
  if hasattr(p,'_r81_exact_wait'):
   p._r81_exact_wait['records'].append(d);return
  proof=dict(records=[d]);p._r81_exact_wait=proof;original=p._internal_poll
  def exact(pid,flags):
   assert pid==p.pid,'foreign CPU wait refused'
   fd=next((v['pidfd'] for v in proof['records'] if v['pidfd'] is not None),None)
   if fd is None:raise RuntimeError('unbound CPU waiter refused')
   info=os.waitid(3,fd,os.WEXITED|(os.WNOHANG if flags&os.WNOHANG else 0))
   if info is None:return 0,0
   return pid,self.raw_status(p,info,'exact cooperating waitid P_PIDFD')
  def poll(_deadstate=None):return original(_deadstate=_deadstate,_waitpid=exact)
  def wait(flags):
   try:return exact(p.pid,flags)
   except ChildProcessError:return p.pid,0  # stdlib compatibility; NOT status evidence.
  p._internal_poll=poll;p._try_wait=wait
 def raw_status(self,p,info,wait):
  d=self.direct[p.pid]
  d['waitid']=dict(pid=info.si_pid,code=info.si_code,status=info.si_status)
  assert info.si_pid==p.pid and info.si_code in (1,2,3),'unexpected pidfd wait status'
  status=info.si_status<<8 if info.si_code==1 else info.si_status|(128 if info.si_code==3 else 0)
  d.update(status=status,wait=wait)
  if hasattr(p,'_r81_exact_wait'):p._r81_exact_wait.update(status=status,wait=wait,waitid=dict(d['waitid']))
  return status
 def consumed(self,p):
  d=self.direct[p.pid]
  if d.get('status') is None:
   proof=getattr(p,'_r81_exact_wait',{})
   if proof.get('status') is None:raise RuntimeError('direct child wait status unavailable')
   d.update({n:proof[n] for n in ('status','wait','waitid')})
  status=d['status']
  if os.WIFEXITED(status):code=os.WEXITSTATUS(status)
  elif os.WIFSIGNALED(status):code=-os.WTERMSIG(status)
  else:raise RuntimeError('nonterminal direct child wait status')
  if p.returncode!=code:raise RuntimeError('Popen returncode contradicts retained kernel status')
  d.update(reaped=True,exit=code)
 def exit(self,p):
  self.held(p)
  d=self.direct[p.pid]
  if not d['reaped'] or d.get('status') is None:raise RuntimeError('exact CPU exit proof unavailable')
  return d['exit']
 def held(self,p,sig=None):
  # Popen.poll/wait share this lock. WNOWAIT proves an unreaped direct child without
  # consuming status; pidfd pins its lifetime before any signal. Never signal a numeric PID.
  d=self.direct[p.pid]
  if d['reaped'] and d['pidfd'] is None:return
  if not p._waitpid_lock.acquire(False):
   # A Popen.wait thread can hold the lock while waiting. The already pinned
   # pidfd remains safe to signal without that lock, including after its reap.
   if sig is not None:self.direct_signal(p,sig)
   if p.returncode is not None and getattr(p,'_r81_exact_wait',{}).get('status') is not None:self.consumed(p)
   return False  # Pending cooperating transaction, never exit/reap proof.
  try:
   if d['pidfd'] is None:
    if p.returncode is not None:
     try:os.waitid(os.P_PID,p.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
     except ChildProcessError:self.consumed(p)
     else:raise RuntimeError('unpinned returncode conflicts with OS waitable child')
    else:
     # Only initial binding uses the numeric PID, before handing the fresh Popen
     # to its caller. The lock excludes cooperating Popen reapers during binding.
     os.waitid(os.P_PID,p.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT)
     libc=ctypes.CDLL(None,use_errno=True);fd=libc.syscall(434,p.pid,0)
     if fd<0:raise OSError(ctypes.get_errno(),'direct child pidfd_open')
     d['pidfd']=fd
   if not d['reaped']:
    try:
     # Linux P_PIDFD=3 is absent from Python3.8's constants. Consuming via the
     # pinned descriptor cannot steal a later direct child's reused numeric PID.
     info=os.waitid(3,d['pidfd'],os.WEXITED|os.WNOHANG)
    except ChildProcessError:
     self.consumed(p)
    else:
     if info is not None:
      status=self.raw_status(p,info,'exact waitid P_PIDFD')
      p._handle_exitstatus(status);self.consumed(p)
     elif sig is not None:self.direct_signal(p,sig)
   if d['reaped']:
    if d['pidfd'] is not None:os.close(d['pidfd']);d['pidfd']=None
    if not any(r[0]==p.pid for r in self.reaped):self.reaped.append([p.pid,self.seen.get(p.pid),d['exit']])
  finally:p._waitpid_lock.release()
 def capture(self,p):
  # The handle is recorded before every fallible kernel or identity operation.
  assert p.pid not in self.handles,'duplicate CPU child capture'
  self.handles[p.pid]=p
  self.direct[p.pid]=dict(pidfd=None,reaped=False,exit=None,wait=None)
  try:
   self.cooperate(p)
   self.held(p)
   assert not self.direct[p.pid]['reaped'],'CPU child exited before identity capture'
   s=self.m.proc_stat(p.pid);assert s and s[1]==self.me,'CPU child identity unavailable'
   self.seen[p.pid]=s[4];return p
  except BaseException as ex:self.error('capture %d'%p.pid,ex);raise
 def reconcile(self,pid):
  if pid not in self.handles or pid not in self.seen:return False
  p=self.handles[pid];d=self.direct[pid]
  pending=self.held(p) is False
  # A busy, already pinned wait may be between kernel reap and lock release.
  # Defer this observation only; a later sweep still requires exact status.
  return d['reaped'] or pending and d['pidfd'] is not None
 def discover(self):
  assert self.m.boot_id()==self.epoch,'CPU boot changed'
  todo=[self.me];out={};visited=set()
  while todo:
   parent=todo.pop()
   if parent in visited:continue
   visited.add(parent)
   for pid in children(parent):
    # A direct child without a captured handle or prior descendant identity may
    # belong to another Popen owner. It is not adopted cleanup authority.
    if parent==self.me and pid not in self.handles and pid not in self.seen:
     raise RuntimeError('unclassified direct/adopted CPU child %d'%pid)
    s=self.m.proc_stat(pid)
    if s is None:
     if self.reconcile(pid):continue
     raise RuntimeError('CPU child identity unavailable during discovery %d'%pid)
    assert s[1]==parent,'CPU ancestry changed during discovery'
    if pid in self.seen:assert self.seen[pid]==s[4],'CPU child PID reused'
    self.seen[pid]=s[4];out[pid]=s;todo.append(pid)
  # Retain identities after reparenting; disappearance is required, including zombies.
  for pid,start in list(self.seen.items()):
   s=self.m.proc_stat(pid)
   if s and s[4]==start:out[pid]=s
  return out
 def adopted_reap(self,live):
  for pid,s in live.items():
   if pid in self.handles:continue
   if s[1]!=self.me or s[0]!='Z':continue
   try:got,status=os.waitpid(pid,os.WNOHANG)
   except ChildProcessError:continue
   if got:self.reaped.append([got,s[4],status])
 def reap(self):
  for p in self.handles.values():self.held(p)
  self.adopted_reap(self.discover())
 def drain(self,grace=35,kill_span=5,reap_span=3):
  def sweep(sig=None):
   # Discovery failure never prevents transactions on ANY retained direct handle.
   for p in self.handles.values():
    try:self.held(p,sig)
    except BaseException as ex:self.error('held %d'%p.pid,ex)
   try:live=self.discover()
   except BaseException as ex:self.error('discover',ex);live={}
   # Continue with already known adopted identities even after partial discovery.
   for pid,start in list(self.seen.items()):
    if pid in self.handles:continue
    try:
     s=self.m.proc_stat(pid)
     if s and s[4]==start:live[pid]=s
    except BaseException as ex:self.error('known %d'%pid,ex)
   for pid,s in live.items():
    if pid in self.handles:continue
    try:
     self.adopted_reap({pid:s})
     if sig is not None and s[0] not in 'ZX' and [pid,s[4],int(sig)] not in self.sent:
      if self.m.job_signal(self.m.host(),pid,s[4],sig):self.sent.append([pid,s[4],int(sig)])
    except BaseException as ex:self.error('adopted %d'%pid,ex)
   for pid,d in self.direct.items():
    if not d['reaped'] and pid not in live:
     try:
      if not self.reconcile(pid):self.error('identity %d'%pid,RuntimeError('live direct child identity unknown'))
     except BaseException as ex:self.error('reconcile %d'%pid,ex)
   return live
  for sig,span in ((signal.SIGTERM,grace),(signal.SIGKILL,kill_span)):
   end=time.monotonic()+span
   while True:
    live=sweep(sig)
    if not live and all(d['reaped'] and d['pidfd'] is None for d in self.direct.values()):break
    if time.monotonic()>=end:break
    time.sleep(min(.1,max(0,end-time.monotonic())))
  end=time.monotonic()+reap_span
  while True:
   left=sweep()
   if not left and all(d['reaped'] and d['pidfd'] is None for d in self.direct.values()) or time.monotonic()>=end:break
   time.sleep(min(.1,max(0,end-time.monotonic())))
  result=dict(gone=not left and all(d['reaped'] and d['pidfd'] is None for d in self.direct.values()) and not self.errors,identities=sorted(self.seen.items()),left={p:list(s) for p,s in left.items()},reaped=self.reaped,handles=[dict(pid=pid,start=self.seen.get(pid),exit=d['exit'],reaped=d['reaped'],wait=d['wait'],status=d.get('status'),waitid=d.get('waitid'),authority='retained direct Popen plus OS wait transaction') for pid,d in self.direct.items()],signals=self.sent,boot=self.epoch,errors=list(self.errors))
  if not result['gone']:raise CleanupError(result)
  return result


def fresh_dir(path):
 path.mkdir(exist_ok=False)
 fd=os.open(str(path.parent),os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
