"""Bounded seed-audit barrier, immutable seal, then detached confirmations."""
from pathlib import Path
import hashlib,json,subprocess,time,socket
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
def call(args,**kw):return subprocess.run(args,check=True,text=True,timeout=180,**kw)
deadline=time.time()+1800
while not (JOBS/'s4-seed-audit-r1.exit').exists():
 assert time.time()<deadline,'seed audit timeout; inspect original process, do not relaunch'
 time.sleep(10)
assert (JOBS/'s4-seed-audit-r1.exit').read_text().strip()=='0'
call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'integrity.py')])
call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'seal.py')])
manifest=json.loads((HERE/'evaluation-manifest.json').read_text());sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
files=[p for p in manifest['files'] if not p.startswith(('runtime/','inputs/'))]+['evaluation-manifest.json']
for host in ('127x04','127x08'):
 call(['rsync','-ac','--files-from=-','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',str(HERE)+'/',f'{host}:{HERE}/'],input='\n'.join(files)+'\n')
 # Create remote receipt directories before collector's first read.
 call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'mkdir','-p',str(HERE/'confirmation')])
 call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),f's4-confirm-node-{host}-r1','env','RAYON_NUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'launch_node.py'),'--concurrency','64'])
(HERE/'PROGRESS.md').write_text(f'# S4 progress\n\nConfirmation launched outcome-blind: 1,280 games, 152 partitions, requested concurrency 64/host. Manifest {sha}. Separate tracker development replays running on 04/08.\n')
(HERE/'RESUME.md').write_text(f'# S4 resume\n\nActive confirmation labels s4-confirm-node-127x04-r1 and s4-confirm-node-127x08-r1; collector s4-collect-r1 on hub. Manifest {sha}. Do not read outcomes until 1,280 receipts, all 152 partitions and both supervisors pass. Technical reruns only, preserving evidence. Dev replay labels s4-dev-replay-v1 on 04/08; original exact replay labels s4-exact-0-r1 and s4-exact-2-r1 on 08, s4-exact-1-r1 on 04.\n')
call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',*[str(HERE/p) for p in ('evaluation-manifest.json','schedule.json','seed-audit-127x01.json','PROGRESS.md','RESUME.md')],f'127x05:{HERE}/'])
call(['bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),'s4-collect-r1','env','RAYON_NUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'collect.py')])
print(json.dumps(dict(launched=True,manifest=sha)),flush=True)
