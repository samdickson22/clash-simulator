import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='03bc6ded28c261f7b3499544a351627c2810732f5c6582b5baae099f290e5022':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
R77_READY_PERMIT(CTX)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('host14 required')
import json,os,time,subprocess,signal,tarfile,types,select
from pathlib import Path,PurePosixPath
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
L=types.ModuleType('cpu_lifetime');exec(compile(FILES['cpu_lifetime.py'],'cpu_lifetime.py','exec'),L.__dict__)
F=types.ModuleType('cpu_fetch');exec(compile(FILES['cpu_fetch.py'],'cpu_fetch.py','exec'),F.__dict__)
L.interruptions();L.subreaper()
m=C.load_r37(CTX);plan=json.loads(FILES['ready-plan.json']);root=Path(plan['ready'])
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('CLASHER_LEASE_JOB')
assert os.sched_getaffinity(0)<=set(range(32)) and os.getpriority(os.PRIO_PROCESS,0)>=15
C.deadline(1800)
# Admission publication must succeed before any destination or source-phase write.
owner=json.loads(os.environ['R78_CPU_OWNER']);fd=int(os.environ.pop('R78_CPU_RELEASE_FD'))
assert owner['boot']==m.boot_id() and os.getppid()==owner['pid'] and m.proc_stat(owner['pid'])[4]==owner['start'],'CPU owner identity changed'
L.parent_death(owner['pid'])
try:
 with C.bounded(30):
  assert select.select([fd],[],[],28)[0] and os.read(fd,16)==b'READY\n','CPU admission not published'
finally:os.close(fd)
R77_READY_PERMIT(CTX)  # Fresh before writes, never re-applied to ongoing1800s work.
C.lease_check();pre=C.admission(m,pss_gb=0)
assert pre['deadline']-time.time()>2820,'insufficient CPU transfer lease headroom'
assert not root.exists()
resultdir=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r77-stage-20261023');assert resultdir.is_dir(),'CPU owner result directory missing'
phase=dict(token=os.urandom(16).hex(),phase_started_epoch=time.time())
fetch=F.SourceFetch(C,L,m,R64_BOOT('ready_source.py',CTX,PAYLOAD),phase,resultdir,R78_SOURCE_SSH);failed=None;cleanup=None
# This is a separate CPU-admitted transfer, never entered from a measurement controller.
def streamhash(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def get(source,dest,expected,seconds=600):
 fetch.get(source,dest,expected,seconds)
 assert streamhash(dest)==expected,'CPU input archive pin mismatch'
def safe_members(t,expected):
 seen=set()
 for x in t.getmembers():
  p=PurePosixPath(x.name)
  assert not p.is_absolute() and '..' not in p.parts and (x.isfile() or x.isdir()),'unsafe archive member'
  assert '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo'),'bytecode archive member'
  assert x.name not in seen,'duplicate archive member';seen.add(x.name)
  if x.isfile():assert x.name in expected and x.size==expected[x.name]['bytes'],'unexpected archive file'
 assert {x.name for x in t.getmembers() if x.isfile()}==set(expected),'archive inventory mismatch'
try:
 root.mkdir(exist_ok=False)
 get(plan['inventory_source'],root/'cpu-stage-inventory.json',plan['inventory_sha256'],45)
 inventory=json.loads((root/'cpu-stage-inventory.json').read_bytes());assert inventory['ready']==str(root) and inventory['host']=='127x14'
 for name,item in plan['archives'].items():
  archive=root/('.transfer-'+name)
  get(item['source_path'],archive,item['sha256'])
  assert archive.stat().st_size==item['bytes']
  if item.get('copy_only'):
   os.link(str(archive),str(root/name));archive.unlink()
  else:
   expected=inventory['archives'][name]['files']
   with tarfile.open(str(archive)) as t:
    safe_members(t,expected)
    for x in t.getmembers():
     dest=root/x.name
     if x.isdir():dest.mkdir(parents=True,exist_ok=True);continue
     dest.parent.mkdir(parents=True,exist_ok=True)
     with t.extractfile(x) as a,dest.open('xb') as b:
      for block in iter(lambda:a.read(1024*1024),b''):b.write(block)
     assert streamhash(dest)==expected[x.name]['sha256'];dest.chmod(x.mode&0o777)
   archive.unlink()
 # Verify all bytes without importing the environment. Receipt lives outside immutable runtime inventory.
 C.no_cache(root)
 assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}==set(inventory['ready_files'])|{'cpu-stage-inventory.json'}
 for rel,row in inventory['ready_files'].items():assert (root/rel).stat().st_size==row['bytes'] and streamhash(root/rel)==row['sha256'],rel
 C.lease_check();C.admission(m)
 # The success receipt is published only after exact local and source cleanup below.
except BaseException as ex:failed=repr(ex)
finally:
 L.cleanup_signals();C.deadline(30)
 try:
  cleanup=fetch.cleanup()
  assert not cleanup['errors'] and cleanup['source_confirmed'] and cleanup['local']['gone'],'CPU/source cleanup unproved %r'%cleanup
 except BaseException as ex:failed=(failed or '')+'; cleanup: '+repr(ex)
 try:
  C.write(resultdir/('ready-stage-failed.json' if failed else 'ready-stage-result.json'),dict(status='failed' if failed else 'CPU-transfer-pass',error=failed,host='127x14',inventory_sha256=plan['inventory_sha256'],root=str(root),gpu_gb=0,imports=0,phase=phase,cleanup=cleanup,utc=C.utc()))
 except BaseException as ex:failed=(failed or '')+'; stage receipt: '+repr(ex)
 signal.setitimer(signal.ITIMER_REAL,0)
if failed:raise RuntimeError(failed)
