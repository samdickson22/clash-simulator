"""Light bounded orchestration for complete-only development summaries."""
from pathlib import Path
import json,subprocess,time,socket
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
def call(args,**kw):return subprocess.run(args,check=True,text=True,timeout=180,**kw)
def remote(host,args,**kw):return call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,*args],**kw)
deadline=time.time()+3600
while True:
 complete=True
 for host in ('127x04','127x08'):
  for label in ('s4-dev-replay-v2','s4-dev-replay-extra-v2','s4-dev-control-r2'):
   command=f'if test -f {JOBS}/{label}.exit; then cat {JOBS}/{label}.exit; else echo running; fi'
   r=remote(host,[command],capture_output=True).stdout.strip();assert r in ('running','0'),(host,label,r)
   complete &= r=='0'
 if complete:break
 assert time.time()<deadline,'dev barrier timed out; no process retry authorized by elapsed time'
 time.sleep(30)
for name in ('dev-v2','dev-exact-control'):
 remote('127x04',['rsync','-ac','--include=*.json','--exclude=*','-e','"ssh -o BatchMode=yes -o ConnectTimeout=10"',f'127x08:{HERE}/{name}/',str(HERE/name)+'/'])
remote('127x04',['bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),'s4-dev-summary-v2','env','RAYON_NUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'dev_summary.py'),'--round','v2'])
while True:
 r=remote('127x04',[f'if test -f {JOBS}/s4-dev-summary-v2.exit; then cat {JOBS}/s4-dev-summary-v2.exit; else echo running; fi'],capture_output=True).stdout.strip()
 assert r in ('running','0'),r
 if r=='0':break
 assert time.time()<deadline
 time.sleep(5)
call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',f'127x04:{HERE}/dev-summary-v2.json',str(HERE)+'/'])
call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',str(HERE/'dev-summary-v2.json'),f'127x05:{HERE}/'])
print('All 56 dev traces summarized after all supervisor successes.',flush=True)
