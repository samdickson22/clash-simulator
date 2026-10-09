"""Recover exact unfinished identities from the current08 phase after vacate."""
import hashlib,json,subprocess
from pathlib import Path
from requeue08 import unfinished

def recover(job):
 job=Path(job);receipt=job/'reporting08-r3-requeue.json'
 if receipt.exists():return
 result=json.loads(subprocess.check_output(['ssh','127x08',f'cat {job}/reporting/staged-r3/exit.json'],text=True))
 assert result['own_workers_vacated'] and result['stop_requested']
 subprocess.run(['rsync','-a','--quiet',f'127x08:{job}/stage-cases/',str(job/'stage-cases')+'/'],check=True)
 summaries=[]
 for path in sorted((job/'stage-queues-r3/08').glob('*.json')):
  q=json.loads(path.read_text());expected={tuple(t) for t in q['tasks']}
  records=[]
  for p in (job/'stage-cases'/q['stage']).glob('*.json'):
   r=json.loads(p.read_text())
   if (r['mode'],r['arm'],r['index']) in expected:records.append(r)
  freeze=Path(q['freeze']);assert hashlib.sha256(freeze.read_bytes()).hexdigest()==q['freeze_sha256']
  pending=unfinished(q['tasks'],records,q['freeze_sha256'],json.loads(freeze.read_text())['seed_bases'])
  dest=job/'stage-queues-r3/03'/('200-rescue-'+path.name)
  tmp=dest.with_suffix('.partial');tmp.write_text(json.dumps(dict(q,host='03',tasks=pending),indent=2)+'\n');tmp.replace(dest)
  summaries.append(dict(stage=q['stage'],completed_retained=len(records),unfinished_requeued=len(pending),queue_sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
 receipt.write_text(json.dumps(dict(queues=summaries,owned_workers_vacated=True,cpu_seconds=result['manager_cpu_seconds']+result['children_cpu_seconds']),indent=2)+'\n')
 (job/'reporting08-requeue.json').write_text(receipt.read_text())
