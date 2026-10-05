"""Detached, bounded two-worker driver; stop on any nonzero child receipt."""
import hashlib,json,os,subprocess,time
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3];D=R/'reports/strategy_council_20260928/pilot/detach.sh'
def progress(s):
 with (H/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {s}\n')
 print(s,flush=True)
def launch(label,args):
 exitfile=H/f'{label}.exit'
 if exitfile.exists():
  if exitfile.read_text().strip()=='0':return None
  raise RuntimeError('Existing failed receipt '+label)
 pid=int(subprocess.check_output(['bash',str(D),str(H/f'{label}.log'),'bash',str(H/'run.sh'),label,str(R/'.venv/bin/python'),'-B',*map(str,args)],cwd=R,text=True).strip())
 (H/f'{label}.launch.json').write_text(json.dumps(dict(pid=pid,time=time.time(),args=list(map(str,args))),indent=2))
 return pid
manifest=json.loads((H/'manifest.json').read_text())
for p,want in manifest['files'].items():
 with open(p,'rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==want,p
progress('Evaluation driver starting after source-pin verification.')
try:
 for mode in ['p16','c56']:
  labels=[f'eval-native-{mode}',f'eval-sim-{mode}']
  launch(labels[0],[H/'offline_loop.py','--mode',mode])
  launch(labels[1],[H/'simulator.py','--mode',mode,'--wait'])
  while True:
   receipts=[H/f'{x}.exit' for x in labels]
   for p in receipts:
    if p.exists() and p.read_text().strip()!='0':raise RuntimeError('Worker failure '+str(p))
   if all(p.exists() for p in receipts):break
   time.sleep(10)
  progress(mode+' native and simulator workers exited zero.')
 (H/'evaluation-complete.json').write_text(json.dumps(dict(time=time.time(),complete=True)))
except BaseException as e:
 (H/'pipeline-error.json').write_text(json.dumps(dict(time=time.time(),error=repr(e))))
 progress('Evaluation driver stopped: '+repr(e));raise
