"""Bind each host's qualification to exact source, plan and immutable native inputs."""
import argparse
from pathlib import Path
from common import sha,write,read,utc,plan

def inventory(j):
 d=j/'repo/reports/explore/t1';files={str(p.relative_to(j/'repo')):sha(p) for p in sorted(d.glob('*')) if p.suffix in ('.py','.sh')}
 files['reports/explore/t1/plan.json']=sha(d/'plan.json')
 return dict(files=files,native_sha256=sha(j/'native/clasher_core.abi3.so'),student_sha256=sha(j/'inputs/R3a.pt'),calibration_sha256=sha(j/'inputs/R3a-calibration.json'),v1_sha256=sha(j/'inputs/main02.pt'))

def main():
 p=argparse.ArgumentParser();p.add_argument('--job',type=Path,required=True);p.add_argument('--record',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args();r=inventory(a.job);target=a.job/'qualification-source-before.json'
 if a.record:write(target,dict(utc=utc(),**r))
 if a.verify:
  before=read(target);assert all(before[k]==v for k,v in r.items()),'qualification source changed'
  for name in ('QUALIFIED','BELIEF-QUALIFIED','TESTS-PASS'):assert (a.job/name).exists()
  write(a.job/'qualification-source-binding.json',dict(utc=utc(),**r,receipts={k:sha(a.job/k) for k in ('qualification.json','belief-qualification.json','guard-support-qualification.json')},source_stable=True))
if __name__=='__main__':main()
