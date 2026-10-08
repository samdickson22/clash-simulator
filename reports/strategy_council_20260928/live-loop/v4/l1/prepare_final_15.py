"""Final train/validation audits, immutable control assets and T6 conversion.

No fitting, selection or heldout payload access; run inside15's lease wrapper.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys


def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True);p.add_argument('--admitted',type=Path,required=True)
    a=p.parse_args()
    if socket.gethostname().split('.')[0]!='127x15':raise ValueError('T6 host15 only')
    if not a.label or not all(c.isalnum() or c in '-_.' for c in a.label):raise ValueError('Invalid label')
    root=Path('/mpac/sdicks02/repos/clasher-lease');repo=root/'repo';code=Path(__file__).parent
    source=root/'data/v4-matches';jobs=root/'jobs';prefix=jobs/a.label
    admitted=json.loads(a.admitted.read_text());staged=json.loads((source/'stage-inventory.json').read_text())
    if staged['receipt_sha256']!=admitted['receipt_sha256'] or not staged['complete_population']:
        raise ValueError('Full pinned final input staging required')
    files=['reports/strategy_council_20260928/live-loop/l1/'+n for n in
           ('v2/model/last.pt','v1/model/hud.npz','v1/model/detector/weights/best.pt','calibration.json')]
    remote='import pathlib,hashlib,json; r=pathlib.Path("/mpac/sdicks02/repos/clasher"); print(json.dumps({n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in '+repr(files)+'}))'
    pins=json.loads(subprocess.run(['ssh','-o','BatchMode=yes','127x01','python3 -'],input=remote,text=True,capture_output=True,check=True).stdout)
    subprocess.run(['rsync','-a','--checksum','--rsync-path=nice -n 10 rsync','--files-from=-',
        '127x01:/mpac/sdicks02/repos/clasher/',str(repo)+'/'],input='\n'.join(files)+'\n',text=True,check=True)
    if any(hashlib.sha256((repo/n).read_bytes()).hexdigest()!=v for n,v in pins.items()):raise ValueError('Control asset checksum mismatch')
    with Path(str(prefix)+'-control-assets.json').open('x') as f:json.dump(pins,f,indent=2)
    def run(name,*args):subprocess.run([sys.executable,'-B',str(code/name),*map(str,args)],check=True)
    run('audit_labels.py','--source',source,'--split',code.parent/'split.json',
        '--output',str(prefix)+'-labels-raw.json','--workers',4)
    run('audit_execution_clock_v4.py','--source',source,'--split',code.parent/'split.json',
        '--output',str(prefix)+'-timing.json')
    dataset=root/'data'/a.label
    run('prepare_t6.py','--source',source,'--split',code.parent/'split.json','--output',dataset,'--workers',2)
    with Path(str(prefix)+'-complete.json').open('x') as f:
        json.dump(dict(matches=len(staged['receipt_sha256']),dataset=str(dataset),control_assets=pins,
            training_started=False,heldout_payloads_opened=False),f,indent=2)


if __name__=='__main__':main()
