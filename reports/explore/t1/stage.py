"""Stage T1 from frozen S1 runtime; never modify the inherited job."""
import argparse,shutil,socket
from pathlib import Path
from common import sha,read,write,utc,plan

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True);p.add_argument('--base',type=Path,default=Path('/mpac/sdicks02/jobs/clasher/s1-20261010-r1'));a=p.parse_args()
 assert socket.gethostname() in ('127x01','127x03','127x08')
 a.job.mkdir(parents=True,exist_ok=True);assert not (a.job/'repo').exists(),'never overwrite a staged runtime'
 for name in ('repo','native','native-source','inputs','corpus'):
  shutil.copytree(a.base/name,a.job/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 shutil.copytree(a.overlay,a.job/'repo/reports/explore/t1')
 inherited=read(a.base/'runtime-pin.json')
 for name,h in inherited['files'].items():assert sha(a.job/'repo'/name)==h,name
 for name,h in inherited['native_source'].items():assert sha(a.job/'native-source'/name)==h,name
 for name,h in read(a.base/'student-source-verified.json')['files'].items():assert sha(a.job/'repo'/name)==h,name
 shutil.copyfile(a.base/'runtime-pin.json',a.job/'inherited-runtime-pin.json')
 cfg=read(a.job/'repo/reports/explore/t1/plan.json')
 for name,h in [('native/clasher_core.abi3.so',cfg['source_reference']['native_sha256']),('inputs/R3a.pt',cfg['student']['checkpoint_sha256']),('inputs/main02.pt',cfg['policy']['checkpoint_sha256']),('inputs/R3a-calibration.json',cfg['student']['calibration_sha256'])]:assert sha(a.job/name)==h,name
 write(a.job/'staging.json',dict(utc=utc(),host=socket.gethostname(),base=str(a.base),inherited_runtime_pin_sha256=sha(a.base/'runtime-pin.json'),inherited_files_verified=len(inherited['files']),student_source_sha256=sha(a.base/'student-source-verified.json'),native_sha256=cfg['source_reference']['native_sha256']))
if __name__=='__main__':main()
