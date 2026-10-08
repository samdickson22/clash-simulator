"""Synthetic checkpoint snapshots and real bounded child shutdown; fleet only."""
import argparse
import json
from pathlib import Path
import signal
import sys
import time
from unittest.mock import patch

import lease_lifecycle_v4 as life


def main(root):
    root.mkdir();run=root/'run';(run/'model').mkdir(parents=True)
    (run/'model/last.pt').write_bytes(b'checkpoint-v1')
    (run/'model/hud.npz').write_bytes(b'hud')
    (run/'model/training-pixels').mkdir();(run/'model/training-pixels/a.jpg').write_bytes(b'pixels')
    (run/'model/last.tmp').write_bytes(b'incomplete')
    checks=0
    def check(value):
        nonlocal checks
        assert value;checks+=1
    def refuses(fn):
        nonlocal checks
        try:fn()
        except ValueError:checks+=1
        else:raise AssertionError('Unsafe lifecycle operation accepted')
    result=life.snapshot(run,root/'snapshot')
    check(set(result['files_sha256'])=={'model/last.pt','model/hud.npz'})
    check(result['checkpoint_count']==1)
    (run/'model/last.pt').write_bytes(b'checkpoint-v2')
    check((root/'snapshot/model/last.pt').read_bytes()==b'checkpoint-v1')
    (run/'model/link.pt').symlink_to(root/'snapshot/model/last.pt')
    refuses(lambda:life.snapshot(run,root/'bad-symlink'))
    # Fixture symlink is retained; subsequent supervisor tests use fake backups.
    saved=[]
    def backup(journal):saved.append(str(journal));return dict(status='verified')
    check(life.supervise([sys.executable,'-c','pass'],root/'success',time.time()+60,
        backup,interval=1,grace=1,lead=5)==0)
    check(len(saved)>=2)
    saved.clear()
    child='import signal,time; signal.signal(signal.SIGTERM,lambda *a:None); time.sleep(60)'
    begin=time.monotonic()
    check(life.supervise([sys.executable,'-c',child],root/'deadline',time.time()+2.5,
        backup,interval=1,grace=.5,lead=1)==75)
    check(time.monotonic()-begin<6)
    check(json.loads((root/'deadline/exit.json').read_text())['stopped'])
    def broken(journal):raise RuntimeError('Destination checksum failure')
    check(life.supervise([sys.executable,'-c','import time; time.sleep(60)'],root/'backup-failure',
        time.time()+60,broken,interval=1,grace=.5,lead=1)==75)
    check(json.loads((root/'backup-failure/exit.json').read_text())['backup_error'] is not None)
    refuses(lambda:life.supervise([],root/'late',time.time(),backup))
    refuses(lambda:life.supervise([],root/'slow',time.time()+60,backup,interval=3601))
    # A recycled PID must never receive a signal.
    class Process:
        def create_time(self):return 2
        def send_signal(self,s):raise AssertionError('Recycled PID signalled')
    with patch.object(life.psutil,'Process',return_value=Process()):life.signal_verified({123:1},signal.SIGKILL)
    checks+=1
    print(json.dumps(dict(checks=checks,passed=True,synthetic_only=True,heldout_payloads_opened=False)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    main(p.parse_args().output)
