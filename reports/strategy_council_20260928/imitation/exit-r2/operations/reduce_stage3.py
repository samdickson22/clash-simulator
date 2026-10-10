"""Require 600 genuine student/reference pairs before the stage3 verdict."""
import argparse
import json
from pathlib import Path
from imitation.exit_r1.rows import sha,write_json
from imitation.exit_r1.screen_metrics import paired_interval

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    a=p.parse_args();j=Path(a.job);losses={}
    for arm in (a.arm,'init'):
        values=[]
        for i in range(600):
            f=j/'stage3/cases'/f'fallback-{arm}-{i:04d}.json';r=json.loads(f.read_text())
            assert (r['mode'],r['arm'],r['index'],r['seed'],r['seat'],r['terminal'],r['freeze_sha256'])==(
                'fallback',arm,i,4503601517370496+i,i%2,True,sha(j/'freeze.json'))
            assert r['harness_sha256']==sha(j/'stage3-harness.json')
            values.append(r['loss'])
        losses[arm]=values
    interval=paired_interval(losses[a.arm],losses['init']);survives=interval['ci95'][1]<0
    write_json(j/'stage3'/f'{a.arm}.json',dict(arm=a.arm,stage=3,paired=interval,survives=survives,
        kill_reasons=[] if survives else ['paired loss-change upper CI >=0'],
        lane='exploration; no multiplicity adjustment',harness_sha256=sha(j/'stage3-harness.json')))

if __name__=='__main__':main()
