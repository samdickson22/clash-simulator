"""Reject formal-sized/subset union attempts before creating outputs."""
import argparse
from pathlib import Path
import subprocess
import sys


def main(output):
    output.mkdir(exist_ok=False);script=Path(__file__).with_name('train_v4.py')
    cases=[['--epochs','24'],['--epochs','1','--steps','129'],
           ['--epochs','1','--steps','128','--max-matches','1'],
           ['--epochs','1','--steps','128','--pixel-cache','/absent']]
    for i,extra in enumerate(cases):
        dest=output/str(i)
        r=subprocess.run([sys.executable,'-B',str(script),'--source','/absent','--split','/absent',
            '--output',str(dest),'--engineering-union','/absent',*extra],capture_output=True,text=True)
        assert r.returncode!=0 and 'Engineering union is restricted' in r.stderr and not dest.exists(),r.stderr
    print('{"checks":4,"passed":true,"synthetic_only":true,"heldout_payloads_opened":false}',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
