"""Bounded audit barrier then detached outcome-blind preflight; no transport retries."""
from pathlib import Path
import json,subprocess,socket,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];JOBS=Path('/mpac/sdicks02/jobs/clasher')
assert socket.gethostname().split('.')[0]=='127x01'
def call(args,**kw):return subprocess.run(args,check=True,text=True,timeout=180,**kw)
try:
 deadline=time.time()+1800
 while not (JOBS/'s6-seed-audit-127x01-r1.exit').exists():
  assert time.time()<deadline,'seed audit timeout; inspect original process, never duplicate'
  time.sleep(10)
 assert (JOBS/'s6-seed-audit-127x01-r1.exit').read_text().strip()=='0'
 for host in ('127x01','127x04'):assert json.loads((HERE/f'seed-audit-{host}.json').read_text())['passed']
 for host in ('127x04','127x08'):
  call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',str(HERE/'seed-audit-127x01.json'),str(HERE/'seed-audit-127x04.json'),f'{host}:{HERE}/'])
 for i in range(8):
  host='127x04' if i%2==0 else '127x08'
  check="import os,subprocess;w=subprocess.check_output(['who'],text=True);p=subprocess.check_output(['ps','-u',str(os.getuid()),'-o','comm='],text=True);n=sum(any(x in l.lower() for x in ('python','pt_data_worker','ffmpeg','blender','clasher')) for l in p.splitlines());assert n+2<=(16 if w.strip() else 96),(n,w)"
  call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'python3','-c',__import__('shlex').quote(check)])
  call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),f's6-preflight-{i}-{host}-r1','env','PYTHONHASHSEED=0','RAYON_NUM_THREADS=1','NUMEXPR_NUM_THREADS=1','VECLIB_MAXIMUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'preflight.py'),'--index',str(i)])
 call(['bash',str(ROOT/'reports/strategy_council_20260928/fleet/fleet_run.sh'),'s6-register-127x01-r1','env','RAYON_NUM_THREADS=1',str(ROOT/'.venv/bin/python'),'-B',str(HERE/'register.py')])
 (HERE/'PROGRESS.md').write_text('# S6 progress\n\nBoth seed audits passed. Eight outcome-blind preflight partitions launched (four per host on 04/08), below console cap 16. Tracker unchanged; no confirmation yet.\n')
 (HERE/'RESUME.md').write_text('# S6 resume\n\nPreflight active: s6-preflight-0..7-<host>-r1 (even indices 04, odd 08); registration s6-register-127x01-r1. Do not duplicate labels. Await all terminal technical receipts, then freeze manifest before confirmation. No outcomes inspected.\n')
 call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',*[str(HERE/n) for n in ('PROGRESS.md','RESUME.md','seed-audit-127x01.json')],f'127x05:{HERE}/'])
 print('preflight launched',flush=True)
except BaseException as e:
 (HERE/'RESUME.md').write_text(f'# S6 resume\n\nPreflight startup stopped: {e}. No retry loop. Inspect detached s6-start-preflight-127x01-r1 log and remote existing labels before any action. Do not assume remote jobs died.\n')
 raise
