"""Bounded technical preflight barrier; seal once, then detach confirmation."""
from pathlib import Path
import hashlib,json,subprocess,time,socket
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
def call(args,**kw):return subprocess.run(args,check=True,text=True,timeout=180,**kw)
def mirror(names):call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',*[str(HERE/n) for n in names],f'127x05:{HERE}/'])
try:
 deadline=time.time()+7200
 while True:
  completed=0
  for host in ('127x04','127x08'):
   script="from pathlib import Path;import json;p=Path('/mpac/sdicks02/jobs/clasher');print(json.dumps({f.name:f.read_text().strip() for f in p.glob('s6-preflight-*-%s-r1.exit')}))"%host
   r=call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'python3','-c',__import__('shlex').quote(script)],capture_output=True)
   exits=json.loads(r.stdout)
   for name,code in exits.items():assert code=='0',(host,name,code)
   completed+=len(exits)
  assert completed<=8
  (HERE/'PROGRESS.md').write_text(f'# S6 progress\n\n{completed}/8 preflight partitions complete. Both seed audits passed; tracker unchanged; outcomes suppressed. Awaiting all preflight evidence before manifest seal and 1,280-game confirmation.\n')
  mirror(['PROGRESS.md']);print(json.dumps(dict(preflight_complete=completed,total=8)),flush=True)
  if completed==8:break
  assert time.time()<deadline,'preflight timeout; preserve and inspect processes, do not duplicate'
  time.sleep(60)
 status=HERE/'preflight-status';status.mkdir(exist_ok=True)
 for host in ('127x04','127x08'):
  own=['equivalence-*.json','pilot-*.json','integrity-*.json']
  # Explicit source globs; missing optional per-host classes are avoided via listing.
  script="from pathlib import Path;import json;p=Path(%r);print(json.dumps([f.name for f in p.glob('*.json') if f.name.startswith(('equivalence-','pilot-','integrity-'))]))"%str(HERE)
  names=json.loads(call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'python3','-c',__import__('shlex').quote(script)],capture_output=True).stdout)
  call(['rsync','-ac','--files-from=-','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',f'{host}:{HERE}/',str(HERE)+'/'],input='\n'.join(names)+'\n')
  labels=[f's6-preflight-{i}-{host}-r1' for i in range(8) if (i%2==0)==(host=='127x04')]
  if host=='127x04':labels+=['s6-tests-127x04-r1','s6-tests-127x04-r2']
  call(['rsync','-ac','--files-from=-','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',f'{host}:{JOBS}/',str(status)+'/'],input='\n'.join(f'{label}.{ext}' for label in labels for ext in ('log','exit'))+'\n')
 assert (JOBS/'s6-register-127x01-r1.exit').read_text().strip()=='0'
 call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'integrity.py')])
 call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'seal.py')])
 manifest=json.loads((HERE/'evaluation-manifest.json').read_text());sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
 files=[p for p in manifest['files'] if not p.startswith(('runtime/','inputs/'))]+['evaluation-manifest.json']
 for host in ('127x04','127x08'):
  call(['rsync','-ac','--files-from=-','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',str(HERE)+'/',f'{host}:{HERE}/'],input='\n'.join(files)+'\n')
  call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'mkdir','-p',str(HERE/'confirmation')])
  call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),f's6-confirm-node-{host}-r1','env','PYTHONHASHSEED=0','RAYON_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','VECLIB_MAXIMUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'launch_node.py'),'--concurrency','64'])
 (HERE/'PROGRESS.md').write_text(f'# S6 progress\n\nConfirmation launched outcome-blind: 1,280 games, 128 partitions, dynamic console cap 16 / unattended workload cap 80 (16 reserved). Manifest {sha}.\n')
 (HERE/'RESUME.md').write_text(f'# S6 resume\n\nActive labels s6-confirm-node-127x04-r1 and s6-confirm-node-127x08-r1; collector s6-collect-127x01-r1. Manifest {sha}. Do not inspect outcomes before all 1,280 terminal receipts, 128 partition successes and both supervisors pass. Technical reruns only; do not duplicate active work.\n')
 mirror(['evaluation-manifest.json','schedule.json','PROGRESS.md','RESUME.md'])
 call(['bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),'s6-collect-127x01-r1','env','RAYON_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'collect.py')])
 print(json.dumps(dict(launched=True,manifest=sha)),flush=True)
except BaseException as e:
 (HERE/'RESUME.md').write_text(f'# S6 resume\n\nStartup STOPPED: {e}. No retry loop. Inspect s6-start-confirmation-127x01-r1 log and existing remote labels; do not assume workers died. No confirmation outcomes inspected.\n')
 (HERE/'PROGRESS.md').write_text(f'# S6 progress\n\nStartup stopped: {e}. See RESUME.md.\n')
 try:mirror(['PROGRESS.md','RESUME.md'])
 except Exception:pass
 raise
