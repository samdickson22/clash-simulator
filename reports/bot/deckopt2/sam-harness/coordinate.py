"""Light05 admission and progress; no simulator/player imports."""
import json,os,shlex,subprocess,time
from sam_common import ROOT,OLD,utc,dump,record
HOSTS=('127x03','127x04','127x01')
def cmd(argv):return subprocess.check_output(list(map(str,argv)),text=True,stderr=subprocess.STDOUT)
def ssh(host,argv):return cmd(['ssh',host,shlex.join(list(map(str,argv)))])
def copy(host):
 ssh(host,['mkdir','-p',ROOT/'preflight'])
 paths=[ROOT/name for name in ('sam_common.py','sam_worker.py','sam_queue.py','sam_bank.py','run-sam.sh','collection-current.json','upgrade-variants.json')]
 cmd(['rsync','-a',*paths,f'{host}:{ROOT}/'])
 for stage in ('upgrades','max','current'):
  ssh(host,['mkdir','-p',ROOT/stage/'validation/rows'])
  cmd(['rsync','-a',ROOT/stage/'manifest.json',f'{host}:{ROOT/stage}/'])
  cmd(['rsync','-a',ROOT/stage/'validation/bank.json',f'{host}:{ROOT/stage}/validation/'])
 dump(ROOT/f'inputs-{host}.json',dict(utc=utc()))
def launch(host,n):
 receipts=list(ROOT.glob(f'launch-{host}-*.json'))
 label=f'sam-{host[-2:]}-{len(receipts)}';receipt=ROOT/f'launch-{host}-{len(receipts)}.json'
 if ssh(host,['bash','-c',f'BOT_CPU_TRY=1 /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh {n+3}; echo $?']).strip()!='0':return False
 output=ssh(host,['/mpac/sdicks02/repos/clasher-bot/bot/detach.sh',ROOT/f'{label}.log',ROOT/f'{label}-detach.json','bash',ROOT/'run-sam.sh',label,n])
 dump(receipt,dict(utc=utc(),host=host,label=label,workers=n,detach=json.loads(output)))
 record(f'Admitted {host} {label}: {n} workers/{n+2}slots, independent detach session.');return True
def main():
 dump(ROOT/'coordinator.json',dict(utc=utc(),pid=os.getpid()))
 for host in HOSTS:
  if not (ROOT/f'inputs-{host}.json').exists():copy(host)
 while not (ROOT/'STOP').exists():
  status=[]
  for stage in ('upgrades','max','current'):
   bank=json.loads((ROOT/stage/'validation/bank.json').read_text());paths=list((ROOT/stage/'validation/rows').glob('*.json'))
   expected=len(bank['cases'])*len(bank['candidates'])*len(bank['players'])
   status.append(dict(stage=stage,rows=len(paths),expected=expected))
  dump(ROOT/'status.json',dict(utc=utc(),stages=status))
  if all(s['rows']==s['expected'] for s in status):dump(ROOT/'DONE.json',dict(utc=utc(),stages=status));record('All three banks complete; final paired analysis pending.');return
  if (ROOT/'preflight/receipt.json').exists():
   for host in HOSTS:
    total=sum(json.loads(p.read_text())['workers'] for p in ROOT.glob(f'launch-{host}-*.json'))
    # Leave the03 preflight its one game slot until it exits. At most40
    # registered workers per host; admission still governs every launch.
    cap=32 if host=='127x03' and not (ROOT/'preflight/replay.json').exists() else 40
    for n in (8,4,2):
     if total+n<=cap and launch(host,n):break
  time.sleep(20)
if __name__=='__main__':
 try:main()
 except BaseException as error:dump(ROOT/'coordinator-error.json',dict(utc=utc(),error=repr(error)));raise
