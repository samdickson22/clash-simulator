import sys,json,time,subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[4];sys.path[:0]=[str(R/'scripts'),str(R/'src')]
from smoke_reference_battle import request
from collect_l1_rendered import ADB
H=Path(__file__).resolve().parent;o=json.loads((H/'emulator/complete.json').read_text());call=lambda c:request(o['probe_port'],c)
call('speed 4')
for _ in range(36):
 s=call('observe')
 if s['ended']:break
 call('advance-native 200')
call('speed 1');time.sleep(1)
(H/'terminal-preflight.json').write_text(json.dumps(call('observe'),indent=2))
(H/'terminal-preflight.png').write_bytes(subprocess.check_output([str(ADB),'-s',o['serial'],'exec-out','screencap','-p']))
print('terminal probe done',flush=True)
