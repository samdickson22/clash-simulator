"""PREREG-K4S: stage the runtime from the inherited S1 runtime (T1's inherited pin f81f3655...).

T1's stage.py copied from the S1 job on 01. On 03 the identical S1 runtime is held by the X4S2 job
(its repo/native/native-source/inputs/corpus match S1 runtime-pin-r2, sha256 f81f3655..., which is
T1's inherited_runtime_pin_sha256). This copies it, drops the unpinned exploration overlays,
verifies every pinned file, native source and input, then adds the K4S overlay. Never modifies the base.
"""
import argparse,shutil,socket
from pathlib import Path
from common import sha,read,write,utc

INHERITED_PIN_SHA256='f81f36558179458ba74edd3a57f44ad3395f4452a93c64d3102c4f4d5048a80d'

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True)
 p.add_argument('--base',type=Path,default=Path('/mpac/sdicks02/jobs/clasher/x4s2-20261011'))
 p.add_argument('--inherited-pin',type=Path,default=Path('/mpac/sdicks02/jobs/clasher/x4s-20261011/s1-runtime-pin-r2.json'));a=p.parse_args()
 assert socket.gethostname() in ('127x01','127x03','127x04','127x08')
 assert sha(a.inherited_pin)==INHERITED_PIN_SHA256
 a.job.mkdir(parents=True,exist_ok=True);assert not (a.job/'repo').exists(),'never overwrite a staged runtime'
 skip=shutil.ignore_patterns('__pycache__','*.pyc')
 def repo_ignore(d,names):
  out=set(skip(d,names))
  if Path(d)==a.base/'repo/reports/explore':out|={n for n in names if n in ('x4s','x4s2','k4s-confirm','t1')}
  return out
 shutil.copytree(a.base/'repo',a.job/'repo',ignore=repo_ignore)
 for name in ('native','native-source','inputs','corpus'):shutil.copytree(a.base/name,a.job/name,ignore=skip)
 inherited=read(a.inherited_pin)
 for name,h in inherited['files'].items():assert sha(a.job/'repo'/name)==h,name
 for name,h in inherited['native_source'].items():assert sha(a.job/'native-source'/name)==h,name
 shutil.copytree(a.overlay,a.job/'repo/reports/explore/k4s-confirm',ignore=skip)
 shutil.copyfile(a.inherited_pin,a.job/'inherited-runtime-pin.json')
 cfg=read(a.job/'repo/reports/explore/k4s-confirm/plan.json')
 for name,h in [('native/clasher_core.abi3.so',cfg['source_reference']['native_sha256']),('inputs/R3a.pt',cfg['student']['checkpoint_sha256']),('inputs/main02.pt',cfg['policy']['checkpoint_sha256']),('inputs/R3a-calibration.json',cfg['student']['calibration_sha256'])]:assert sha(a.job/name)==h,name
 assert inherited['native_sha256']==cfg['source_reference']['native_sha256']
 write(a.job/'staging.json',dict(utc=utc(),host=socket.gethostname(),base=str(a.base),inherited_runtime_pin=str(a.inherited_pin),inherited_runtime_pin_sha256=INHERITED_PIN_SHA256,inherited_files_verified=len(inherited['files']),native_source_verified=len(inherited['native_source']),native_sha256=cfg['source_reference']['native_sha256'],corpus_sha256={f.name:sha(f) for f in sorted((a.job/'corpus').iterdir())}))
if __name__=='__main__':main()
