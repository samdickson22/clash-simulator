"""Temporary outcome-blind backup of reachable r2 nodes after 07 transport loss.
No analysis, reassignment or frozen-file edits. Stops after 04/08 supervisors
finish, on six-hour operational timeout, or on receipt validation failure.
"""
from pathlib import Path
import hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parents[1]
JOBS=Path('/mpac/sdicks02/jobs/clasher')
HOSTS=('127x04','127x08')
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ConnectionAttempts=1']
END=time.time()+6*3600
EXPECTED='3ad63c0a7ad1634bac32bf5b031a7a312013497d8863aeaa3b0e2b0e077e5677'
assert hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()==EXPECTED
def write(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data)+'\n');tmp.replace(path)
while True:
    statuses={};errors=[]
    for host in HOSTS:
        for pattern in ('confirmation/','worker-*-done.json','launch-*.json'):
            dest=HERE/'confirmation' if pattern=='confirmation/' else HERE
            dest.mkdir(exist_ok=True)
            cmd=['rsync','-a','--timeout=120','--exclude=*.tmp','-e',' '.join(SSH)]
            if pattern=='confirmation/':cmd+=['--ignore-existing']
            cmd+=[f'{host}:{HERE}/{pattern}',str(dest)+'/']
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=150)
            if p.returncode not in (0,23):errors.append(dict(host=host,operation=pattern,exit=p.returncode,error=p.stderr[-1000:]))
        code=f"""from pathlib import Path
import json
j=Path('/mpac/sdicks02/jobs/clasher');s=Path('{HERE}')
d=json.loads((s/'launch-{host}-r2.json').read_text())
finished=[];failed=[]
for w in d['workers']:
 p=j/(w['label']+'.exit')
 if p.exists():
  finished.append(w['index'])
  if p.read_text().strip()!='0':failed.append(w['index'])
p=j/'s1-confirm-node-{host}-r2.exit'
print(json.dumps(dict(completed_partitions=len(finished),expected_partitions=len(d['workers']),failures=failed,supervisor_exit=p.read_text().strip() if p.exists() else None)))
"""
        p=subprocess.run(SSH+[host,'/mpac/sdicks02/repos/clasher/.venv/bin/python','-B','-'],input=code,capture_output=True,text=True,timeout=30)
        if p.returncode:errors.append(dict(host=host,operation='status',exit=p.returncode,error=p.stderr[-1000:]))
        else:statuses[host]=json.loads(p.stdout)
    p=subprocess.run([sys.executable,'-B',str(HERE/'operations/technical_status.py')],capture_output=True,text=True,check=True)
    technical=json.loads(p.stdout)
    out=dict(utc=time.time(),scope=list(HOSTS),unreachable_host='127x07',nodes=statuses,errors=errors,technical=technical,analysis_permitted=False)
    write(HERE/'operations/reachable-monitor-r2.json',out)
    print(json.dumps(out),flush=True)
    if len(statuses)==len(HOSTS) and all(s['supervisor_exit']=='0' and s['completed_partitions']==s['expected_partitions'] and not s['failures'] for s in statuses.values()) and not errors:
        print('Reachable-node backup complete; 127x07 remains unresolved; analysis forbidden',flush=True);break
    if time.time()>=END:raise RuntimeError('Six-hour backup window exhausted; inspect exact resume state')
    time.sleep(60)
