"""Lower only this worker's fixed 04 lease to its verified remaining workers."""
import json
import subprocess
from pathlib import Path

ROOT = Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
REMOTE = r'''
import json,os,pathlib,subprocess
root=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
pid=1974092
lease=pathlib.Path('/mpac/sdicks02/jobs/clasher/bot-cpu-claims/lease-1974092')
proc=pathlib.Path('/proc')/str(pid)
out={'utc':subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip(),'pid':pid}
if not proc.exists() or not lease.exists():
 out['status']='released'
else:
 command=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
 assert 'cpu_job.sh' in command and os.getpgid(pid)==pid,command
 receipt=json.loads((root/'fullpool/controller-fpr2-04-0.json').read_text())
 alive=[]
 for worker in receipt['worker_pids']:
  p=pathlib.Path('/proc')/str(worker)
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   if (p/'stat').read_text().split()[2]!='Z' and str(root/'fullpool_wait_entry.py') in cmd:
    assert os.getpgid(worker)==pid,(worker,os.getpgid(worker))
    alive.append(worker)
  except FileNotFoundError:pass
 old,group=map(int,lease.read_text().split())
 assert group==pid and len(alive)<=old,(old,group,alive)
 out.update(old=old,remaining_workers=len(alive),worker_pids=alive)
 if alive and len(alive)<old and proc.exists() and lease.exists():
  temporary=lease.with_name(lease.name+'.deckopt2-tail-tmp')
  temporary.write_text(f'{len(alive)} {pid}\n')
  os.replace(temporary,lease)
  out['status']='lowered'
 else:out['status']='unchanged' if alive else 'awaiting_owner_cleanup'
print(json.dumps(out))
'''

if __name__ == '__main__':
    result = json.loads(subprocess.check_output(
        ['ssh', '127x04', 'python3 -'], input=REMOTE, text=True))
    with (ROOT / 'fullpool/lease-tail-audit.jsonl').open('a') as stream:
        stream.write(json.dumps(result) + '\n')
    print(json.dumps(result))
