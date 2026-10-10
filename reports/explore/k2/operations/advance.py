"""Operational driver outside frozen snapshot: launch at nice0, timing/reduction at nice10."""
import argparse,json,os,socket,subprocess
from pathlib import Path
from supervise import processes,release_gate,utc

def run(job,*args):
    return subprocess.run(['nice','-n',str(10-os.getpriority(os.PRIO_PROCESS,0)),'bash',str(job/'repo/reports/explore/k2/runtime.sh'),*map(str,args)],check=True)

def phase_exit(job,phase):
    path=job/phase/'supervisor-exit.json'
    if not path.exists():return False
    launch=json.loads((job/phase/'launch.json').read_text());exited=json.loads(path.read_text())
    assert exited['returncode']==0 and exited['reason'] is None,exited
    groups={launch['supervisor_pgid'],launch['child_pgid']}
    if any(r['pgid'] in groups for r in processes()):return False
    return True

def launch(job,phase):
    claim=job/(phase+'-launch-claim')
    if claim.exists():
        assert (job/(phase+'-supervisor-pid.json')).exists(),'interrupted launch needs identity investigation; do not retry'
        identity=json.loads((job/(phase+'-supervisor-pid.json')).read_text())
        assert any(r['pgid']==identity['pgid'] for r in processes()) or (job/phase/'supervisor-exit.json').exists(),'launched process died without exit; investigate'
        return False
    subprocess.run(['bash',str(job/'repo/reports/explore/k2/launch.sh'),phase],check=True)
    return True

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);a=ap.parse_args();job=a.job
    assert socket.gethostname()=='127x03' and os.sched_getaffinity(0)=={59}
    assert os.getpriority(os.PRIO_PROCESS,0)==0 and os.sched_getscheduler(0)==os.SCHED_OTHER
    assert (job/'runtime-pin.json').exists() and (job/'freeze.json').exists()
    release_gate(job)
    if not phase_exit(job,'smoke'):
        fresh=launch(job,'smoke');print(json.dumps(dict(stage='smoke',fresh_launch=fresh,utc=utc())));return
    if not (job/'SMOKE-PASS').exists():
        run(job,'reports/explore/k2/reduce.py','--games',job/'smoke/games','--out',job/'smoke-summary.json','--smoke')
        smoke=json.loads((job/'smoke-summary.json').read_text());receipt=json.loads((job/'smoke/receipt.json').read_text())
        assert smoke['checks']['games']==24 and receipt['games']==24 and receipt['terminal']
        (job/'SMOKE-PASS').write_text(utc()+'\n')
    if not phase_exit(job,'reporting'):
        fresh=launch(job,'reporting');print(json.dumps(dict(stage='reporting',fresh_launch=fresh,utc=utc())));return
    if not (job/'POSTPROCESSED').exists():
        os.setpriority(os.PRIO_PROCESS,0,10)
        run(job,'reports/explore/k2/reduce.py','--games',job/'reporting/games','--out',job/'results.json')
        run(job,'reports/explore/k2/gc_summary.py','--games',job/'reporting/games','--worker-log',job/'reporting/worker.log','--results',job/'results.json','--out',job/'gc-maintenance.json')
        run(job,'reports/explore/k2/execution_audit.py','--job',job,'--out',job/'execution.json')
        run(job,job/'host_audit_external.py','--job',job,'--out',job/'host-audit-final.json')
        (job/'POSTPROCESSED').write_text(utc()+'\n')
    print(json.dumps(dict(stage='ready_for_local_report_commit_release',utc=utc())))
if __name__=='__main__':main()
