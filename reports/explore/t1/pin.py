"""Bind inherited runtime plus T1 owned bytes and freeze authorization."""
import argparse
from pathlib import Path
from common import sha,read,write,utc,plan

def verify(j):
 p=read(j/'runtime-pin.json')
 for name,h in p['files'].items():assert sha(j/'repo'/name)==h,name
 for name,h in p['native_source'].items():assert sha(j/'native-source'/name)==h,name
 for name,h in p['inputs'].items():assert sha(j/name)==h,name
 return p

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();j=a.job
 inherited=read(j/'inherited-runtime-pin.json');files=dict(inherited['files'])
 for name,h in files.items():assert sha(j/'repo'/name)==h,name
 d=j/'repo/reports/explore/t1'
 files.update({str(p.relative_to(j/'repo')):sha(p) for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.sh','.json','.md') and 'receipts' not in p.parts})
 inputs={n:sha(j/n) for n in ('native/clasher_core.abi3.so','inputs/R3a.pt','inputs/main02.pt','inputs/R3a-calibration.json')}
 cfg=plan();assert inputs['native/clasher_core.abi3.so']==cfg['source_reference']['native_sha256'];assert inputs['inputs/R3a.pt']==cfg['student']['checkpoint_sha256'];assert inputs['inputs/main02.pt']==cfg['policy']['checkpoint_sha256'];assert inputs['inputs/R3a-calibration.json']==cfg['student']['calibration_sha256']
 write(j/'runtime-pin.json',dict(utc=utc(),files=files,native_source=inherited['native_source'],inputs=inputs,inherited_runtime_pin_sha256=sha(j/'inherited-runtime-pin.json'),plan_sha256=sha(d/'plan.json')))
 verify(j)
if __name__=='__main__':main()
