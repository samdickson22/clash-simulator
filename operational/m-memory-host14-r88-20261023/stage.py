import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='70cc719588df2cf3be9ea7de0b972d84ef8a2bb90be8350020e44314d503564e':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import os,sys,json,base64,hashlib,subprocess,tarfile,time,signal
from pathlib import Path,PurePosixPath
BASE=Path('/mpac/sdicks02/jobs/clasher/M-physical-host14-r87-fix-20261023/r')
SOURCE=Path('/mpac/sdicks02/repos/clasher-M-host14-source-20261023')
def stop(*_):raise RuntimeError('staging interrupted')
for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,stop)
signal.alarm(180)
fetch=None;created=False;failure=None
try:
 assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and os.environ.get('CLASHER_LEASE_JOB')
 assert not Path(os.environ['CLASHER_LEASE_STOP_FILE']).exists()
 # The large environment transfer is already complete; validate it before measurement staging writes.
 import types
 C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__);C.verify_ready(json.loads(FILES['ready-plan.json']))
 BASE.mkdir(parents=True,exist_ok=False);created=True;SOURCE.mkdir(exist_ok=False)
 payload=json.loads(__import__('zlib').decompress(base64.b64decode(PAYLOAD)))
 with (BASE/'payload.b64').open('x') as f:f.write(PAYLOAD)
 with (BASE/'package-pins.json').open('xb') as f:f.write(base64.b64decode(CTX['pins']))
 for name,data in payload['files'].items():
  p=BASE/name;assert not Path(name).is_absolute() and '..' not in Path(name).parts
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('xb') as f:f.write(base64.b64decode(data))
 with (BASE/'archive.tar').open('xb') as f:f.write((Path('/mpac/sdicks02/repos/clasher-M-host14-ready-20261023')/'source.tar').read_bytes())
 assert hashlib.sha256((BASE/'archive.tar').read_bytes()).hexdigest()=='73527481b5010e9a19a1090eee49710f45ae77d3f97a8dc9d1bcb61d40eaae13'
 manifest=json.loads((BASE/'inputs.json').read_bytes())
 with tarfile.open(str(BASE/'archive.tar')) as tar:
  members=tar.getmembers();names=set()
  for x in members:
   p=PurePosixPath(x.name);assert not p.is_absolute() and '..' not in p.parts and (x.isdir() or x.isfile())
   assert x.name not in names;names.add(x.name)
   dest=SOURCE/x.name
   if x.isdir():dest.mkdir(parents=True,exist_ok=True)
   else:
    dest.parent.mkdir(parents=True,exist_ok=True)
    with tar.extractfile(x) as a,dest.open('xb') as b:b.write(a.read())
 for size in ('M',):
  anchor=BASE/'anchors'/size/'anchor.pt';anchor.parent.mkdir(parents=True,exist_ok=True)
  ref='/mpac/sdicks02/repos/clasher-M-host14-ready-20261023/dependencies/refs/mpac/sdicks02/scratch/pretrain-v1-dev/followup-20261022/next-anchors/'+size+'/anchor.pt'
  with anchor.open('xb') as f:f.write(Path(ref).read_bytes())
 with (BASE/'context.json').open('x') as f:json.dump(CTX,f)
 import types
 C=types.ModuleType('common');C.__file__=str(BASE/'common.py');exec(compile(FILES['common.py'],C.__file__,'exec'),C.__dict__)
 m=C.load_r37();C.lease_check();pins={s:C.verify_inputs(s) for s in ('M',)}
 C.write(BASE/'stage-receipt.json',dict(status='pass',utc=C.utc(),pid=os.getpid(),start=m.proc_stat(os.getpid())[4],pins=pins,admission=C.admission(m),cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES']))
except BaseException as ex:failure=repr(ex)
finally:
 # Bounded exact cleanup of the only staging child: its unreaped Popen PID cannot be reused.
 signal.alarm(0);signal.alarm(15)
 try:
  if fetch is not None and fetch.poll() is None:fetch.kill();fetch.wait(timeout=5)
 except BaseException as ex:failure=(failure or '')+'; fetch cleanup: '+repr(ex)
 if failure and created:
  with (BASE/'stage-failed.json').open('x') as f:json.dump(dict(status='failed',error=failure,fetch_pid=fetch.pid if fetch else None,fetch_exit=fetch.returncode if fetch else None,fetch_reaped=fetch is None or fetch.returncode is not None,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())),f,indent=2,sort_keys=True)
 signal.alarm(0)
if failure:print(failure,file=sys.stderr);sys.exit(1)
