"""Hub-only receipt collection. Reports completeness; opens strength only at end."""
import bootstrap
from bootstrap import HERE,ROOT
import argparse,json,subprocess,time
from pathlib import Path
from evaluate import write

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wait',action='store_true');args=ap.parse_args()
    assert __import__('socket').gethostname().split('.')[0]=='127x01'
    execution=json.loads((HERE/'execution.json').read_text())
    status=HERE/'collected-status';status.mkdir(exist_ok=True)
    while True:
        for host in ('127x04','127x07','127x08'):
            for pattern in ('confirmation/','worker-*-done.json','launch-*.json'):
                dest=HERE/'confirmation' if pattern=='confirmation/' else HERE
                dest.mkdir(exist_ok=True)
                proc=subprocess.run(['rsync','-a',*(['--ignore-existing'] if pattern=='confirmation/' else []),'--exclude=*.tmp',f'{host}:{HERE}/{pattern}',str(dest)+'/'],capture_output=True,text=True)
                if proc.returncode not in (0,23):raise RuntimeError(proc.stderr)
        complete=0;failed=[]
        for worker in execution['workers']:
            i=worker['index'];host=worker['host']
            done=HERE/f'worker-{i}-done.json'
            launches=[]
            for p in sorted(HERE.glob(f'launch-{host}-*.json'),key=lambda p:json.loads(p.read_text())['launched_at']):
                launches.extend(w for w in json.loads(p.read_text())['workers'] if w['index']==i)
            if not launches:continue
            attempt=launches[-1];path=f'/mpac/sdicks02/jobs/clasher/{attempt["label"]}.exit'
            proc=subprocess.run((['cat',path] if host=='127x01' else ['ssh','-o','BatchMode=yes',host,'cat',path]),capture_output=True,text=True)
            if proc.returncode:continue
            code=proc.stdout.strip()
            if code!='0':failed.append(dict(index=i,host=host,label=attempt['label'],exit=code));continue
            if not done.exists():continue
            (status/f'worker-{i}.exit').write_text(code+'\n')
            __import__('shutil').copyfile(done,status/done.name)
            log=path.removesuffix('.exit')+'.log'
            proc=subprocess.run((['cat',log] if host=='127x01' else ['ssh','-o','BatchMode=yes',host,'cat',log]),capture_output=True,text=True,check=True)
            (status/f'worker-{i}.log').write_text(proc.stdout)
            complete+=1
        receipts=len(list((HERE/'confirmation').glob('*.json')))
        write(HERE/'monitor.json',dict(utc=time.time(),partitions_complete=complete,partitions_total=len(execution['workers']),receipts=receipts,failures=failed))
        print(json.dumps(dict(partitions=complete,receipts=receipts,failures=failed)),flush=True)
        if failed:raise RuntimeError('technical worker failure; retained receipts need inspection')
        if complete==len(execution['workers']):
            subprocess.run([str(ROOT/'.venv/bin/python'),'-B',str(HERE/'analyze.py')],check=True)
            return
        if not args.wait:return
        time.sleep(60)

if __name__=='__main__':main()
