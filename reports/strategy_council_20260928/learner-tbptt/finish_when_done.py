"""Bounded, restart-aware supervisor for this task's own experiment receipts."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
RUNNER=ROOT/'run_experiment.py'
PINNED=ROOT/'runtime-src-fixed'
PYTHON=REPO/'.venv/bin/python'
LABELS=('ab-full-pinned','ab-t64-fixed')


def progress(message):
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    line=f'{stamp} {message}'
    with (ROOT/'PROGRESS.md').open('a') as f: f.write(line+'\n')
    print(line,flush=True)


def rows(label):
    path=ROOT/'runs'/label/'monitor.jsonl'
    # A writer can have a partial final line while running.
    result=[]
    if path.exists():
        for line in path.read_text().splitlines():
            try: result.append(json.loads(line))
            except json.JSONDecodeError: break
    return result


def complete(label):
    path=ROOT/'runs'/label/'completion.json'
    return path.exists() and json.loads(path.read_text())['completed']


def alive(label):
    path=ROOT/'runs'/label/'provenance.json'
    if not path.exists(): return False
    pid=json.loads(path.read_text())['pid']
    r=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
    return r.returncode==0 and str(RUNNER.relative_to(REPO)) in r.stdout and f'{label}.toml' in r.stdout


def benchmark_from_prefix(label,target):
    selected=[r for r in rows(label) if r['decisions']<=4096]
    if not selected or selected[-1]['decisions']!=4096: return
    d=ROOT/'runs'/target
    if d.exists(): return
    d.mkdir()
    source=ROOT/'runs'/label
    (d/'provenance.json').write_bytes((source/'provenance.json').read_bytes())
    (d/'monitor.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in selected))
    receipt=dict(completed=True,decisions=4096,updates=len(selected),derived_from=f'{label}: first 4096 decisions',
                 update_ms_per_decision=1000*sum(r['update_seconds'] for r in selected)/4096,
                 decisions_per_second=4096/sum(r['update_seconds']+r['collect_seconds'] for r in selected))
    (d/'completion.json').write_text(json.dumps(receipt,indent=2))
    progress(f'Pinned benchmark prefix saved: {target}: {receipt}')


def main():
    # Atomic ownership marker prevents accidentally starting two supervisors.
    lock=ROOT/'supervisor.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(fd,str(os.getpid()).encode()); os.close(fd)
    try:
        progress(f'Supervisor PID {os.getpid()}: waiting for first T64 to finish, then launch corrected T64 into its slot.')
        waiting=time.monotonic()
        while (not complete('ab-t64-pinned') and not (ROOT/'runs/ab-t64-pinned/rejected.json').exists()) or alive('ab-t64-pinned'):
            if not complete('ab-t64-pinned') and not (ROOT/'runs/ab-t64-pinned/rejected.json').exists() and not alive('ab-t64-pinned'):
                raise RuntimeError('first T64 stopped before its receipt')
            if time.monotonic()-waiting > 86400:
                raise TimeoutError('first T64 did not finish within 24h')
            time.sleep(30)
        config=ROOT/'configs/ab-t64-fixed.toml'
        config.write_text((ROOT/'configs/ab-t64.toml').read_text().replace('"ab-t64"','"ab-t64-fixed"'))
        assert not (ROOT/'runs/ab-t64-fixed').exists()
        result=subprocess.run([str(REPO/'reports/strategy_council_20260928/pilot/detach.sh'),
            str(ROOT/'logs/ab-t64-fixed.log'),'nice','-n','10','env',f'PYTHONPATH={PINNED}',
            str(PYTHON),str(RUNNER),str(config)],cwd=REPO,check=True,capture_output=True,text=True)
        progress(f'Corrected T64 launched PID {result.stdout.strip()}, fixed windows with reset masks.')
        for _ in range(60):
            if (ROOT/'runs/ab-t64-fixed/provenance.json').exists(): break
            time.sleep(1)
        a,b=[json.loads((ROOT/'runs'/x/'provenance.json').read_text()) for x in LABELS]
        differences=[key for key,value in a['source_sha256'].items() if b['source_sha256'].get(key)!=value]
        assert differences == ['src/clasher/rl/tbptt.py'], differences
        assert a['checkpoint_sha256']==b['checkpoint_sha256']
        progress('A/B source differs only in the intentional tbptt.py chunk correction; checkpoint and engine sources match, default byte identity reverified.')
        started=time.monotonic(); last={}; t32_launched=False
        while time.monotonic()-started<90000:
            for label in LABELS:
                r=rows(label)
                count=r[-1]['decisions'] if r else 0
                bucket=count//10000
                if last.get(label)!=bucket:
                    progress(f'{label}: {count} decisions, completed={complete(label)}')
                    last[label]=bucket
                if not complete(label) and not alive(label):
                    raise RuntimeError(f'{label} stopped without a complete receipt at {count} decisions')
            benchmark_from_prefix(LABELS[0],'bench-full-pinned')
            benchmark_from_prefix(LABELS[1],'bench-t64-fixed')
            if not t32_launched and any(complete(x) and not alive(x) for x in LABELS):
                label='bench-t32-fixed'
                config=ROOT/'configs'/f'{label}.toml'
                config.write_text((ROOT/'configs/bench-t32.toml').read_text().replace('"bench-t32"','"bench-t32-fixed"'))
                assert not (ROOT/'runs'/label).exists()
                cmd=[str(REPO/'reports/strategy_council_20260928/pilot/detach.sh'),str(ROOT/'logs'/f'{label}.log'),
                     'nice','-n','10','env',f'PYTHONPATH={PINNED}',str(PYTHON),str(RUNNER),str(config)]
                result=subprocess.run(cmd,cwd=REPO,check=True,capture_output=True,text=True)
                progress(f'Launched pinned T32 benchmark PID {result.stdout.strip()} into freed A/B slot.')
                t32_launched=True
            if t32_launched and complete('bench-t32-fixed') and all(complete(x) for x in LABELS):
                if any(alive(x) for x in (*LABELS,'bench-t32-fixed')):
                    time.sleep(5); continue
                subprocess.run([str(PYTHON),str(ROOT/'summarize.py'),'--require-complete','--plot'],cwd=REPO,check=True)
                (ROOT/'runs/bench-t32-fixed/final.pt').unlink(missing_ok=True)
                progress('Both 150k A/B receipts and pinned T32 benchmark complete; summary and monitor plot generated, benchmark checkpoint removed. Final model/curve review still required.')
                (ROOT/'supervisor-completion.json').write_text(json.dumps(dict(completed=True,needs_final_review=True)))
                return
            if t32_launched and (ROOT/'runs/bench-t32-fixed/provenance.json').exists() and not complete('bench-t32-fixed') and not alive('bench-t32-fixed'):
                raise RuntimeError('pinned T32 benchmark stopped without completion')
            time.sleep(30)
        raise TimeoutError('supervisor exceeded 25 hours')
    except Exception as exc:
        progress(f'Supervisor failed: {type(exc).__name__}: {exc}')
        (ROOT/'supervisor-completion.json').write_text(json.dumps(dict(completed=False,error=str(exc))))
        raise
    finally:
        lock.unlink(missing_ok=True)

if __name__=='__main__': main()
