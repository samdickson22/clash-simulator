"""Lightweight owned-worker supervisor. No signals are sent to other processes."""
from pathlib import Path
import fcntl,json,os,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
lock=(HERE/'launcher.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
os.chdir(ROOT);python=str(ROOT/'.venv/bin/python')
# Refuse to overwrite status for an already active independent worker.
locks=[]
for i in range(3):
    f=(HERE/f'worker{i}.lock').open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(f)
for f in locks:f.close()
children={};logs=[]
for i in range(3):
    exitfile=HERE/f'worker{i}.exit'
    if exitfile.exists():exitfile.rename(HERE/f'worker{i}.exit.previous-{time.time_ns()}')
    log=(HERE/f'worker{i}.log').open('a');logs.append(log)
    children[i]=subprocess.Popen(['nice','-n','10',python,'-B',str(HERE/'evaluate.py'),'--worker',str(i)],stdout=log,stderr=subprocess.STDOUT)
(HERE/'launcher-children.json').write_text(json.dumps({str(i):p.pid for i,p in children.items()})+'\n')
finished={}
while len(finished)<3:
    for i,p in children.items():
        if i not in finished and p.poll() is not None:
            finished[i]=p.returncode;(HERE/f'worker{i}.exit').write_text(str(p.returncode)+'\n')
    subprocess.run([python,'-B',str(HERE/'status.py')],check=True)
    if len(finished)<3:time.sleep(30)
for log in logs:log.close()
rc=int(any(finished.values()))
if not rc:
    with (HERE/'analyze.log').open('a') as log:rc=subprocess.run(['nice','-n','10',python,'-B',str(HERE/'analyze.py')],stdout=log,stderr=subprocess.STDOUT).returncode
(HERE/'launcher.exit').write_text(str(rc)+'\n')
raise SystemExit(rc)
