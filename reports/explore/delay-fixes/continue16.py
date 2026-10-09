"""After the already-admitted p1000 shard exits, extend to1250 paired seeds."""
import datetime,json,subprocess,time,sys
from pathlib import Path
root=Path(__file__).resolve().parent
host='127x16';base='/mpac/sdicks02/repos/clasher-lease'
label=sys.argv[1] if len(sys.argv)>1 else 'cpu-delay-fixes-extra1000-hotfix-v1'
for attempt in range(60):
 if datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime(2026,10,9,4,15,tzinfo=datetime.timezone.utc):break
 p=subprocess.run(['ssh','-o','BatchMode=yes',host,f'cat {base}/jobs/{label}.exit.json'],capture_output=True,text=True)
 if p.returncode==0:
  r=json.loads(p.stdout);(root/'receipts'/f'{label}.exit.json').write_text(p.stdout)
  if r['exit_code'] or r.get('stop_reason'):break
  subprocess.run(['ssh','-o','BatchMode=yes',host,f'rsync -az {base}/delay-fixes-runtime/reports/explore/delay-fixes/shards/p1000/ 127x08:/mpac/sdicks02/repos/clasher/reports/explore/delay-fixes/shards/p1000/'],check=True)
  subprocess.run(['python3',str(root/'launch_shards.py'),'--pairs','225','--start-offset','1025','--hosts',host,'--tag','extra16-v1','--manifest','launch-extra16.json'],check=True)
  break
 time.sleep(30)
else:raise RuntimeError('bounded p1000 wait exhausted')
