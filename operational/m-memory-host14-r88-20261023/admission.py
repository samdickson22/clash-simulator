import sys
if sys.flags.optimize:raise RuntimeError('R64 requires optimization 0')
if len(sys.argv)>1 and len(sys.argv[1].encode())>126000:raise RuntimeError('packed admission argument cap')
import hashlib
if hashlib.sha256(globals().get('R64_GATE_BYTES',b'')).hexdigest()!='70cc719588df2cf3be9ea7de0b972d84ef8a2bb90be8350020e44314d503564e':raise RuntimeError('R64 verified bootstrap required')
exec(compile(R64_GATE_BYTES,'gate.py','exec'))
_,FILES=R64_CHECK(CTX,PAYLOAD)
R77_ARGUMENTS(CTX,PAYLOAD)
import socket
if socket.gethostname().split('.')[0]!='127x14':raise RuntimeError('R64 host14 required')
import types,json,os,time
from pathlib import Path
C=types.ModuleType('common');exec(compile(FILES['common.py'],'common.py','exec'),C.__dict__)
m=C.load_r37(CTX)
assert m.host()=='127x14'
a=types.SimpleNamespace(**json.loads(sys.argv[1]))
assert (a.name,a.workers,a.pss_gb,a.gpu_gb,a.grace,a.cwd) in [('M-host14-stage-20261023',6,2,0,120,m.STATE_ROOT),('M-host14-measure-20261023-once',12,4,38,120,m.STATE_ROOT)]
st=C.state(m)
class ExclusiveAdmission:
 def __getattr__(self,n):return getattr(st,n)
 def lock(self,name,block=True):
  lk=st.lock(name,block)
  if name not in ('state.lock','generation.lock'):return lk
  try:
   C.admission(m,workers=a.workers,pss_gb=a.pss_gb)
   recs=st.records();assert not any(r['state'] in ('intent','uncertain','stopping') for r in recs.values())
   jobs=m.job_discover(m.host(),recs,m.job_scan(m.host()),m.boot_id())
   assert not any(v and C.gpu_contract(recs[n])>0 for n,v in jobs.items()),'BC/other GPU admission won; defer without exposure'
   assert not jobs.get('M-host14-stage-20261023'),'own stage must be exactly gone before next admission'
   if name=='generation.lock' and a.gpu_gb:
    # Both locks are held; competing R37 admission cannot pass between this check and spawn.
    import subprocess
    code=R64_BOOT('exposure.py',CTX,PAYLOAD)
    p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','ControlMaster=no','-o','ControlPath=none','-o','StrictHostKeyChecking=yes','127x05','timeout 15s taskset -c 0-31 nice -n 15 /bin/python3 -I -B -'],input=code,capture_output=True,text=True,timeout=20)
    assert p.returncode==0,'global exposure refused or ambiguous: '+p.stderr
    C.write(Path('/mpac/sdicks02/jobs/clasher/r64-M-new-measurement.exposure'),dict(host=m.host(),name=a.name,epoch=time.time(),review=CTX['review'],central_host='127x05',automatic_retry=False))
   return lk
  except BaseException:
   if lk is not None:lk.close()
   raise
m.admit(a,ExclusiveAdmission(),m.LEASE_DIR+'/127x14.json')
