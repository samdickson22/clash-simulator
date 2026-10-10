"""Require inherited source/adapter/native equality; pin final owned freeze."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();j=a.job;repo=j/'repo'
    inherited=json.loads((j/'inherited-runtime-pin.json').read_text())
    for name,h in inherited['files'].items():
        assert sha(repo/name)==h,('inherited source mismatch',name)
    for name,h in inherited['native_source'].items():assert sha(j/'native-source'/name)==h,name
    dest=repo/'reports/explore/s1';cfg=json.loads((dest/'plan.json').read_text());f=json.loads((dest/'FROZEN.json').read_text())
    for name,h in f['files'].items():assert sha(repo/name)==h,name
    assert sha(j/'native/clasher_core.abi3.so')==cfg['source_reference']['native_sha256']==inherited['native_sha256']
    for tag in ('policy','student'):assert sha(Path(cfg[tag]['checkpoint']))==cfg[tag]['checkpoint_sha256']
    assert sha(j/'inputs/R3a-calibration.json')==cfg['student']['calibration_sha256']
    student=json.loads((j/'student-source-verified.json').read_text())
    for name,h in student['files'].items():assert sha(repo/name)==h,name
    files={name:sha(repo/name) for name in inherited['files']}
    files.update({str(p.relative_to(repo)):sha(p) for p in sorted(dest.glob('*.py'))})
    files.update({str(p.relative_to(repo)):sha(p) for p in sorted(dest.glob('*.sh'))})
    files.update({str(p.relative_to(repo)):sha(p) for p in (dest/'plan.json',dest/'FROZEN.json')})
    for p in (repo/'student-source').rglob('*.py'):files[str(p.relative_to(repo))]=sha(p)
    result=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),freeze_commit=json.loads((j/'freeze.json').read_text())['commit'],files=files,native_sha256=sha(j/'native/clasher_core.abi3.so'),native_source=inherited['native_source'],plan_sha256=sha(dest/'plan.json'),FROZEN_sha256=sha(dest/'FROZEN.json'),checkpoint_sha256=cfg['student']['checkpoint_sha256'],policy_sha256=cfg['policy']['checkpoint_sha256'],calibration_sha256=cfg['student']['calibration_sha256'])
    (j/'runtime-pin.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
