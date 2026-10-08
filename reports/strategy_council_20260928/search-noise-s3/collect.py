"""01 light collector: immutable admission, no retries after transport failure."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,socket,subprocess,time,traceback
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]

def write(p,data):
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(data,separators=(',',':'))+'\n');tmp.replace(p)

def call(args):
    p=subprocess.run(args,capture_output=True,text=True,timeout=180)
    if p.returncode:raise RuntimeError(f'transport/command failure {args[:3]}: {p.stderr[-2000:]}')
    return p.stdout

def mirror():
    files=[str(HERE/n) for n in ('PROGRESS.md','RESUME.md','monitor.json','RESULTS.md','result.json','ELT-DIAGNOSIS.md') if (HERE/n).exists()]
    call(['rsync','-ac','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',*files,f'127x05:{HERE}/'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',default='r1');args=ap.parse_args()
    assert socket.gethostname().split('.')[0]=='127x01'
    execution=json.loads((HERE/'execution.json').read_text());schedule=json.loads((HERE/'schedule.json').read_text())
    import sys
    sys.path.insert(0,str(HERE));from cells import CELLS
    expected=[(ep,c,s) for ep in schedule['pairs'] for c in CELLS for s in (0,1)];assert len(expected)==1792
    sha=hashlib.sha256((HERE/'evaluation-manifest.json').read_bytes()).hexdigest()
    dest=HERE/'confirmation';dest.mkdir(exist_ok=True);status=HERE/'collected-status';status.mkdir(exist_ok=True)
    admitted={};complete=set();supervisors=set()
    try:
        while True:
            for host in ('127x04','127x08'):
                stage=HERE/'incoming'/host;stage.mkdir(parents=True,exist_ok=True)
                # Trailing source slash only includes this study's own game receipts.
                call(['rsync','-ac','--exclude=*.tmp','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',f'{host}:{HERE}/confirmation/',str(stage)+'/'])
                for path in stage.glob('*.json'):
                    stat=path.stat();key=(host,path.name)
                    if admitted.get(key)==(stat.st_size,stat.st_mtime_ns):continue
                    data=path.read_bytes();r=json.loads(data);index=int(path.stem);ep,c,s=expected[index]
                    assert r['manifest']==sha and r['terminal'] and r['job']==index
                    for k,w in [('seed',ep['seed']),('noise_seed',ep['noise_seed']),('pair',ep['pair']),('variant',c),('seat',s),('mode','scripts')]:assert r[k]==w,(index,k)
                    assert execution['workers'][index%len(execution['workers'])]['host']==host
                    target=dest/path.name
                    if target.exists():assert target.read_bytes()==data,('immutable receipt mismatch',index)
                    else:
                        temp=target.with_suffix('.tmp');temp.write_bytes(data);temp.replace(target)
                    admitted[key]=(stat.st_size,stat.st_mtime_ns)
                state=json.loads(call(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,'python3',str(HERE/'status.py'),'--attempt',args.attempt]))
                if state['supervisor'] is not None:
                    supervisor=state['supervisor'];(status/f'supervisor-{host}.log').write_text(supervisor['log'])
                    (status/f'supervisor-{host}.exit').write_text(supervisor['exit']+'\n')
                    assert supervisor['exit']=='0',('supervisor failed',host)
                    supervisors.add(host)
                for worker in state['workers']:
                    i=worker['index'];assert worker['exit']=='0',('worker failed',i,worker['label'])
                    if worker['done'] is None:continue
                    assert worker['done']['complete'] and worker['done']['manifest']==sha
                    write(status/f'worker-{i}-done.json',worker['done'])
                    (status/f'worker-{i}.exit').write_text('0\n');(status/f'worker-{i}.log').write_text(worker['log']);complete.add(i)
            receipts=len(list(dest.glob('*.json')))
            monitor=dict(utc=time.time(),receipts=receipts,total=1792,partitions_complete=len(complete),partitions_total=152,supervisors_complete=sorted(supervisors),outcomes_inspected=False)
            write(HERE/'monitor.json',monitor);print(json.dumps(monitor),flush=True)
            (HERE/'PROGRESS.md').write_text(f'# S3 progress\n\n{time.strftime("%Y-%m-%d %H:%M:%S UTC",time.gmtime())}: {receipts}/1792 validated terminal receipts; {len(complete)}/152 successful partitions; {len(supervisors)}/2 successful supervisors. Outcome-blind. Manifest {sha}.\n')
            if receipts==1792 and len(complete)==152 and len(supervisors)==2:
                call([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'analyze.py')])
                (HERE/'PROGRESS.md').write_text(f'# S3 progress\n\nCOMPLETE: 1792 games, 152 partitions, two supervisors. Complete-only analysis finished. Manifest {sha}. See RESULTS.md, result.json, ELT-DIAGNOSIS.md.\n')
                (HERE/'RESUME.md').write_text('# S3 resume\n\nStudy complete. Do not relaunch. Raw receipts on 01/04/08; reports mirrored to 05. No commits made.\n')
                mirror();return
            mirror();time.sleep(60)
    except BaseException as exc:
        write(HERE/'INCIDENT-collector.json',dict(utc=time.time(),error=str(exc),traceback=traceback.format_exc(),outcomes_inspected=False))
        (HERE/'RESUME.md').write_text(f'# S3 resume\n\nCollector STOPPED: {exc}. No retry loop. Do not assume remote workers are dead or restart them. Preserve all receipts and inspect INCIDENT-collector.json and detached logs. Outcome barrier remains required. Attempt {args.attempt}; manifest {sha}.\n')
        (HERE/'PROGRESS.md').write_text(f'# S3 progress\n\nCollector stopped; {exc}. See RESUME.md.\n')
        try:mirror()
        except Exception:pass
        raise
if __name__=='__main__':main()
