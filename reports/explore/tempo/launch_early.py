import json,subprocess
from pathlib import Path
root=Path('/mpac/sdicks02/repos/clasher');r=root/'reports/explore/tempo';b=json.loads((r/'receipts/perception-rate.baseline.json').read_text())
cmd=['bash',str(root/'reports/strategy_council_20260928/fleet/fleet_run.sh'),'tempo-early-report-v1','nice','-n','10','chrt','--idle','0','taskset','-c','0-47,64-111','env','RAYON_NUM_THREADS=1',str(root/'.venv/bin/python'),'-B',str(r/'worker_runtime.py'),'--offset','0','--pairs','100','--workers','34','--arms','0','H12','H16','--out',str(r/'early-reporting'),'--max-seconds','1200','--gpu-guard','--throughput-log',b['log_path'],'--throughput-field',b['field'],'--baseline-rate',str(b['baseline']),'--case-costs',str(root/'reports/explore/search-ab/case-costs.json')]
s=subprocess.run(cmd,text=True,capture_output=True);(r/'receipts/early-launch.json').write_text(json.dumps(dict(command=cmd,status=s.returncode,stdout=s.stdout,stderr=s.stderr))+'\n');print(s.stdout,s.stderr)
