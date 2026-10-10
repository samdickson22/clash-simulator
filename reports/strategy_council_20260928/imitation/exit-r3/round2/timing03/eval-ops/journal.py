"""Durable PID/PGID records, serialized across owned scientific children."""
import fcntl,json,os,subprocess
from pathlib import Path
def record(job,role,**fields):
    j=Path(job);lock=(j/'EVAL-PGIDS.lock').open('a')
    with lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        p=j/'EVAL-PGIDS.json';v=json.loads(p.read_text()) if p.exists() else []
        v.append(dict(pid=os.getpid(),pgid=os.getpgrp(),role=role,utc=subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),**fields))
        temp=p.with_suffix('.tmp');temp.write_text(json.dumps(v,indent=2)+'\n');temp.replace(p)
