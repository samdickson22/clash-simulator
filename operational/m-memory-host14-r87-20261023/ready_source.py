import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x05':raise RuntimeError('source host05 required')
import os,json,time,signal,select,types,stat
from pathlib import Path
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
L=types.ModuleType('cpu_lifetime');exec(compile(FILES['cpu_lifetime.py'],'cpu_lifetime.py','exec'),L.__dict__)

def no_children(event,args):
 if event in ('subprocess.Popen','os.fork','os.forkpty','os.posix_spawn','os.system','socket.connect'):raise RuntimeError('source helper cannot create children/network')

def source_accounting():
 # Source05 has no R37 host entry. Charge all same-UID Clasher processes plus this dedicated wrapper
 # chain, with conservative 32-process/32GiB caps, without granting a lease or querying a GPU.
 m=types.SimpleNamespace(proc_stat=L.proc,boot_id=L.boot)
 chain=C.wrapper_chain(m);ids={w['pid'] for w in chain};rows={}
 for n in os.listdir('/proc'):
  if not n.isdigit():continue
  pid=int(n)
  try:
   if C.proc_uid(pid)!=os.getuid():continue
   cmd=Path('/proc/%d/cmdline'%pid).read_bytes()
   try:cwd=os.readlink('/proc/%d/cwd'%pid)
   except FileNotFoundError:
    if L.proc(pid) is None:continue
    cwd=''
   env=Path('/proc/%d/environ'%pid).read_bytes()
   own=pid in ids or b'\0CLASHER_LEASE_JOB=' in b'\0'+env or cwd.startswith('/mpac/sdicks02/repos/clasher') or cwd.startswith('/mpac/sdicks02/jobs/clasher/') or b'/mpac/sdicks02/repos/clasher' in cmd or b'/mpac/sdicks02/jobs/clasher/' in cmd
   if not own:continue
   s=L.proc(pid)
   if s is None:continue
   pss,how=C.wrapper_pss(m,pid)
   assert L.proc(pid)[4]==s[4],'source accounting PID changed'
   if pid in ids and not cmd.startswith(b'sshd'):
    assert s[3]>=10,'source compute nice below10'
    assert os.sched_getaffinity(pid)<=set(range(32)),'source affinity outside0-31'
   rows[pid]=dict(start=s[4],pss=pss,source=how)
  except (FileNotFoundError,ProcessLookupError):
   if L.proc(pid) is not None:raise
 assert ids<=set(rows),'source wrappers missing from accounting'
 pss=sum(v['pss'] for v in rows.values())
 reserved_procs=len(rows)+max(0,6-len(ids));reserved_pss=pss+max(0,2*(1<<30)-sum(rows[p]['pss'] for p in ids))
 assert reserved_procs<=32 and reserved_pss<=32*(1<<30),'source all-owner plus phase reservation cap'
 assert sum(rows[p]['pss'] for p in ids)<=2*(1<<30) and len(ids)<=6,'source phase six-slot/two-GiB budget'
 mem=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))*1024
 assert mem-2*(1<<30)>28*(1<<30) and os.getloadavg()[0]<=90,'source headroom'
 return dict(procs=len(rows),pss=pss,reserved_procs=reserved_procs,reserved_pss=reserved_pss,wrappers=chain,rows=rows,mem=mem,load=os.getloadavg()[0])

def identity():return dict(pid=os.getpid(),start=L.proc(os.getpid())[4],boot=L.boot(),uid=os.getuid())

def stream(source,seconds,account):
 """No children. Bounded even if the receiver stalls or disappears; EOF/missing heartbeat stops it."""
 end=time.monotonic()+seconds;last=time.monotonic();buffer=b'';digest=hashlib.sha256();total=0;next_account=0;sample=None
 fd=os.open(str(source),os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 try:
  assert stat.S_ISREG(os.fstat(fd).st_mode),'source is not regular'
  os.set_blocking(1,False);os.set_blocking(0,False)
  while True:
   now=time.monotonic()
   assert now<end,'source fetch deadline'
   assert now-last<5,'source heartbeat lost'
   if now>=next_account:sample=account();next_account=now+1
   if not buffer:
    buffer=os.read(fd,1024*1024)
    if not buffer:break
    digest.update(buffer);total+=len(buffer)
   r,w,_=select.select([0],[1],[],min(.2,max(.001,end-now)))
   if 0 in r:
    b=os.read(0,4096)
    assert b and set(b)<={10,72},'source disconnected/stopped'  # H/newline only; STOP or EOF fails.
    last=time.monotonic()
   if 1 in w and buffer:
    try:count=os.write(1,buffer);buffer=buffer[count:]
    except BlockingIOError:pass
  return dict(bytes=total,sha256=digest.hexdigest(),accounting=sample)
 finally:os.close(fd)

def confirm(folder,request,seconds=10):
 ident=json.loads((folder/'identity.json').read_bytes())
 assert ident['boot']==L.boot() and ident['uid']==os.getuid(),'source identity boot/UID changed'
 end=time.monotonic()+seconds
 while True:
  s=L.proc(ident['pid'])
  if s is None or s[4]!=ident['start']:break  # exact identity absent; zombies do not pass.
  assert time.monotonic()<end,'source helper not reaped'
  time.sleep(.1)
 terminal=json.loads((folder/'terminal.json').read_bytes())
 assert terminal['identity']==ident and terminal['token']==request['token'] and terminal['no_children'] is True,'source receipt identity mismatch'
 return dict(source_reaped=True,identity=ident,terminal=terminal)

def main(request):
 sys.addaudithook(no_children);L.interruptions();C.deadline(20 if request['mode']=='confirm' else request['seconds'])
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.getpriority(os.PRIO_PROCESS,0)>=15
 assert os.sched_getaffinity(0)<=set(range(32))
 phase=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r77-source-20261023')
 plan=json.loads(FILES['ready-plan.json']);sources=[plan['inventory_source']]+[v['source_path'] for v in plan['archives'].values()]
 i=request['index'];assert type(i) is int and 0<=i<len(sources)
 assert len(request['token'])==32 and all(c in '0123456789abcdef' for c in request['token'])
 folder=phase/('fetch-%d'%i)
 if request['mode']=='confirm':
  try:return confirm(folder,request)
  finally:signal.setitimer(signal.ITIMER_REAL,0)
 assert request['mode']=='stream' and request['source']==sources[i] and 0<request['seconds']<=600
 assert 0<=time.time()-request['phase_started_epoch']<=1800,'CPU phase work expired'
 assert 0<=request['phase_started_epoch']-CTX['cpu_stage']['checked_epoch']<=60,'CPU phase did not start on fresh permit'
 # Each logical phase/fetch is exclusive and permanent on05; later fetches share the original phase.
 phase_record=dict(token=request['token'],freeze_sha256=R64_SHA(__import__('base64').b64decode(CTX['freeze'])),started_epoch=request['phase_started_epoch'])
 accounting=source_accounting()
 if i==0:
  R77_READY_PERMIT(CTX)
  L.fresh_dir(phase);C.write(phase/'phase.json',phase_record)
 else:assert json.loads((phase/'phase.json').read_bytes())==phase_record
 L.fresh_dir(folder);ident=identity();C.write(folder/'identity.json',ident)
 failure=None;result=None
 try:result=stream(Path(request['source']),request['seconds'],source_accounting)
 except BaseException as ex:failure=repr(ex)
 finally:
  L.cleanup_signals();C.deadline(5)
  try:C.write(folder/'terminal.json',dict(identity=ident,token=request['token'],no_children=True,status='failed' if failure else 'pass',error=failure,result=result,initial_accounting=accounting))
  finally:signal.setitimer(signal.ITIMER_REAL,0)
 if failure:raise RuntimeError(failure)

if __name__=='__main__' or 'CTX' in globals():
 answer=main(json.loads(sys.argv[1]))
 if answer is not None:print(json.dumps(answer,sort_keys=True),flush=True)
