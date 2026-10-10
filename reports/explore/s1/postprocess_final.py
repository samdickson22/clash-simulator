"""Meterable completion driver; runs only the sealed reducers and read-only check."""
import argparse,hashlib,json,os,socket,subprocess,sys
from pathlib import Path
from host_audit import foreign_compute,processes,release_gate,utc
from supervise import runtime_guard

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True)
    ap.add_argument('--verifier-sha256',required=True);a=ap.parse_args();j=a.job
    assert socket.gethostname()=='127x01' and os.sched_getaffinity(0)=={39}
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    release_gate(j);pin=runtime_guard(j);census=processes();assert not foreign_compute(j,census)
    phase=j/'reporting';launch=json.loads((phase/'launch.json').read_text())
    end=json.loads((phase/'supervisor-exit.json').read_text());receipt=json.loads((phase/'receipt.json').read_text())
    assert end['returncode']==0 and end['reason'] is None
    assert receipt['games']==receipt['fresh']==3000 and receipt['terminal']
    assert len(list((phase/'games').glob('*.json')))==3000 and len(list((phase/'blocks').glob('*.json')))==600
    assert not [r for r in census if r['pgid'] in (launch['supervisor_pgid'],launch['child_pgid'])]
    assert launch['freeze_commit']==pin['freeze_commit'] and launch['plan_sha256']==pin['plan_sha256']
    dest=j/'repo/reports/explore/s1';verifier=dest/'verify_statistics.py'
    assert hashlib.sha256(verifier.read_bytes()).hexdigest()==a.verifier_sha256
    assert not (j/'results.json').exists() and not (j/'ANALYSIS-COMPLETE').exists(),'no automatic analysis retry'
    (j/'analysis-barrier.json').write_text(json.dumps(dict(utc=utc(),games=3000,complete_blocks=600,
        original_reporting_groups_absent=True,source_pin_verified=True,
        freeze_commit=pin['freeze_commit'],verifier_sha256=a.verifier_sha256,
        outcome_reduction_opened_only_after_complete_barrier=True),indent=2)+'\n')
    def run(name,*args):subprocess.run([sys.executable,'-B',str(dest/name),*map(str,args)],check=True)
    run('reduce.py','--games',phase/'games','--out',j/'results.json')
    run('gc_summary.py','--games',phase/'games','--worker-log',phase/'worker.log','--results',j/'results.json','--out',j/'gc-maintenance.json')
    run('verify_statistics.py','--games',phase/'games','--results',j/'results.json','--out',j/'statistics-verification.json')
    runtime_guard(j)
    (j/'ANALYSIS-COMPLETE').write_text(utc()+'\n')
if __name__=='__main__':main()
