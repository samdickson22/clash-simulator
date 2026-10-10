"""Bounded stage advance after qualification/freeze; owns no persistent schedule."""
import argparse,json,os,subprocess
from pathlib import Path
from host_audit import processes,release_gate,utc

def execute(job,*args):
    subprocess.run(['nice','-n',str(10-os.getpriority(os.PRIO_PROCESS,0)),'taskset','-c','39','bash',str(job/'repo/reports/explore/s1/runtime.sh'),*map(str,args)],check=True)

def exited(job,phase):
    path=job/phase/'supervisor-exit.json'
    if not path.exists():return False
    result=json.loads(path.read_text());assert result['returncode']==0 and result['reason'] is None,result
    launch=json.loads((job/phase/'launch.json').read_text())
    groups={launch['supervisor_pgid'],launch['child_pgid']}
    return not any(r['pgid'] in groups for r in processes())

def launch(job,phase):
    if (job/(phase+'-launch-claim')).exists():
        receipt=job/(phase+'-supervisor-pid.json');assert receipt.exists(),'interrupted launch needs identity investigation'
        ident=json.loads(receipt.read_text());assert any(r['pgid']==ident['pgid'] for r in processes()) or (job/phase/'supervisor-exit.json').exists(),'dead phase without exit needs investigation; no auto retry'
        return False
    subprocess.run(['bash',str(job/'repo/reports/explore/s1/launch.sh'),phase],check=True);return True

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();j=a.job
    assert os.uname().nodename=='127x01' and os.getpriority(os.PRIO_PROCESS,0)==0
    release_gate(j)
    if not exited(j,'smoke'):
        fresh=launch(j,'smoke');print(json.dumps(dict(utc=utc(),phase='smoke',fresh=fresh)));return
    if not (j/'SMOKE-PASS').exists():
        execute(j,'reports/explore/s1/reduce.py','--games',j/'smoke/games','--out',j/'smoke-summary.json','--smoke')
        smoke=json.loads((j/'smoke-summary.json').read_text());assert smoke['checks']['games']==40
        (j/'SMOKE-PASS').write_text(utc()+'\n')
    if not exited(j,'reporting'):
        fresh=launch(j,'reporting');print(json.dumps(dict(utc=utc(),phase='reporting',fresh=fresh)));return
    if not (j/'POSTPROCESSED').exists():
        execute(j,'reports/explore/s1/reduce.py','--games',j/'reporting/games','--out',j/'results.json')
        execute(j,'reports/explore/s1/gc_summary.py','--games',j/'reporting/games','--worker-log',j/'reporting/worker.log','--results',j/'results.json','--out',j/'gc-maintenance.json')
        execute(j,'reports/explore/s1/execution_audit.py','--job',j,'--out',j/'execution.json')
        (j/'POSTPROCESSED').write_text(utc()+'\n')
    print(json.dumps(dict(utc=utc(),phase='publication_pending')))
if __name__=='__main__':main()
