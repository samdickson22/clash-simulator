"""Hash the copied student source against R3's frozen evaluation inventory."""
import argparse,hashlib,json,subprocess
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();j=a.job
    r3=Path('/mpac/sdicks02/jobs/clasher/exit-r3-20261010-r2')
    frozen=json.loads((r3/'evaluation-freeze.json').read_text());files=frozen['home_files'];checked={}
    for p in (j/'repo/student-source').rglob('*.py'):
        name='student-source/'+str(p.relative_to(j/'repo/student-source'))
        assert name in files and sha(p)==files[name],name
        checked[str(p.relative_to(j/'repo'))]=sha(p)
    assert checked and any(n.endswith('exit_r3/network.py') for n in checked)
    result=dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),R3_freeze_sha256=sha(r3/'evaluation-freeze.json'),files=checked)
    (j/'student-source-verified.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
