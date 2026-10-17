"""Light05 admission/health, with per-partition verified tail leases."""
import json,os,shlex,subprocess,time
from sam_common import ROOT,PY,utc,dump,record
HOSTS=('127x03','127x04')
def ssh(host,args):return subprocess.check_output(['ssh',host,shlex.join(list(map(str,args)))],text=True)
TAIL=r'''
import json,os,pathlib
j=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2-levelgain-20261017');out=[]
for p in j.glob('controller-lg-*.json'):
 c=json.loads(p.read_text());g=c['pgid'];parent=c['pid'];lease=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims')/f'lease-{g}'
 if not lease.exists() or not pathlib.Path('/proc',str(parent)).exists():continue
 alive=[]
 for pid in c['worker_pids']:
  q=pathlib.Path('/proc',str(pid))
  try:
   command=(q/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   if (q/'stat').read_text().split()[2]!='Z' and any(str(j/name) in command for name in ('sam_worker.py','extended_worker.py','extra_worker.py')):
    assert os.getpgid(pid)==g;alive.append(pid)
  except FileNotFoundError:pass
 if not alive:continue
 owner=pathlib.Path('/proc',str(g))
 if not owner.exists():continue
 command=(owner/'cmdline').read_bytes().replace(b'\0',b' ').decode();assert 'cpu_job.sh' in command and any(str(j/name) in command for name in ('sam_worker.py','extended_worker.py','extra_worker.py'))
 old,group=map(int,lease.read_text().split());assert group==g
 if len(alive)<old:
  tmp=lease.with_name(lease.name+'.lg-tail');tmp.write_text(f'{len(alive)} {g}\n');os.replace(tmp,lease);out.append(dict(pgid=g,old=old,new=len(alive)))
print(json.dumps(out))
'''
def main():
 dump(ROOT/'extra-ops-process.json',dict(pid=os.getpid(),utc=utc()))
 while not (ROOT/'STOP').exists():
  for host in HOSTS:
   health=ROOT/f'health-{host}';health.mkdir(exist_ok=True)
   subprocess.run(['rsync','-a','--ignore-missing-args','--include=controller-*.json','--include=worker-error-*.json','--exclude=*',f'{host}:{ROOT}/',str(health)+'/'],check=True)
   finished=[json.loads(p.read_text()) for p in health.glob('controller-finished-*.json')]
   assert not list(health.glob('worker-error-*.json')) and all(not any(r['statuses'].values()) for r in finished),'worker/controller failure'
   changes=json.loads(subprocess.check_output(['ssh',host,'python3 -'],input=TAIL,text=True))
   for r in changes:
    with (ROOT/'tail-leases.jsonl').open('a') as f:f.write(json.dumps(dict(utc=utc(),host=host,**r))+'\n')
  status=[];pending=False
  for stage in ('shifted-extra',):
   p=ROOT/stage/'validation/bank.json'
   if not p.exists():continue
   b=json.loads(p.read_text());n=len(list((ROOT/stage/'validation/rows').glob('*.json')));expected=len(b['cases'])*len(b['candidates'])*len(b['players'])
   status.append(dict(stage=stage,games=n,expected=expected));pending|=len(list((ROOT/stage/'claims').glob('*.json')))<len(b['cases'])
  dump(ROOT/'status.json',dict(utc=utc(),stages=status))
  if pending and (ROOT/'preflight/receipt.json').exists():
   for host in HOSTS:
    receipts=[json.loads(p.read_text()) for p in ROOT.glob(f'launch-{host}-*.json')];health=ROOT/f'health-{host}'
    booked=sum(r['workers'] for r in receipts if not (health/f'controller-finished-{r["label"]}.json').exists())
    for n in (8,4,2,1):
     if booked+n>40:continue
     if ssh(host,['bash','-c',f'BOT_CPU_TRY=1 /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh {n+2}; echo $?']).strip()!='0':continue
     label=f'lg-extra-{host[-2:]}-{len(receipts)}'
     out=ssh(host,['/mpac/sdicks02/repos/clasher-bot/bot/detach.sh',ROOT/f'{label}.log',ROOT/f'{label}-detach.json','bash',ROOT/'run-extra.sh',label,n])
     dump(ROOT/f'launch-{host}-extra{len(receipts)}.json',dict(host=host,label=label,workers=n,utc=utc(),detach=json.loads(out)))
     record(f'Admitted {host} {label}: {n} game workers, separate session.');break
  env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMPY_MADVISE_HUGEPAGE='0',PYTHONPATH=f'{ROOT}:/mpac/sdicks02/jobs/clasher/bot-deckopt2-sam:/mpac/sdicks02/jobs/clasher/bot-deckopt2')
  subprocess.run([PY,str(ROOT/'analysis.py')],env=env,check=True)
  if len(status)==1 and all(s['games']==s['expected'] for s in status):dump(ROOT/'EXTRA-DONE.json',dict(utc=utc(),stages=status));record('Supplemental shifted-prior singletons complete.');return
  time.sleep(20)
if __name__=='__main__':
 try:main()
 except BaseException as error:dump(ROOT/'extra-ops-error.json',dict(utc=utc(),error=repr(error)));(ROOT/'STOP').touch();raise
