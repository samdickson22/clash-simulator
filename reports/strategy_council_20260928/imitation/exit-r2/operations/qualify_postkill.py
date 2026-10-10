"""Metadata-only home03 qualification. Exploration; NEVER ADOPTABLE."""
import argparse,ast,os,resource,socket,subprocess,sys,time
from pathlib import Path
from imitation.exit_r1.rows import sha,write_json
from postkill_admission import labelled
FILES=('postkill_admission.py','k_postkill_sdefault.py','game_worker_postkill.py','postkill_block_worker.py','game_pool_postkill.py','reduce_postkill.py','seed_audit_postkill.py','test_postkill.py','qualify_postkill.py')
def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);j=Path(p.parse_args().job);start=time.monotonic()
    assert socket.gethostname().split('.')[0]=='127x03' and os.sched_getaffinity(0)=={63} and os.sched_getscheduler(0)==os.SCHED_IDLE and os.getpriority(os.PRIO_PROCESS,0)>=10
    for name in FILES:ast.parse((j/'ops'/name).read_text())
    rc=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(j/'ops/test_postkill.py')]).returncode
    u=resource.getrusage(resource.RUSAGE_SELF);v=resource.getrusage(resource.RUSAGE_CHILDREN)
    write_json(j/f'postkill-code-qualification-{os.getpid()}.json',labelled(dict(passed=rc==0,tests=12,exit_code=rc,files={name:sha(j/'ops'/name) for name in FILES},utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),parent_cpu_seconds=u.ru_utime+u.ru_stime,children_cpu_seconds=v.ru_utime+v.ru_stime,wall_seconds=time.monotonic()-start,no_games=True,no_policy_inference=True)))
    raise SystemExit(rc)
if __name__=='__main__':main()
