"""Finish training with a fresh MPS process after each saved epoch."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
from scripts.run_l1_v1_pipeline import V1,PY,main,progress
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO']='0.4'
os.environ['PYTORCH_MPS_LOW_WATERMARK_RATIO']='0.25'
for attempt in range(6):
    deadline=time.monotonic()+600
    while shutil.disk_usage(V1).free<8*1024**3:
        if time.monotonic()>deadline:raise RuntimeError('No safe disk headroom for a fresh training process')
        time.sleep(10)
    logfile=V1/f'train-epoch-process-{attempt}.log'
    with logfile.open('w') as log:
        child=subprocess.Popen([str(PY),'scripts/resume_l1_training.py','--output',str(V1/'model'),'--one-epoch'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        receipt={'wrapper_pid':os.getpid(),'training_pid':child.pid,'attempt':attempt,'started_at':time.time()}
        (V1/'resume-process.json').write_text(json.dumps(receipt)+'\n')
        progress(f'Fresh-process training attempt {attempt}, owned trainer PID {child.pid}.')
        result=child.wait()
    if result==75:
        saved=json.loads((V1/'model/epoch-phase.json').read_text())
        progress(f'Completed epoch {saved["completed_epoch"]}; released its MPS process before the next epoch.')
        time.sleep(5)
        continue
    if result:
        if 'L1 host resource guard' in logfile.read_text():
            progress('Resource guard stopped an incomplete epoch; retaining the last complete checkpoint.')
            time.sleep(10)
            continue
        raise RuntimeError(f'Training failed with exit {result}; see {logfile.name}')
    (V1/'train-complete.json').write_text(json.dumps({'exit_code':0,'resumed':True,'completed_at':time.time()})+'\n')
    main()
    break
else:
    raise RuntimeError('Bounded training continuation attempts exhausted')
