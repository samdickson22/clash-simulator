"""Resume only the dedicated official AVD. Does not launch a battle or recreate data."""
import json
import os
from pathlib import Path
import subprocess
import time
from official_loop import ROOT,SDK,AVD,NAME,SERIAL,owned_pid

WORKSPACE=ROOT.parents[3]
DETACH=WORKSPACE/'reports/strategy_council_20260928/pilot/detach.sh'

def main():
    try:
        print(json.dumps({'already_running':True,'pid':owned_pid()}));return
    except (subprocess.CalledProcessError,FileNotFoundError):pass
    # Never commandeer another process on these dedicated ports.
    for port in [5590,5591,8590]:
        found=subprocess.run(['lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True)
        if found.returncode==0:raise RuntimeError(f'Port {port} occupied')
    if not (AVD/'config.ini').exists():raise RuntimeError('Official AVD missing')
    env={**os.environ,'ANDROID_AVD_HOME':str(AVD.parent),
        'ANDROID_USER_HOME':str(AVD.parent.parent/'android'),'ANDROID_HOME':str(SDK),
        'PYTHONDONTWRITEBYTECODE':'1'}
    argv=[str(SDK/'emulator/emulator'),'-avd',NAME,'-port','5590','-grpc','8590',
        '-grpc-use-token','-gpu','host','-memory','3072','-cores','2','-no-snapshot',
        '-partition-size','3072','-no-boot-anim','-no-audio','-no-window']
    stamp=time.strftime('%Y%m%d-%H%M%S')
    pid=int(subprocess.check_output([str(DETACH),str(ROOT/f'emulator-{stamp}.log'),*argv],env=env,text=True))
    time.sleep(1)
    receipt={'pid':pid,'avd':NAME,'serial':SERIAL,'grpc_port':8590,'avd_home':str(AVD.parent),
        'requested_ram_mb':3072,'requested_data_virtual_gib':3,'snapshots':False,
        'gpu':'host','resolution':[720,1280],'command':argv,'started_at':time.time()}
    (ROOT/'ownership.json').write_text(json.dumps(receipt,indent=2)+'\n')
    owned_pid()
    guard_pid=int(subprocess.check_output([str(DETACH),str(ROOT/f'guard-{stamp}.log'),
        str(WORKSPACE/'.venv/bin/python'),str(ROOT/'storage_guard.py')],env=env,text=True))
    time.sleep(1)
    print(json.dumps({'emulator_pid':pid,'storage_guard_pid':guard_pid}))

if __name__=='__main__':main()
