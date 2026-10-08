"""Five-minute, 24-hour receipt wait; never releases extraction implicitly."""
import json,socket,time
from pathlib import Path
DATA=Path('/mpac/sdicks02/repos/clasher/reports/strategy_council_20260928/imitation/data')
p=DATA/'receipts/T1-PASS.json'; out=DATA/'receipts/s122-d1-wait.json'
assert socket.gethostname()=='127x01'
start=time.time(); out.parent.mkdir(parents=True,exist_ok=True)
while True:
    state={'host':socket.gethostname(),'started_unix':start,'checked_unix':time.time(),'poll_seconds':300,'deadline_unix':start+86400,'receipt_path':str(p),'receipt_present':p.exists(),'requires_interface_and_hash_verification_before_T10':True}
    tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(state,indent=2)+'\n');tmp.replace(out)
    print(json.dumps(state),flush=True)
    if p.exists():
        json.loads(p.read_text());break
    if time.time()>=start+86400:raise SystemExit('D1 receipt wait reached 24h; extraction remains blocked')
    time.sleep(min(300,start+86400-time.time()))
