"""Build only new, receipt-pinned shards on home 03 under fleet_run.

Planning consumes compact previously verified evidence. It grants neither formal
population admission nor heldout access. Eight workers fit the console cap.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--label',required=True)
    p.add_argument('--admitted',type=Path,required=True)
    a=p.parse_args()
    if socket.gethostname().split('.')[0]!='127x03':raise ValueError('Home 03 only')
    if not all(c.isalnum() or c in '-_.' for c in a.label):raise ValueError('Invalid label')
    code=Path(__file__).resolve().parent
    split=code.parent/'split.json';evidence=code/'receipts/preformal-cache-20261008'
    jobs=Path('/mpac/sdicks02/jobs/clasher');prefix=jobs/a.label
    plan=Path(str(prefix)+'-plan.json');stage=Path(str(prefix)+'-stage.json')
    source=Path('/mpac/sdicks02/repos/clasher-v4-cpu/matches')
    cache=Path('/mpac/sdicks02/repos/clasher-v4-cache')
    def run(name,*args):subprocess.run([sys.executable,'-B',str(code/name),*map(str,args)],check=True)
    run('cache_extension_v4.py','--current',a.admitted,
        '--base-manifest',evidence/'v4-cache-gather-20261008-18r10-manifest.json',
        '--base-inventory',evidence/'v4-cache-extend-20261008-18r10-stage.json',
        '--extra-base',evidence/'v4-cache-unique-20261008-16r4-manifest.json',
        evidence/'v4-cache-unique-20261008-16r4-plan.json','--output',plan)
    inv=json.loads(plan.read_text())
    if not inv['episodes']:raise ValueError('No new shards; do not stage an unfiltered population')
    run('stage_training.py','--destination',source,'--split',split,'--episodes',*inv['episodes'])
    staged=(source/'stage-inventory.json').read_bytes();actual=json.loads(staged)
    if actual['receipt_sha256']!=inv['receipt_sha256']:raise ValueError('Staged source differs from pinned plan')
    with stage.open('xb') as f:f.write(staged)
    run('build_cache.py','--source',source,'--cache',cache,'--split',split,
        '--inventory',plan,'--workers',8,'--budget-gb',124,'--receipt',str(prefix)+'-build.json')
    run('cache_manifest.py','--source',source,'--cache',cache,'--split',split,
        '--inventory',plan,'--output',str(prefix)+'-manifest.json')


if __name__=='__main__':main()
