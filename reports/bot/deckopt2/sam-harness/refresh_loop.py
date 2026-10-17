"""Passive light05 reports and verified own-tail lease reductions."""
import json,os,shlex,subprocess,time
from sam_common import ROOT,PY,utc,dump,record
HOSTS=('127x01','127x03','127x04')
REMOTE=r'''
import json,os,pathlib
j=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam');out=[]
for p in j.glob('controller-sam-*.json'):
 c=json.loads(p.read_text());group=c['pgid'];parent=c['pid'];lease=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims')/f'lease-{group}'
 if not lease.exists() or not pathlib.Path('/proc',str(parent)).exists():continue
 alive=[]
 for pid in c['worker_pids']:
  q=pathlib.Path('/proc',str(pid))
  try:
   command=(q/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   if (q/'stat').read_text().split()[2]!='Z' and str(j/'sam_worker.py') in command:
    assert os.getpgid(pid)==group
    alive.append(pid)
  except FileNotFoundError:pass
 if not alive:continue
 owner=pathlib.Path('/proc',str(group))
 if not owner.exists():continue
 command=(owner/'cmdline').read_bytes().replace(b'\0',b' ').decode()
 assert 'cpu_job.sh' in command and str(j/'sam_worker.py') in command
 old,g=map(int,lease.read_text().split());assert g==group
 # The parent only waits after forking. Reserve the surviving game workers,
 # without an extra idle controller slot in every small tail partition.
 desired=len(alive)
 if desired<old and lease.exists() and owner.exists():
  temp=lease.with_name(lease.name+'.sam-tail-tmp');temp.write_text(f'{desired} {group}\n');os.replace(temp,lease)
  out.append(dict(pgid=group,old=old,new=desired,workers=alive))
print(json.dumps(out))
'''
def main():
 dump(ROOT/'refresh-process.json',dict(pid=os.getpid(),utc=utc()))
 while not (ROOT/'STOP-REFRESH').exists():
  for host in HOSTS:
   dest=ROOT/f'health-{host}';dest.mkdir(exist_ok=True)
   subprocess.run(['rsync','-a','--ignore-missing-args','--include=controller-*.json','--include=worker-error-*.json','--exclude=*',f'{host}:{ROOT}/',str(dest)+'/'],check=True)
   changes=json.loads(subprocess.check_output(['ssh',host,'python3 -'],input=REMOTE,text=True))
   for change in changes:
    with (ROOT/'tail-leases.jsonl').open('a') as stream:stream.write(json.dumps(dict(utc=utc(),host=host,**change))+'\n')
   errors=list(dest.glob('worker-error-*.json'))
   finished=[json.loads(p.read_text()) for p in dest.glob('controller-finished-*.json')]
   if errors or any(any(x['statuses'].values()) for x in finished):
    dump(ROOT/'health-error.json',dict(utc=utc(),host=host,errors=[p.name for p in errors],failed_controllers=[x for x in finished if any(x['statuses'].values())]));(ROOT/'STOP').touch()
  env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONPATH=f'{ROOT}:/mpac/sdicks02/jobs/clasher/bot-deckopt2:/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool')
  subprocess.run([PY,str(ROOT/'report.py')],env=env,check=True)
  if (ROOT/'DONE.json').exists():record('Passive report loop finished all banks.');return
  time.sleep(40)
if __name__=='__main__':
 try:main()
 except BaseException as error:dump(ROOT/'refresh-error.json',dict(utc=utc(),error=repr(error)));raise
