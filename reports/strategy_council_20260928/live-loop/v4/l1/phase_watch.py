"""Receipt-only Phase A watcher, 15-minute cadence, hard 12-hour deadline.

Never opens any match payload or fabricates T1 completion. A ready signal is not
training admission: formal_guard.py and all preparation/selection gates still run.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import time

REMOTE = r'''
import collections,hashlib,json,pathlib,time
base=pathlib.Path('/mpac/sdicks02/repos/clasher')
v4=base/'reports/strategy_council_20260928/live-loop/v4'
counts=collections.Counter();events=collections.Counter();seconds=0.;receipts={}
for p in sorted(pathlib.Path('/mpac/sdicks02/repos/clasher-v4-data/matches').glob('*/receipt.json')):
    r=json.loads(p.read_text())
    if r.get('split') not in ('train','validation','heldout'):continue
    counts[r['split']]+=1;events[r['split']]+=r.get('accepted_opponent_events',0)
    seconds+=r.get('elapsed_emulator_seconds',0);receipts[r['episode']]=hashlib.sha256(p.read_bytes()).hexdigest()
result=dict(time=time.time(),matches=dict(counts),opponent_events=dict(events),emulator_seconds=seconds,receipts=receipts)
for n in ('pipeline-state.json','phase-a-exit.json'):
    p=v4/n;result[n]=json.loads(p.read_text()) if p.exists() else None
p=v4/'T1-PROGRESS.md';result['t1_progress_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();result['t1_progress_tail']=p.read_text()[-5000:]
print(json.dumps(result))
'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--deadline',type=float,required=True);p.add_argument('--once',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);stopping=False
    latest=a.output/'latest.json'
    if a.once and latest.exists() and time.time()-json.loads(latest.read_text())['time']<900:
        print('Receipt-only poll skipped: previous poll was less than 15 minutes ago',flush=True);return
    def stop(*args):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    next_poll=time.time()
    while not stopping and time.time()<=a.deadline:
        if time.time()<next_poll:
            time.sleep(min(30,next_poll-time.time(),max(0,a.deadline-time.time())))
            continue
        now=time.time()
        try:
            proc=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','127x01','python3 -'],
                                input=REMOTE,text=True,capture_output=True,timeout=90,check=True)
            record=json.loads(proc.stdout)
            state=record['pipeline-state.json'] or {};ex=record['phase-a-exit.json'] or {}
            record['producer_complete']=state.get('stage')=='complete' and ex.get('code')==0
            record['coverage_met']=record['matches'].get('heldout',0)>=20 and record['opponent_events'].get('heldout',0)>=1500
            record['status']='producer-complete-needs-verification' if record['producer_complete'] else 'waiting'
            record['heldout_payloads_opened']=False
        except Exception as exc:record=dict(time=now,status='read-error',error=str(exc),heldout_payloads_opened=False)
        record['deadline']=a.deadline
        name=datetime.datetime.fromtimestamp(now,datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        (a.output/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        tmp=a.output/'latest.tmp';tmp.write_text(json.dumps(record,indent=2)+'\n');tmp.replace(a.output/'latest.json')
        print(json.dumps({k:v for k,v in record.items() if k not in ('receipts','t1_progress_tail')}),flush=True)
        if record.get('producer_complete') or a.once:return
        next_poll=now+900
    (a.output/'stopped.json').write_text(json.dumps(dict(time=time.time(),status='signal' if stopping else '12-hour-timeout',heldout_opened=False))+'\n')


if __name__=='__main__':main()
