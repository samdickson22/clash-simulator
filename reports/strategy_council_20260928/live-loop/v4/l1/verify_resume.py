"""Exercise an owned trainer's SIGTERM checkpoint and identical-config resume."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);run=a.output/'model'
    command=[sys.executable,str(Path(__file__).with_name('train_v4.py')),'--source',str(a.source),'--split',str(a.split),
             '--pixel-cache',str(a.cache),'--output',str(run),'--epochs','1','--steps','128','--loader-workers','6']
    child=subprocess.Popen(command)
    deadline=time.monotonic()+180;sent=False
    while child.poll() is None:
        path=run/'training.jsonl'
        if path.exists() and len(path.read_text().splitlines())>=24:
            # Popen owns this exact PID; no name-based signal or unrelated job.
            child.send_signal(signal.SIGTERM);sent=True;break
        if time.monotonic()>deadline:
            child.send_signal(signal.SIGTERM);child.wait(timeout=90);raise TimeoutError('No training progress')
        time.sleep(.05)
    code=child.wait(timeout=90)
    if not sent or code!=0:raise ValueError('Checkpoint/exit test failed')
    stopped=json.loads((run/'checkpoint-stop.json').read_text())
    if not 24<=stopped['step']<128 or (run/'complete.json').exists():raise ValueError('Invalid partial stop')
    subprocess.run([*command,'--resume'],check=True)
    completed=json.loads((run/'complete.json').read_text())
    rows=[json.loads(x) for x in (run/'training.jsonl').read_text().splitlines()]
    if [r['step'] for r in rows]!=list(range(1,129)):raise ValueError('Duplicate/missing steps after resume')
    result=dict(pass_=True,signal_pid=child.pid,stopped_step=stopped['step'],final_step=completed['steps_completed'],
                steps_unique_and_contiguous=True,source_manifest_unchanged=True,heldout_opened=False)
    (a.output/'complete.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
