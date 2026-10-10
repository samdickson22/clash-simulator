"""One detached auxiliary phase: exact argv, PID/PGID, whole process-tree CPU."""
import argparse,json,os,resource,subprocess,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);ap.add_argument('--name',required=True);ap.add_argument('command',nargs=argparse.REMAINDER);a=ap.parse_args()
    assert os.uname().nodename=='127x01' and a.command and a.command[0]=='--'
    assert os.getpriority(os.PRIO_PROCESS,0)==10 and os.sched_getscheduler(0)==os.SCHED_OTHER
    start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    command=a.command[1:]
    rc=subprocess.run(command).returncode
    own=resource.getrusage(resource.RUSAGE_SELF);after=resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime+own.ru_utime+own.ru_stime
    (a.job/'meters').mkdir(exist_ok=True)
    (a.job/'meters'/(a.name+'.json')).write_text(json.dumps(dict(utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),pid=os.getpid(),pgid=os.getpgrp(),command=command,returncode=rc,whole_tree_cpu_seconds=cpu,wall_seconds=time.monotonic()-start,accounting='non-nested auxiliary tree once; no sum of child diagnostics'),indent=2)+'\n')
    raise SystemExit(rc)
if __name__=='__main__':main()
