"""Own immutable runtime copy after R3's exclusive reservation is returned."""
import argparse,hashlib,json,os,shutil,socket,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--overlay',type=Path,required=True);a=ap.parse_args()
    assert socket.gethostname()=='127x01'
    from host_audit import release_gate,foreign_compute,processes
    release_gate(a.job);assert not foreign_compute(a.job,processes())
    base=Path('/mpac/sdicks02/jobs/clasher/k-anytime-20261010-r1')
    assert not (a.job/'repo').exists(),'no snapshot overwrite'
    shutil.copytree(base/'repo',a.job/'repo',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(base/'native',a.job/'native')
    shutil.copytree(base/'native-source',a.job/'native-source')
    dest=a.job/'repo/reports/explore/s1';shutil.copytree(a.overlay,dest,dirs_exist_ok=False)
    r3=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
    shutil.copytree(r3/'student-source',a.job/'repo/student-source')
    (a.job/'inputs').mkdir(exist_ok=True)
    shutil.copyfile(r3/'fits/R3a/step-00002500.pt',a.job/'inputs/R3a.pt')
    shutil.copyfile(r3/'inputs/main02.pt',a.job/'inputs/main02.pt')
    shutil.copyfile(r3/'offline/R3a-calibration.json',a.job/'inputs/R3a-calibration.json')
    shutil.copyfile(base/'runtime-pin.json',a.job/'inherited-runtime-pin.json')
    cfg=json.loads((dest/'plan.json').read_text())
    assert sha(a.job/'native/clasher_core.abi3.so')==cfg['source_reference']['native_sha256']
    assert sha(a.job/'inputs/R3a.pt')==cfg['student']['checkpoint_sha256']
    assert sha(a.job/'inputs/main02.pt')==cfg['policy']['checkpoint_sha256']
    assert sha(a.job/'inputs/R3a-calibration.json')==cfg['student']['calibration_sha256']
    (a.job/'staging.json').write_text(json.dumps(dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),base=str(base),student_source=str(r3),files={str(p.relative_to(a.job)):sha(p) for p in (a.job/'native/clasher_core.abi3.so',a.job/'inputs/R3a.pt',a.job/'inputs/main02.pt',a.job/'inputs/R3a-calibration.json')}),indent=2)+'\n')
if __name__=='__main__':main()
