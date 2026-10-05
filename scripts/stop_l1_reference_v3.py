"""Stop one reference emulator identified by this task's launch receipt."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from certify_l1_timing_v3 import verify_owner
from collect_l1_rendered import progress


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('ownership',type=Path)
    a=p.parse_args();receipt=json.loads(a.ownership.read_text());verify_owner(receipt)
    os.kill(receipt['pid'],signal.SIGTERM)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if subprocess.run(['ps','-p',str(receipt['pid'])],capture_output=True).returncode:
            break
        time.sleep(.2)
    else:raise TimeoutError('Owned emulator has not stopped')
    (a.ownership.parent/'stop.json').write_text(json.dumps(dict(pid=receipt['pid'],
        stopped=True,firewall_verified_before_stop=True,time=time.time()))+'\n')
    progress(f"v3 stopped owned {receipt['serial']}, PID {receipt['pid']}, after firewall verification.")


if __name__=='__main__':main()
