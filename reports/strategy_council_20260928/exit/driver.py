"""Resumable owned-process supervisor. Launch only through pilot/detach.sh."""
import argparse
import subprocess
import time
import traceback
from common import *

COMMAND = f'bash {COUNCIL}/pilot/detach.sh {HERE}/logs/driver.log --cwd {ROOT} nice -n 10 {ROOT}/.venv/bin/python -B {HERE}/driver.py'
DONE=[]

def progress(stage, running, commands):
    snapshots=[]
    for out in sorted(HERE.glob('it[123]')):
        snapshots.append(f"{out.name}: {len(list((out/'games').glob('*.json')))} collection games, {len(list((out/'search').glob('*.json')))} search evaluation games, fit receipt {(out/'fit.json').exists()}, result {(out/'result.json').exists()}.")
    text='\n'.join(['# ExIt progress','',f'Updated UTC: {datetime.now(timezone.utc).isoformat()}',f'Driver PID: {os.getpid()}',
        f'Done: {"; ".join(DONE)}',f'Running stage: {stage}',f'Running direct child PIDs: {running}',
        'Policy evaluation wrappers may own up to three nice-10 evaluator children. No other heavy stages overlap.',
        *snapshots,'','Next: advance the declared collection -> fit -> policy evaluation -> search evaluation -> acceptance sequence; stop on rejection/error.',
        '', 'Exact active commands:',*["`"+' '.join(cmd)+"`" for cmd in commands], '', 'Exact resume command after confirming this driver is no longer running:',f'`{COMMAND}`',
        '', 'A running driver must not be duplicated. Only exit/ is writable for this task. Source/data pins are in manifest.json.'])+'\n'
    tmp=HERE/'PROGRESS.tmp.md';tmp.write_text(text);tmp.replace(HERE/'PROGRESS.md')

def run(stage, commands):
    processes=[];handles=[]
    try:
        for index,cmd in enumerate(commands):
            logpath=HERE/'logs'/f'{stage}-{index}.log';logpath.parent.mkdir(exist_ok=True)
            handle=logpath.open('a');handles.append(handle)
            process=subprocess.Popen(cmd,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT)
            processes.append(process)
        while any(p.poll() is None for p in processes):
            progress(stage,[p.pid for p in processes if p.poll() is None],commands)
            time.sleep(10)
        codes=[p.returncode for p in processes]
        write_json(HERE/'receipts'/f'{stage}.json',dict(commands=commands,pids=[p.pid for p in processes],returncodes=codes))
        if any(codes):raise RuntimeError(f'{stage} failed: {codes}; inspect logs')
        verify();DONE.append(stage);progress('between steps',[],[])
    finally:
        # Wait for siblings we started if one command raises. Never signal foreign jobs.
        for p in processes:p.wait()
        for h in handles:h.close()

def cmd(script,*args):
    # The driver already runs at nice 10; descendants inherit it.
    return [str(ROOT/'.venv/bin/python'),'-B',str(HERE/script),*map(str,args)]

def main(smoke=False):
    verify();config();progress('starting',[],[])
    if smoke:
        run('smoke',[cmd('collect.py','--iteration',1,'--smoke','--worker',i,'--workers',2) for i in range(2)])
        run('validate',[cmd('validate.py')]);return
    for it in range(1,config().iterations+1):
        out=folder(it)
        if (out/'result.json').exists():
            result=json.loads((out/'result.json').read_text());DONE.append(f'iteration {it} already evaluated')
            if not result['accepted']:break
            continue
        run(f'it{it}-collect',[cmd('collect.py','--iteration',it,'--worker',i,'--workers',config().workers) for i in range(config().workers)])
        if not (out/'fit.json').exists():run(f'it{it}-fit',[cmd('fit.py','--iteration',it)])
        for which in ('initial','student'):
            run(f'it{it}-policy-{which}',[cmd('evaluate.py','--iteration',it,'--kind','policy','--which',which)])
        run(f'it{it}-search',[cmd('evaluate.py','--iteration',it,'--kind','search','--worker',i) for i in range(config().workers)])
        run(f'it{it}-analyze',[cmd('analyze.py','--iteration',it)])
        if not json.loads((out/'result.json').read_text())['accepted']:break
    write_json(HERE/'completion.json',dict(complete=True,pid=os.getpid(),done=DONE,bytes=budget()))
    progress('complete',[],[])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--smoke',action='store_true');args=p.parse_args()
    try:main(args.smoke)
    except BaseException:
        write_json(HERE/'error.json',dict(pid=os.getpid(),traceback=traceback.format_exc()))
        progress('ERROR: inspect error.json and logs',[],[]);raise
