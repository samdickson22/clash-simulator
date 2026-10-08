"""Direct LAN, checksum-verified copies; no training imports or checkpoint loads."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import shlex
import socket
import subprocess
import time


REMOTE = '''import pathlib,json,hashlib,sys
a=json.loads(sys.argv[1]);p=pathlib.Path(a['path'])
if a['op']=='list':
 files=list(p.glob('epoch-*.pt'))+list(p.glob('best-dev-step-*.pt'))
 latest=max(p.glob('step-*.pt'),key=lambda x:x.stat().st_mtime_ns,default=None)
 if latest:files.append(latest)
 for name in ('train.jsonl','segments.jsonl','checkpoints.json','hostloss-operations.json','loader-operations.jsonl','allocator-operations.jsonl'):
  if (p/name).exists():files.append(p/name)
 print(json.dumps([{'name':f.name,'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns} for f in files]))
else:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 print(json.dumps(h.hexdigest()))
'''


def call(host, op, path):
    argv = ['python3', '-c', REMOTE, json.dumps({'op': op, 'path': str(path)})]
    if host != '127x04':
        argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', host,
                shlex.join(argv)]
    return json.loads(subprocess.check_output(argv, text=True, timeout=45))


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan', required=True)
    p.add_argument('--plan-sha256', required=True);p.add_argument('--once', action='store_true')
    a=p.parse_args();planpath=Path(a.plan)
    assert socket.gethostname().split('.')[0]=='127x04'
    assert hashlib.sha256(planpath.read_bytes()).hexdigest()==a.plan_sha256
    spec=json.loads(planpath.read_text())
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==spec['script_sha256']
    lock=(planpath.parent/'mirror.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    statepath=planpath.parent/'mirror-state.json'
    state=json.loads(statepath.read_text()) if statepath.exists() else {}
    while True:
        for run in spec['runs']:
            if run.get('last_copy_start_utc') and datetime.now(timezone.utc)>=datetime.fromisoformat(run['last_copy_start_utc'].replace('Z','+00:00')):
                continue
            try:
                sourcehost=run['source_host'];desthost=run['destination_host']
                assert sourcehost in ('127x01','127x04','127x08','127x13','127x14')
                assert desthost in ('127x01','127x04') and sourcehost!=desthost
                assert str(run['destination']).startswith('/mpac/sdicks02/tmp/t5-checkpoint-backups-20261008/')
                if desthost=='127x04':Path(run['destination']).mkdir(parents=True,exist_ok=True)
                else:subprocess.run(['ssh','-o','ConnectTimeout=8',desthost,'mkdir -p '+shlex.quote(run['destination'])],check=True,timeout=15)
                for info in call(sourcehost,'list',run['source']):
                    name=info['name'];assert Path(name).name==name
                    key=run['run']+'/'+name
                    if state.get(key,{}).get('source_stat')==info:continue
                    src=str(Path(run['source'])/name);dst=str(Path(run['destination'])/name)
                    before=call(sourcehost,'sha',src)
                    argv=['rsync','-c','--timeout=30','-e','ssh -o BatchMode=yes -o ConnectTimeout=8',
                          src if sourcehost=='127x04' else sourcehost+':'+src,
                          dst if desthost=='127x04' else desthost+':'+dst]
                    subprocess.run(argv,check=True,timeout=45)
                    after=call(desthost,'sha',dst)
                    if before!=after:
                        raise RuntimeError('source changed during copy or checksum mismatch: '+key)
                    record={'at':datetime.now(timezone.utc).isoformat(),'run':run['run'],
                            'source_host':sourcehost,'source':src,'destination_host':desthost,
                            'destination':dst,'sha256':after,'source_stat':info,'verified':True}
                    state[key]=record
                    with (planpath.parent/'mirror-receipts.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
                    tmp=statepath.with_suffix('.partial');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(statepath)
                print(json.dumps({'event':'mirror_pass','run':run['run'],'at':datetime.now(timezone.utc).isoformat()}),flush=True)
            except Exception as e:
                print(json.dumps({'event':'mirror_error','run':run['run'],'error':str(e),'at':datetime.now(timezone.utc).isoformat()}),flush=True)
        if a.once:return
        time.sleep(60)


if __name__=='__main__':main()
