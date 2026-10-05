"""Owned continuation after the recorded resource stop."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))
from scripts.run_l1_v1_pipeline import V1,PY,main,progress
os.environ['PYTORCH_MPS_HIGH_WATERMARK_RATIO']='0.4'
os.environ['PYTORCH_MPS_LOW_WATERMARK_RATIO']='0.25'
progress('Resuming the latest completed checkpoint at batch 8 with CPU validation metrics and bounded MPS memory.')
with (V1/'train-resume.log').open('w') as log:
    child=subprocess.Popen([str(PY),'scripts/resume_l1_training.py','--output',str(V1/'model')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    (V1/'resume-process.json').write_text(json.dumps({'wrapper_pid':os.getpid(),'training_pid':child.pid,'started_at':time.time()})+'\n')
    result=child.wait()
if result:
    (V1/'resume-failure.json').write_text(json.dumps({'exit_code':result,'at':time.time()})+'\n')
    raise SystemExit(result)
(V1/'train-complete.json').write_text(json.dumps({'exit_code':0,'resumed':True,'completed_at':time.time()})+'\n')
main()
