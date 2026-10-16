"""Light 05 coordinator: independent true-deck bank and atomic paired blocks."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import fullpool_clean

ROOT=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2');D=ROOT/'fullpool'
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
REPO='/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool'
HOSTS=('127x01','127x03','127x04')

def utc():return subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip()
def dump(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)
def cmd(argv):return subprocess.check_output(list(map(str,argv)),text=True,stderr=subprocess.STDOUT)
def ssh(host,argv):return cmd(['ssh',host,shlex.join(list(map(str,argv)))])
def record(message):
    with (ROOT/'PROGRESS.md').open('a') as f:f.write('\n'+utc()+' '+message+'\n')
def copy_inputs(host):
    files=['fullpool_eval.py','fullpool_worker.py','fullpool_bank.py','fullpool_queue.py','fullpool_entry.py','run-fullpool-pool.sh','fullpool_clean.py','fullpool_resume.py','fullpool_resume_entry.py','fullpool_resume_queue.py','fullpool_wait_entry.py','run-fullpool-resume.sh']
    cmd(['rsync','-a',*[ROOT/f for f in files],f'{host}:{ROOT}/'])
    files=['manifest.json','player-config.json','gate-approved.json','repeat-proof.json','vocab-combined.json','model-pins.json','resume-manifest.json']
    cmd(['rsync','-a',*[D/f for f in files],f'{host}:{D}/'])
    ssh(host,['mkdir','-p',D/'validation/rows'])
    cmd(['rsync','-a',D/'validation/bank.json',f'{host}:{D}/validation/'])
def launch(host,label,n):
    receipt=D/f'{label}.receipt.json'
    if receipt.exists():return
    # Probe before creating a detached waiter. Waiting cpu_job command lines
    # themselves enter the shared process count; many waiters can consume
    # the last available room. The actual admission remains atomic below.
    probe=f'if BOT_CPU_TRY=1 /mpac/sdicks02/repos/clasher-bot/bot/exit/cpu_room.sh {n+3}; then echo room; else echo busy; fi'
    if ssh(host,['bash','-c',probe]).strip()!='room':return
    output=ssh(host,['/mpac/sdicks02/repos/clasher-bot/bot/detach.sh',D/f'{label}.log',receipt,
                     'bash',ROOT/'run-fullpool-resume.sh',label,n])
    cmd(['rsync','-a',f'{host}:{receipt}',receipt]);record(f'True-deck serial validation {host} {label} launched {n} workers, separate session/shared fixed CPU lease {n+2}; {output.strip()}')
def main():
    dump(D/'pipeline-process.json',dict(pid=os.getpid(),utc=utc()))
    while not (D/'STOP').exists():
        ready=(D/'resume-manifest.json').exists() and all(p.exists() for p in [ROOT/'selection.json',ROOT/'final-validation/validation/bank.json',D/'repeat-proof.json',D/'strong-smoke-result.json'])
        if not ready:
            dump(D/'pipeline-status.json',dict(utc=utc(),state='waiting for replay proof, scoped strong smoke and screen finalists'));time.sleep(45);continue
        if not (D/'manifest.json').exists():
            # Pure bank construction on 05: no Runtime or game runs here.
            env=dict(os.environ,PYTHONPATH=REPO,PYTHONDONTWRITEBYTECODE='1')
            print(subprocess.check_output([PY,str(ROOT/'fullpool_bank.py')],env=env,text=True),flush=True)
            record('Independent full-pool true-deck validation bank registered before any game; serial no-wall c4/f1a2 replay proof required and checked.')
        bank=json.loads((D/'validation/bank.json').read_text())
        expected=len(bank['cases'])*len(bank['candidates'])*len(bank['players'])
        for host in HOSTS:
            if not (D/f'inputs-resume-{host}.json').exists():
                copy_inputs(host);dump(D/f'inputs-resume-{host}.json',dict(utc=utc()))
        # Full-pool validation has priority after screening. At most32 game
        # workers on01/03 and40 on04; shared admission governs actual room.
        for host in HOSTS[:2]:
            if host == '127x03' and not (ROOT/'projected-parity/receipt.json').exists():
                continue  # Reserve the released small allocation for the required parity check.
            sizes = (4,)  # BOT LEAD: no additional01/03 capacity tonight.
            for i,n in enumerate(sizes):launch(host,f'fpr2-{host[-2:]}-{i}',n)
        # Projected validation is deferred until this variant completes.
        # The first claims fit the allocation released by screening: 01:6,
        # 03:10 and04:42 slots, with optional small additions as room opens.
        launch('127x04','fpr2-04-0',40)
        paths=list((D/'validation/rows').glob('*.json'))
        bad=[]
        for path in paths:
            row=json.loads(path.read_text())
            if fullpool_clean.problems(row):bad.append(str(path))
        assert not bad,bad
        dump(D/'pipeline-status.json',dict(utc=utc(),state='running',rows=len(paths),expected=expected))
        if len(paths)==expected:
            dump(D/'VALIDATION-READY.json',dict(utc=utc(),games=expected));record('True-deck validation complete; all raw rows retained and clean, ready for paired analysis.');return
        time.sleep(45)
if __name__=='__main__':
    try:main()
    except BaseException as error:
        dump(D/'pipeline-error.json',dict(utc=utc(),error=repr(error)));raise
