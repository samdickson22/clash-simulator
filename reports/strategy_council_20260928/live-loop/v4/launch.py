"""Use the audited L2 launcher with the retained v4 base config and private ports.

Usage: python launch.py NEW_RECEIPT_DIR [--resume-owned OLD_RECEIPT_DIR]
Never adopts an emulator without the launcher's matching ownership receipt.
"""
import json
import os
from pathlib import Path
import sys
import subprocess
from common import HERE,ROOT,write
sys.path.insert(0,str(ROOT/'scripts'))
import launch_l1_reference as launcher

if __name__=='__main__':
    output=Path(sys.argv[1]).resolve()
    config=Path.home()/'.cache/clasher-live-v4/launch-config'
    config.mkdir(parents=True,exist_ok=True)
    write(config/'plan.json',dict(config=json.loads((HERE/'base-config.json').read_text())))
    launcher.CAPTURE=config
    os.environ['ANDROID_ADB_SERVER_PORT']='5042'
    sys.argv.extend(['--gpu','host','--console-port','5584','--probe-port','26794','--grpc-port','8558'])
    launcher.main()
    receipt=json.loads((output/'complete.json').read_text())
    receipt.update(render_backend='host',adb_port=5042,process_start=subprocess.check_output(['/bin/ps','-p',str(receipt['pid']),'-o','lstart='],text=True).strip())
    write(output/'complete.json',receipt)
    write(HERE/'emulator-host/complete.json',receipt)
