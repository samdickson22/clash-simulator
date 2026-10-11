"""PREREG-K4S Operational Amendment OA-1: hub 127x05 owned copier for 127x03/127x04 completed blocks.

The frozen K4S mirror.py (byte-identical to T1's) is hub-01-only and asserts 8 games per block; 01 is not
available to K4S and smoke/subsample blocks carry 10 games. This file is the frozen copier protocol with only
the hub identity and the game count rebound. It never modifies a frozen file and never reads an outcome:
it moves bytes, hashes them and parses only complete.json (descriptor, game SHAs, interference).

Protocol kept from the frozen mirror.py, so the frozen guard on the timing host (ssh_transport.copier_activity)
classifies every remote child as owned copier work:
- owned-copier-admission.json {identity pid/pgid/..., source_ip, host, job, phase, active} is written on the hub
  and pushed to the source host at the same job path before any supervisor launches;
- every steady-state remote command is `env T1_COPIER_PID=<pid> T1_COPIER_PGID=<pgid>` + exact `find <job>/<phase>
  -mindepth 2 -maxdepth 2 -name complete.json -print` or `rsync --server ...` on paths under the job, over LAN ssh;
- complete.json is committed on the hub only after every game file listed in it has arrived and hash-matched;
  then hub-ack.json is written on the hub and copied back next to the source block's complete.json.

Rebinding vs the frozen mirror.py:
- hub = 127x05, source_ip = its LAN address 129.65.221.15 (gethostbyname gives 127.0.1.1 on 05);
- one source host per copier process (03 and 04 have different job paths, each under its approved root);
- game count = len(descriptor.order) (8 or 10) over the canonical K4S arms; game names exactly {id}-d27-{arm}.json;
- hub copies live under <job>/hub-blocks/<phase>/<id>/ on 05; one block id is acknowledged in one phase only.

Lifecycle (Sol review r1 findings 1-3, r2 findings 6-7):
- an exclusive non-blocking flock on <job>/oa1-copier.lock (hub) is taken before the admission receipt is inspected
  or published and is held for the copier's whole life, so at most one copier root per job;
- every transport (ssh/rsync) runs in its own process group; on timeout or error the whole group is killed and the
  copier waits until no member of that group exists, so no local transport outlives the call that started it;
- SIGTERM/SIGINT only record a stop request; the current bounded transfer finishes, then the copier stops;
- before registering and before revoking, the source must be quiescent: no remote `rsync --server` on this job's
  paths may exist (checked with one plain `pgrep` over LAN ssh, bounded wait); after revocation the source receipt
  is pulled back twice, 5 s apart, and must stay inactive;
- hub durability (hub-ack.json) and return of the ACK to the source (hub-ack.returned.json) are tracked separately; a
  block is acknowledged, returned or counted only after verify_hub_block() re-checks the ACK binding, the complete
  proof SHA, the canonical inventory and every regular game file hash on 05 (always before a return, and for every
  existing block once at copier start). An invalid hub block is quarantined (its ACK/marker renamed) and re-copied;
- on every exit path the copier revokes its own receipt only if the receipt still names this process; failure exits 3
  with a lifecycle error. There is no separate recovery mode: after SIGKILL/power loss a normal start recovers (it
  waits <=10 min on the job lock, which orphaned transports hold until they exit by themselves; timeout = stop for
  manual handling).
"""
import argparse,fcntl,hashlib,json,os,re,shlex,signal,socket,subprocess,sys,tempfile,time
from pathlib import Path

HUB='127x05'
HUB_IP='129.65.221.15'
USER='sdicks02'
ROOTS={'127x03':Path('/mpac/sdicks02/jobs/clasher'),'127x04':Path('/mpac/sdicks02/jobs-k4s')}
SOURCES=tuple(ROOTS)
ARMS=('K4-200','K4S-200','K4-180','K4S-180','K4-160','K4S-160','K4S-140','K4S-120','K4-140','K4-120')
PHASE=re.compile(r'(smoke|reporting|replacement-r[0-9]+)')
BLOCK=re.compile(r'(smoke|primary|guard)-[0-9]{4}')
JOBNAME=re.compile(r'k4s-confirm-[a-z0-9][a-z0-9-]*')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3']
RSYNC=['rsync','-a','--timeout=120','-e',shlex.join(SSH)]   # rsync I/O timeout also bounds an orphaned transfer
BLOCK_PULL=['--no-links','--ignore-times']   # never trust size+mtime: a quarantined game is always re-transferred
BLOCK_TIMEOUT=300
SMALL_TIMEOUT=30
LOCK_WAIT=600
ERRORS=(subprocess.CalledProcessError,subprocess.TimeoutExpired,AssertionError,OSError,ValueError,KeyError,TypeError)
STOP_REQUEST=[]
LOCK={}   # fd and job of the held job lock; every transport inherits the fd (see run())
PENDING=set()   # transport groups started by this root whose drain has not been proven
HOLDER=['bash','-c','"$@"; rc=$?; exit $rc','k4s-oa1-holder']   # keeps the inherited lock fd for the transport's whole life

class LifecycleError(Exception):
 """A transport could not be proven gone: never a recoverable block error; the copier stops and revokes."""

def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(x,indent=2)+'\n');tmp.replace(p)

def self_identity():
 d=Path('/proc/self');raw=(d/'cmdline').read_bytes();stat=(d/'stat').read_text().rsplit(')',1)[1].split()
 return dict(pid=os.getpid(),pgid=os.getpgrp(),start_ticks=int(stat[19]),cmdline_sha256=hashlib.sha256(raw).hexdigest(),uid=os.getuid(),exe=(d/'exe').resolve().as_posix())

def live(pid):
 try:
  d=Path('/proc')/str(pid);raw=(d/'cmdline').read_bytes();stat=(d/'stat').read_text().rsplit(')',1)[1].split()
  return dict(pid=pid,pgid=int(stat[2]),start_ticks=int(stat[19]),cmdline_sha256=hashlib.sha256(raw).hexdigest(),uid=d.stat().st_uid)
 except OSError:return None

def alive(identity):
 now=live(identity['pid'])
 return now is not None and all(now.get(k)==identity[k] for k in ('pgid','start_ticks','cmdline_sha256','uid'))

def group_members(pgid):
 out=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   f=(d/'stat').read_text().rsplit(')',1)[1].split()
   if int(f[2])==pgid and f[0]!='Z':out.append(int(d.name))   # zombies hold no transport
  except (OSError,IndexError,ValueError):pass
 return out

def drain(pgid,limit=30):
 """Kill and wait for every member of one transport process group (rsync and its ssh helper)."""
 for sig in (signal.SIGTERM,signal.SIGKILL):
  try:os.killpg(pgid,sig)
  except ProcessLookupError:return
  end=time.monotonic()+limit/2
  while group_members(pgid) and time.monotonic()<end:time.sleep(.1)
  if not group_members(pgid):return
 raise LifecycleError(f'transport group {pgid} did not drain')

def finish(p):
 """Drain the group this root just started and only then reap its leader. The leader is still an unreaped zombie
 here (run() waits with WNOWAIT), so its PID/PGID cannot have been recycled: the signal can only reach our group.
 Any failure to drain or reap (deadline, killpg/proc errors, reap timeout) is a LifecycleError: the copier stops
 (exit 3) and the group stays in PENDING, so revocation is refused while it lives. Only a completed drain AND reap
 retire the PENDING entry."""
 try:
  drain(p.pid)
  p.wait(timeout=5)
 except LifecycleError:raise
 except BaseException as e:
  raise LifecycleError(f'transport group {p.pid} cleanup failed: {type(e).__name__}: {e}') from e
 PENDING.discard(p.pid)

def run(cmd,timeout,capture=False):
 """One transport in its own process group; nothing in that group outlives this call. Output goes to files so a
 stray helper cannot hold the call open through an inherited pipe. The transport runs under a bash holder that
 inherits the job-lock fd, so the job lock stays held while any transport process lives, even if this root is
 SIGKILLed: a successor can only take the lock after every orphan has exited by itself."""
 fd=LOCK.get('fd')
 with tempfile.TemporaryFile() as outf,tempfile.TemporaryFile() as errf:
  p=subprocess.Popen(HOLDER+list(cmd) if fd is not None else cmd,start_new_session=True,pass_fds=(fd,) if fd is not None else (),
                     stdout=outf if capture else subprocess.DEVNULL,stderr=errf,stdin=subprocess.DEVNULL)
  try:
   PENDING.add(p.pid);deadline=time.monotonic()+timeout
   while os.waitid(os.P_PID,p.pid,os.WEXITED|os.WNOHANG|os.WNOWAIT) is None:   # exited, but not reaped
    if time.monotonic()>deadline:raise subprocess.TimeoutExpired(cmd,timeout)
    time.sleep(.05)
  except BaseException:
   finish(p);raise
  finish(p)   # also drains helpers left behind by a finished leader (normally none)
  outf.seek(0);out=outf.read().decode(errors='replace')
  if p.returncode!=0:
   errf.seek(0);raise subprocess.CalledProcessError(p.returncode,cmd,out,errf.read()[-2000:].decode(errors='replace'))
 return out

def check_job(j,host):
 # Owned, canonical K4S job paths only: never a symlinked alias, T1 path or 04 perception storage.
 assert host in ROOTS and j.is_absolute() and JOBNAME.fullmatch(j.name),'job name'
 assert j.parent==ROOTS[host] and Path(os.path.realpath(j))==j,'job must sit directly under the approved root for its host'

def lock(j,wait=0):
 """Exclusive job lock. Orphaned transports of a dead root hold it through their inherited fd; nothing is ever
 killed to get it: wait (bounded) until they exit by themselves (rsync --timeout, ssh ServerAlive, closed pipes)."""
 j.mkdir(parents=True,exist_ok=True)
 fd=os.open(j/'oa1-copier.lock',os.O_RDWR|os.O_CREAT,0o600);end=time.monotonic()+wait
 while True:
  try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
  except BlockingIOError:
   if time.monotonic()>=end:
    os.close(fd);raise SystemExit(f'job lock held by another OA-1 copier or its orphaned transports (waited {wait}s); nothing was signalled')
   time.sleep(2)
 LOCK.update(fd=fd,job=j)
 return fd

def unlock(fd):
 if LOCK.get('fd')==fd:LOCK.clear()
 os.close(fd)

def own_transports_gone():
 """Read-only: every transport group this root started has been proven drained (no signal is sent here)."""
 live=sorted(pg for pg in PENDING if group_members(pg))
 assert not live,f'own transport groups still alive: {live}'

def prefix(j):
 r=read(j/'owned-copier-admission.json')['identity']
 assert r['pid']==os.getpid() and r['pgid']==os.getpgrp(),'copier root attribution changed'
 return ['env',f'T1_COPIER_PID={r["pid"]}',f'T1_COPIER_PGID={r["pgid"]}']

def rsync_path(j):return shlex.join(prefix(j)+['rsync'])

def push_verified(j,host,local,remote,owned):
 """Copy one small file to the source and prove it arrived by pulling it back and byte-comparing."""
 extra=['--rsync-path',rsync_path(j)] if owned else []
 run(RSYNC+extra+[str(local),f'{host}:{remote}'],SMALL_TIMEOUT)
 back=Path(str(local)+'.source-check')
 if back.exists():back.unlink()
 run(RSYNC+extra+[f'{host}:{remote}',str(back)],SMALL_TIMEOUT)
 same=back.read_bytes()==Path(local).read_bytes();back.unlink()
 assert same,'source copy differs after transfer'

def remote_transfers(j,host):
 """PIDs of any rsync server still working on this job's paths on the source (one plain LAN ssh, pgrep only)."""
 pattern=f'^rsync --server .* {j}/'
 try:out=run(SSH+[host,shlex.join(['pgrep','-u',USER,'-f','--',pattern])],SMALL_TIMEOUT,capture=True)
 except subprocess.CalledProcessError as e:
  if e.returncode==1:return []   # pgrep: nothing matched
  raise
 return [int(x) for x in out.split()]

def quiesce(j,host,limit=60):
 end=time.monotonic()+limit
 while True:
  left=remote_transfers(j,host)
  if not left:return
  if time.monotonic()>end:raise RuntimeError(f'source transfers still running on {host}: {left}')
  time.sleep(2)

def register(j,host,phase,me):
 """Caller holds the job lock; `me` is this process's identity (set first, so cleanup can revoke even when the
 initial push fails)."""
 target=j/'owned-copier-admission.json'
 if target.exists():
  old=read(target)
  assert not alive(old['identity']),'finish/stop the prior owned copier before registering another phase'
 assert me==self_identity() and me['pgid']==me['pid'],'copier must lead its own process group'
 quiesce(j,host)   # no earlier transfer may still publish into the source
 write(target,dict(utc=utc(),host=HUB,source_ip=HUB_IP,identity=me,job=str(j),phase=phase,source_host=host,active=True,amendment='K4S OA-1'))
 # Registered before the scientific supervisor launches on the source host; a plain LAN copy, verified.
 push_verified(j,host,target,target,owned=False)
 return me

def revoke(j,host,me):
 """Deactivate this process's own admission receipt on the hub and the source (never a successor's). Never signals
 anything. Every transport this root started is proven gone (read-only check), the source must be quiescent, and
 the inactive receipt is confirmed twice, 5 s apart. There is no separate recovery mode: after a crash, SIGKILL or
 power loss a normal copier start is the recovery (it waits on the inherited job lock until every orphan has exited
 by itself, accepts the dead prior receipt, re-verifies every hub block and re-registers)."""
 target=j/'owned-copier-admission.json';receipt=read(target)
 assert receipt['identity']==me,'receipt belongs to another copier; not revoking a successor'
 own_transports_gone()   # read-only proof that every transport this root started is gone
 receipt.update(active=False,finished_utc=utc());write(target,receipt)
 last=None
 for _ in range(3):
  try:
   quiesce(j,host)
   push_verified(j,host,target,target,owned=False)
   time.sleep(5)
   back=Path(str(target)+'.source-recheck')
   run(RSYNC+[f'{host}:{target}',str(back)],SMALL_TIMEOUT)
   ok=back.read_bytes()==target.read_bytes();back.unlink()
   assert ok and not remote_transfers(j,host),'source receipt changed after revocation'
   return receipt
  except ERRORS+(RuntimeError,) as e:last=e;time.sleep(5)
 raise RuntimeError(f'revocation not confirmed on {host}: {type(last).__name__}: {last}')

def expected_games(proof,identity):
 d=proof['descriptor'];order=d['order']
 assert d['id']==identity and BLOCK.fullmatch(identity),'block identity'
 assert isinstance(order,list) and len(order) in (8,10) and len(set(order))==len(order) and set(order)<=set(ARMS),'arm order'
 names={f'{identity}-d27-{arm}.json' for arm in order}
 assert set(proof['games'])==names and len(proof['games'])==len(order),'game inventory differs from descriptor order'
 return len(order)

def verify_games(dest,proof,identity):
 n=expected_games(proof,identity)
 games=dest/'games';assert games.is_dir() and not games.is_symlink(),'games directory'
 for name,h in proof['games'].items():
  f=games/name;assert f.is_file() and not f.is_symlink(),name
  assert sha(f)==h,name
 return n

def verify_hub_block(j,host,phase,identity):
 """Full check of a hub block before its ACK is returned or counted: ACK binding, proof SHA, inventory, game bytes."""
 dest=j/'hub-blocks'/phase/identity;ack=read(dest/'hub-ack.json');proof_file=dest/'complete.json'
 assert proof_file.is_file() and not proof_file.is_symlink(),'hub complete proof'
 want=dict(hub=HUB,source_host=host,job=str(j),phase=phase,block=identity,sealed=True)
 assert all(ack.get(k)==v for k,v in want.items()),'hub ACK binding'
 assert ack.get('complete_sha256')==sha(proof_file),'hub ACK does not bind the hub proof'
 proof=read(proof_file);assert proof['host']==host,'proof host'
 n=verify_games(dest,proof,identity);assert ack.get('games')==n,'hub ACK game count'
 return ack

def quarantine(j,phase,identity,why):
 dest=j/'hub-blocks'/phase/identity;stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
 for name in ('hub-ack.json','hub-ack.returned.json','complete.json'):
  if (dest/name).exists():(dest/name).replace(dest/f'{name}.invalid-{stamp}')
 write(dest/f'quarantine-{stamp}.json',dict(utc=utc(),reason=why))

def acked_elsewhere(j,phase,identity):
 root=j/'hub-blocks'
 return [p.name for p in root.iterdir() if p.is_dir() and p.name!=phase and (p/identity/'hub-ack.json').exists()] if root.exists() else []

def copy_block(j,host,phase,identity):
 """Durable on the hub: raw files, hash-verified proof, then hub-ack.json (local)."""
 assert socket.gethostname()==HUB and host in SOURCES and PHASE.fullmatch(phase) and BLOCK.fullmatch(identity)
 assert not acked_elsewhere(j,phase,identity),'block id already acknowledged in another phase'
 source=f'{host}:{j}/{phase}/{identity}/';dest=j/'hub-blocks'/phase/identity
 dest.mkdir(parents=True,exist_ok=True);os.chmod(dest,0o700)
 # complete.json is committed on the hub only after the raw files and hashes arrive. Symlinks are never copied.
 run(RSYNC+BLOCK_PULL+['--rsync-path',rsync_path(j),'--exclude','complete.json','--exclude','hub-ack.json','--exclude','hub-ack.returned.json',source,str(dest)+'/'],BLOCK_TIMEOUT)
 pending=dest/'complete.pending.json'
 run(RSYNC+['--no-links','--rsync-path',rsync_path(j),source+'complete.json',str(pending)],SMALL_TIMEOUT)
 proof=read(pending);assert proof['host']==host,'proof host'
 n=verify_games(dest,proof,identity)
 pending.replace(dest/'complete.json')
 ack=dict(utc=utc(),hub=HUB,hub_ip=HUB_IP,amendment='K4S OA-1',source_host=host,job=str(j),phase=phase,block=identity,complete_sha256=sha(dest/'complete.json'),games=n,sealed=True)
 write(dest/'hub-ack.json',ack)
 return ack

def return_ack(j,host,phase,identity):
 """Idempotent: verify the hub block, put its ACK next to the source complete.json, prove it (pull back, compare)."""
 ack=verify_hub_block(j,host,phase,identity);dest=j/'hub-blocks'/phase/identity
 push_verified(j,host,dest/'hub-ack.json',f'{j}/{phase}/{identity}/hub-ack.json',owned=True)
 write(dest/'hub-ack.returned.json',dict(utc=utc(),source_host=host,hub_ack_sha256=sha(dest/'hub-ack.json'),complete_sha256=ack['complete_sha256'],verified_by='full hub verification + pull-back byte compare'))

def returned(j,phase,identity):
 d=j/'hub-blocks'/phase/identity
 try:
  m=read(d/'hub-ack.returned.json')
  return m['hub_ack_sha256']==sha(d/'hub-ack.json') and m['complete_sha256']==sha(d/'complete.json')
 except (OSError,ValueError,KeyError):return False

def listing(j,host,phase):
 cmd=prefix(j)+['find',str(j/phase),'-mindepth','2','-maxdepth','2','-name','complete.json','-print']
 out=run(SSH+[host,shlex.join(cmd)],SMALL_TIMEOUT,capture=True)
 found=[]
 for line in out.splitlines():
  p=Path(line);identity=p.parent.name
  assert p==j/phase/identity/'complete.json' and BLOCK.fullmatch(identity),'unexpected listing line'
  found.append(identity)
 return found

def startup_verify(j,host,phase):
 """Once per copier start: every existing hub block of this phase is fully re-verified; invalid ones are quarantined
 (and re-copied on the next pass if the source still lists them)."""
 root=j/'hub-blocks'/phase;bad={}
 for d in sorted(root.iterdir()) if root.exists() else []:
  if not (d/'hub-ack.json').exists():continue
  try:verify_hub_block(j,host,phase,d.name)
  except ERRORS as e:
   bad[d.name]=f'{type(e).__name__}: {e}';quarantine(j,phase,d.name,bad[d.name])
 return bad

def one_pass(j,host,phase,verified):
 """`verified`: hub blocks fully verified in this copier's lifetime (startup check or fresh copy/return)."""
 listed=error=None;blocks={}
 try:listed=listing(j,host,phase)
 except ERRORS+(RuntimeError,) as e:error=f'listing {type(e).__name__}: {e}'
 # One failing block never stalls the others; each failure is recorded and retried on the next pass.
 for identity in listed or []:
  if STOP_REQUEST:break
  try:
   d=j/'hub-blocks'/phase/identity
   if (d/'hub-ack.json').exists() and identity not in verified:
    try:verify_hub_block(j,host,phase,identity)
    except ERRORS as e:quarantine(j,phase,identity,f'{type(e).__name__}: {e}');raise
    verified.add(identity)
   if not (d/'hub-ack.json').exists():
    print(json.dumps(copy_block(j,host,phase,identity)),flush=True);verified.add(identity)
   if not returned(j,phase,identity):return_ack(j,host,phase,identity)
  except ERRORS+(RuntimeError,) as e:blocks[identity]=f'{type(e).__name__}: {e}'
 ids=listed or []
 durable=[x for x in ids if x in verified and (j/'hub-blocks'/phase/x/'hub-ack.json').exists()]
 back=[x for x in durable if returned(j,phase,x)]
 return dict(utc=utc(),host=host,phase=phase,listed=None if listed is None else len(listed),durable_on_hub=len(durable),ack_returned=len(back),
             pending_return=sorted(set(ids)-set(back)),error=error,block_errors=blocks,lifecycle_error=None,stop_request=STOP_REQUEST[:1],sealed=True)

def _signal(sig,frame):STOP_REQUEST.append(signal.Signals(sig).name)

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--host',required=True,choices=SOURCES)
 p.add_argument('--phase',required=True);p.add_argument('--once',action='store_true')
 a=p.parse_args(argv);j=a.job
 assert socket.gethostname()==HUB and os.getpriority(os.PRIO_PROCESS,0)==19 and len(os.sched_getaffinity(0))==1
 check_job(j,a.host)
 signal.signal(signal.SIGTERM,_signal);signal.signal(signal.SIGINT,_signal)
 health=j/f'copy-health-{a.host}.json'
 assert PHASE.fullmatch(a.phase)
 fd=lock(j,wait=LOCK_WAIT)
 try:
  me=None;status=0;last=None
  try:
   me=self_identity();register(j,a.host,a.phase,me)
   verified=set();bad=startup_verify(j,a.host,a.phase)
   verified|={d.name for d in (j/'hub-blocks'/a.phase).iterdir() if (d/'hub-ack.json').exists()} if (j/'hub-blocks'/a.phase).exists() else set()
   if bad:write(j/f'startup-quarantine-{a.host}.json',dict(utc=utc(),phase=a.phase,quarantined=bad))
   while not (j/'STOP-COPY').exists() and not STOP_REQUEST:
    last=one_pass(j,a.host,a.phase,verified);write(health,last)
    if a.once:break
    for _ in range(10):
     if STOP_REQUEST or (j/'STOP-COPY').exists():break
     time.sleep(1)
  except LifecycleError as e:
   status=3;last=dict(last or dict(utc=utc(),host=a.host,phase=a.phase,sealed=True),lifecycle_error=f'LifecycleError: {e}');write(health,last)
  except Exception as e:   # any other fatal error (e.g. registration push, startup verification I/O): honest exit 2
   reason=f'{type(e).__name__}: {e}'   # also in the projected `error` field (k4s_health.hub shows it)
   status=2;last=dict(last or dict(utc=utc(),host=a.host,phase=a.phase,sealed=True),fatal_error=reason,error=f'fatal: {reason}');write(health,last)
  finally:
   target=j/'owned-copier-admission.json'
   if me is not None and target.exists() and read(target)['identity']==me:
    try:
     revoke(j,a.host,me)
     if last is not None:write(health,dict(last,utc=utc(),stop_request=STOP_REQUEST[:1],revoked=True,final=True))
    except (RuntimeError,LifecycleError,AssertionError,*ERRORS) as e:
     state=dict(last or dict(utc=utc(),host=a.host,phase=a.phase,sealed=True));prev=state.get('lifecycle_error')
     state.update(utc=utc(),lifecycle_error=(prev+'; then revocation: ' if prev else '')+f'{type(e).__name__}: {e}',revoked=False)
     write(health,state);status=3
  return status
 finally:
  unlock(fd)
if __name__=='__main__':sys.exit(main())
