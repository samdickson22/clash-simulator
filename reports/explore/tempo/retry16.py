"""New smaller 16 work declaration after other CPU workload has drained."""
import json,subprocess,shlex,time
from pathlib import Path
r=Path(__file__).resolve().parent;path=r/'receipts/early-leases-launch.json';records=json.loads(path.read_text());old=next(x for x in records if x['host']=='127x16');assert old['status']!=0
probe=subprocess.run(['ssh','-o','BatchMode=yes','127x16','nice -n 10 chrt --idle 0 ps -eo args'],text=True,capture_output=True,check=True)
assert not any('clasher.analysis.loss_review.delay_simulate' in x and not 'ps -eo' in x for x in probe.stdout.splitlines()),'wait for other CPU workload drain'
command=list(old['command']);command[command.index('--max-processes')+1]='32';command[command.index('--expected-pss-gb')+1]='21.6';command[command.index('--workers')+1]='28';command[command.index('-c')+1]='64-91';command[command.index(old['label'])]='tempo-early-127x16-v2'
result=subprocess.run(['ssh','-o','BatchMode=yes','127x16',shlex.join(['nice','-n','10','chrt','--idle','0',*command])],text=True,capture_output=True,timeout=90)
rec=dict(old,label='tempo-early-127x16-v2',workers=28,status=result.returncode,stdout=result.stdout,stderr=result.stderr,command=command,utc=time.time(),reason='other delay-fixes CPU workload drained; smaller 28-worker declaration fits combined PSS budget')
records.append(rec);path.write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(rec))
