"""Recover only unfinished identities after an owned08 reporting stop."""
import hashlib
import json
from pathlib import Path
import subprocess

def unfinished(tasks, records, freeze_sha, seed_bases):
    expected={tuple(t) for t in tasks};seen=set()
    for r in records:
        key=(r['mode'],r['arm'],r['index'])
        assert key in expected and key not in seen and r['terminal'] is True
        assert r['freeze_sha256']==freeze_sha
        assert r['seed']==seed_bases[key[0]]+key[2] and r['seat']==key[2]%2
        seen.add(key)
    return [t for t in tasks if tuple(t) not in seen]

def recover(job):
    job=Path(job);receipt=job/'reporting08-requeue.json'
    if receipt.exists():return
    result=json.loads(subprocess.check_output(['ssh','127x08',f'cat {job}/reporting/staged-r1/exit.json'],text=True))
    assert result['own_workers_vacated'] and result['stop_requested']
    queue=json.loads((job/'stage-queues/08/100-S-teacher.json').read_text())
    subprocess.run(['rsync','-a','--quiet',f'127x08:{job}/stage-cases/',str(job/'stage-cases')+'/'],check=True)
    # The04 raw receipts have not yet been copied, so this stage contains only08.
    records=[json.loads(p.read_text()) for p in sorted((job/'stage-cases/S-teacher').glob('*.json'))]
    freeze_path=Path(queue['freeze']);assert hashlib.sha256(freeze_path.read_bytes()).hexdigest()==queue['freeze_sha256']
    pending=unfinished(queue['tasks'],records,queue['freeze_sha256'],json.loads(freeze_path.read_text())['seed_bases'])
    assert result['completed']<=len(records)<=len(queue['tasks'])
    dest=job/'stage-queues/03/200-requeued08-S-teacher.json';tmp=dest.with_suffix('.partial')
    tmp.write_text(json.dumps(dict(queue,host='03',tasks=pending),indent=2)+'\n');tmp.replace(dest)
    receipt.write_text(json.dumps(dict(completed_retained=len(records),unfinished_requeued=len(pending),
        destination_host='03',all_rows_seeds_seats_preserved=True,
        queue_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),
        cpu_seconds=result['manager_cpu_seconds']+result['children_cpu_seconds'],
        owned_workers_vacated=True),indent=2)+'\n')
