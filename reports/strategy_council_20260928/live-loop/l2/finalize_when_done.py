"""Detached reporting and owned-emulator cleanup after all evaluation workers finish."""
import json,subprocess,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[3]
def progress(s):
 with (H/'PROGRESS.md').open('a') as f:f.write(f'\n{time.strftime("%Y-%m-%d %H:%M:%S")}: {s}\n')
 print(s,flush=True)
while not (H/'evaluation-complete.json').exists():
 if (H/'pipeline-error.json').exists():
  progress('Finalizer stopped because evaluation reported an error; preserve run for repair.');sys.exit(1)
 time.sleep(10)
progress('All registered evaluation workers completed. Starting frozen-outcome analysis.')
with (H/'analysis.log').open('wb') as f:
 result=subprocess.run([str(R/'.venv/bin/python'),'-B',str(H/'analyze.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT)
progress('Analysis exit '+str(result.returncode))
sys.path[:0]=[str(R/'scripts'),str(H/'runtime/src')]
from certify_l1_timing_v3 import verify_owner
from collect_l1_rendered import ADB
owner=json.loads((H/'emulator/complete.json').read_text());verify_owner(owner)
command=subprocess.check_output(['ps','-p',str(owner['pid']),'-o','command='],text=True).strip()
from smoke_reference_battle import request
request(owner['probe_port'],'pause');request(owner['probe_port'],'render off')
receipt=subprocess.run([str(ADB),'-s',owner['serial'],'emu','kill'],capture_output=True,text=True,timeout=15)
for _ in range(100):
 test=subprocess.run(['ps','-p',str(owner['pid']),'-o','command='],capture_output=True,text=True)
 if test.returncode:break
 time.sleep(.1)
stopped=test.returncode!=0
(H/'stop.json').write_text(json.dumps(dict(time=time.time(),pid=owner['pid'],serial=owner['serial'],verified_command=command,
 adb_returncode=receipt.returncode,stopped=stopped,analysis_exit=result.returncode),indent=2)+'\n')
progress(f'Owned emulator cleanup verified={stopped}. No foreign process touched.')
if result.returncode or not stopped:sys.exit(1)
(H/'complete.json').write_text(json.dumps(dict(time=time.time(),pairs=48,report='RESULTS.md',emulator_stopped=True),indent=2)+'\n')
progress('L2 evaluation, analysis, report and owned-emulator cleanup complete; L3 verdict remains NOT READY.')
