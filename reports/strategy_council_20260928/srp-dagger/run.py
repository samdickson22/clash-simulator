"""Detached coordinator. Only its own children are started or managed."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PYTHON = ROOT / '.venv/bin/python'
EVAL = HERE.parent/'human-prior-p16/evaluation'


def note(text):
    stamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    with (HERE/'PROGRESS.md').open('a') as stream:
        stream.write(f'\n## {stamp}\n\n{text}\n')
    print(text, flush=True)


def alive(pid):
    try: os.kill(pid,0); return True
    except ProcessLookupError: return False


def launch(name, args):
    command = ['nice','-n','10',str(PYTHON),'-B',*map(str,args)]
    with (HERE/'logs'/f'{name}.log').open('w') as stream:
        proc = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    note(f'Running {name}, PID {proc.pid}. Exact command: `{ " ".join(command) }`')
    return proc


def finish(name,proc):
    while proc.poll() is None: time.sleep(10)
    if proc.returncode: raise RuntimeError(f'{name} PID {proc.pid} failed, exit {proc.returncode}')
    note(f'Done: {name}, PID {proc.pid}, exit 0.')


def main(first_pid, initial_pid, resume_collector_pid=None):
    note(f'Coordinator PID {os.getpid()}. Waiting on owned first-game PID {first_pid}; '
         f'initial evaluation PID {initial_pid} remains active. Next: validation, collection, fit, final evaluation.')
    if resume_collector_pid:
        first = None
        note(f'Adopt existing owned collector PID {resume_collector_pid}; do not relaunch games 1-19.')
    else:
        while alive(first_pid): time.sleep(10)
        if not (HERE/'games/game-000.json').exists(): raise RuntimeError('first game failed')
        finish('verify-first',launch('verify-first',[HERE/'verify.py']))
        first = launch('collect-01-19',[HERE/'kit.py','collect','--start','1','--stop','20'])
    while alive(initial_pid):
        if first is not None and first.poll() not in (None,0): raise RuntimeError('first collection worker failed')
        time.sleep(10)
    initial_files = list((EVAL/'srp-dagger-initial-s2902').glob('*.games.json'))
    if len(initial_files)!=6 or any(len(json.loads(p.read_text()))!=32 for p in initial_files):
        raise RuntimeError('initial evaluation incomplete')
    note('Done: initial evaluation, six cells x 32 games. Next: second collection worker.')
    second = launch('collect-20-39',[HERE/'kit.py','collect','--start','20','--stop','40'])
    if first is not None:
        finish('collect-01-19',first)
    else:
        while alive(resume_collector_pid):
            if second.poll() not in (None,0): raise RuntimeError('second collector failed')
            time.sleep(10)
        if not all((HERE/'games'/f'game-{g:03d}.json').exists() for g in range(20)):
            raise RuntimeError('adopted collector incomplete')
        note('Done: adopted collector games 0-19 have complete receipts; its OS exit status is unavailable.')
    finish('collect-20-39',second)
    finish_pilot()


def finish_pilot():
    finish('verify-all',launch('verify-all',[HERE/'verify.py']))
    finish('fit',launch('fit',[HERE/'fit.py']))
    finish('eval-final',launch('eval-final',[HERE/'evaluate.py','--checkpoint',HERE/'student.pt',
        '--name','srp-dagger-it1-s2902','--parallel','2','--trace-games','0']))
    finish('report',launch('report',[HERE/'report.py']))
    note('Done: 40 collected games, one fit, both 192-game evaluations and paired analysis. '
         'No owned heavy jobs remain. Results: results.json. Next: review receipts and final report.')
    (HERE/'completion.json').write_text(json.dumps({'complete':True,'pid':os.getpid()})+'\n')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--first-pid',type=int,required=True)
    parser.add_argument('--initial-pid',type=int,required=True)
    parser.add_argument('--resume-collector-pid',type=int)
    args=parser.parse_args()
    try: main(args.first_pid,args.initial_pid,args.resume_collector_pid)
    except Exception as exc:
        note(f'FAILED: {exc!r}. See logs. No success receipt written.')
        raise
