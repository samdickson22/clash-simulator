"""Lightweight stdlib coordinator: relay matched control and enforce 40 GPU-h.

Runs on05, reads only small receipts/log tails over SSH, no tensor/data IO.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

WORK='/mpac/sdicks02/repos/clasher-lease/capacity-scan-20261009-v1'
ARMS={'127x13':288,'127x14':384,'127x15':480,'127x16':192}
SNAPSHOT=r'''
import json,sys
from pathlib import Path
w=Path(sys.argv[1]); width=int(sys.argv[2]); out=w/'runs'/('width'+str(width))
result={'width':width}
for name,path in [('launch',w/('width'+str(width)+'-v1-launch.json')),('health',w/('width'+str(width)+'-v1-health.json')),('exit',w/('width'+str(width)+'-v1-exit.json')),('quarter',out/'quarter.json'),('decision',out/'kill-decision.json'),('scan_exit',out/'scan-exit.json'),('complete',out/'complete.json')]:
 if path.exists():result[name]=json.loads(path.read_text())
path=out/'scan-segments.jsonl'
if path.exists():result['segments']=[json.loads(x) for x in path.read_text().splitlines()]
log=out/'train.jsonl'
if log.exists():
 with log.open('rb') as f:
  f.seek(max(0,log.stat().st_size-131072)); lines=f.read().decode().splitlines()
 for x in reversed(lines):
  try:r=json.loads(x)
  except (ValueError,UnicodeError):continue
  if r.get('event')=='step':result['latest_step']=r;break
log=w/('width'+str(width)+'-v1.log')
if log.exists():
 with log.open('rb') as f:
  f.seek(max(0,log.stat().st_size-4096));result['tail']=f.read().decode(errors='replace')[-3000:]
print(json.dumps(result))
'''


def snapshot(item):
    host,width=item
    try:
        r=subprocess.run(['ssh','-o','ConnectTimeout=10',host,'nice','-n','10','python3','-c',
                          __import__('shlex').quote(SNAPSHOT),WORK,str(width)],capture_output=True,text=True,timeout=45)
        if r.returncode:
            raise RuntimeError(r.stderr[-1000:])
        return host,json.loads(r.stdout)
    except Exception as e:
        return host,dict(width=width,error=str(e))


def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def stop_all():
    for host in ARMS:
        subprocess.run(['ssh','-o','ConnectTimeout=10',host,'touch',WORK+'/STOP'],capture_output=True,timeout=30)


def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    prior=json.loads((out/'state.json').read_text()) if (out/'state.json').exists() else {}
    relayed=set(prior.get('control_relayed',[])); stopping=prior.get('stopping',False)
    cached=prior.get('arms',{})
    # Conservative accounting includes staging/supervision time. Actual GPU
    # wall time is separately reported from scan-segments at completion.
    while True:
        with ThreadPoolExecutor(max_workers=4) as pool:
            arms=dict(pool.map(snapshot,ARMS.items()))
        for host,r in list(arms.items()):
            if 'error' in r:
                arms[host]={**cached.get(host,{}),**r}
        cached=arms
        now=datetime.now(timezone.utc); hours=0
        for r in arms.values():
            if 'launch' in r:
                start=datetime.fromisoformat(r['launch']['started_at'])
                end=datetime.fromisoformat(r['exit']['ended_at']) if 'exit' in r else now
                hours+=(end-start).total_seconds()/3600
        control=arms['127x16'].get('quarter')
        if control:
            assert control['rows']==95144680 and control['width']==192
            control_file=out/'control-quarter.json';atomic(control_file,control)
            for host in ('127x13','127x14','127x15'):
                if host not in relayed:
                    dest=WORK+'/runs/control-quarter.json'
                    try:
                        subprocess.run(['ssh',host,'mkdir','-p',WORK+'/runs'],check=True,capture_output=True,timeout=30)
                        subprocess.run(['scp','-q',str(control_file),host+':'+dest+'.partial'],check=True,timeout=30)
                        subprocess.run(['ssh',host,'mv',dest+'.partial',dest],check=True,capture_output=True,timeout=30)
                        relayed.add(host)
                    except Exception as e:
                        arms[host]['relay_error']=str(e)
        if not stopping and (hours>=39.8 or now>=datetime.fromisoformat('2026-10-11T03:00:00+00:00')):
            stop_all();stopping=True
        complete=all('exit' in r for r in arms.values())
        result=dict(at=now.isoformat(),arms=arms,conservative_gpu_hours=hours,
                    control_relayed=sorted(relayed),stopping=stopping,all_exited=complete)
        atomic(out/'state.json',result)
        with (out/'observations.jsonl').open('a') as f:
            f.write(json.dumps(dict(at=result['at'],hours=hours,rows={h:r.get('latest_step',{}).get('rows') for h,r in arms.items()},errors={h:r.get('error') for h,r in arms.items()}))+'\n')
        if complete:
            atomic(out/'complete.json',result);return
        time.sleep(30)


if __name__=='__main__':main()
