"""Wait only for owned jobs, retain early games, select using tuning only."""
import json,shlex,subprocess,time,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[3];r=root/'reports/explore/tempo';python=str(root/'.venv/bin/python')
def call(args,timeout=120):return subprocess.run(['nice','-n','10','chrt','--idle','0',*args],text=True,capture_output=True,timeout=timeout)
def ssh(host,args):
 args=['nice','-n','10','chrt','--idle','0',*args]
 return call(args if host=='127x04' else ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,shlex.join(args)])
def wait_home(host,label,limit=1800):
 start=time.time()
 while time.time()-start<limit:
  result=ssh(host,['cat','/mpac/sdicks02/jobs/clasher/'+label+'.exit'])
  if result.returncode==0:return int(result.stdout)
  time.sleep(20)
 raise RuntimeError('bounded own-job wait expired '+label)
assert wait_home('127x03','tempo-tune-v1')==0
assert wait_home('127x04','tempo-early-report-v1') in (0,75)
assert wait_home('127x04','tempo-smoke-v1')==0
call(['rsync','--rsync-path=nice -n 10 chrt --idle 0 rsync','-ac','127x03:/mpac/sdicks02/repos/clasher-tempo-runtime/reports/explore/tempo/tuning/',str(r/'tuning')+'/']).check_returncode()
call([python,str(r/'select.py'),'--games',str(r/'tuning/games'),'--out',str(r/'parameters.json')]).check_returncode()
# Runtime refresh is sequential with owned completion, never during active shards.
if not (r/'receipts/combination-scheduler.json').exists():call(['bash',str(r/'stage.sh'),'127x03','/mpac/sdicks02/repos/clasher-tempo-runtime']).check_returncode()
combo_args=[python,str(r/'scheduler.py'),'--phase','combination','--selection',str(r/'parameters.json')]
if (r/'receipts/combination-scheduler.json').exists():combo_args.append('--resume-state')
result=call(combo_args,timeout=9000)
(r/'receipts/combination-controller.txt').write_text(result.stdout+result.stderr);result.check_returncode()
call([python,str(r/'select.py'),'--games',str(r/'combination'),'--out',str(r/'selection.json'),'--combination','--prior',str(r/'parameters.json')]).check_returncode()

if not (r/'receipts/reporting-scheduler.json').exists():
 # Every early arm has a fixed definition independent of selected E/W weights.
 roots=[r/'early-reporting']
 launch_path=r/'receipts/early-leases-launch.json'
 if launch_path.exists():
  for rec in json.loads(launch_path.read_text()):
   if rec.get('status')!=0:continue
   host=rec['host'];start=time.time()
   while time.time()-start<1800:
    result=ssh(host,['cat','/mpac/sdicks02/repos/clasher-lease/jobs/'+rec['label']+'.exit.json'])
    if result.returncode==0:break
    time.sleep(20)
   else:raise RuntimeError('bounded lease wait expired')
   dest=r/'early-leases'/host;dest.mkdir(parents=True,exist_ok=True)
   call(['rsync','--rsync-path=nice -n 10 chrt --idle 0 rsync','-ac',host+':/mpac/sdicks02/repos/clasher-lease/tempo-runtime/reports/explore/tempo/early-reporting/',str(dest)+'/']).check_returncode();roots.append(dest)
 for prior in roots:
  for game in (prior/'games').glob('*.json'):
   row=json.loads(game.read_text());pair=int(row['identity'].split('-')[1]);folder=r/'reporting'/f'p{pair//25*25:04d}'/'games';folder.mkdir(parents=True,exist_ok=True);shutil.copy2(game,folder/game.name)
report_args=[python,str(r/'scheduler.py'),'--phase','reporting','--selection',str(r/'selection.json')]
if (r/'receipts/reporting-scheduler.json').exists():report_args.append('--resume-state')
if (r/'resume-hosts.json').exists():report_args+=['--resume-hosts',*json.loads((r/'resume-hosts.json').read_text())['hosts']]
result=call(report_args,timeout=9000)
(r/'receipts/reporting-controller.txt').write_text(result.stdout+result.stderr);result.check_returncode()
call([python,str(r/'reduce.py'),'--root',str(r)],timeout=600).check_returncode()
