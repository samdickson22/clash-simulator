"""Require 600 genuine student/reference pairs before the stage3 verdict."""
import argparse
import json
from pathlib import Path
from imitation.exit_r1.rows import sha,write_json
from imitation.exit_r1.screen_metrics import paired_interval

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--arm',required=True)
    a=p.parse_args();j=Path(a.job);losses={};pairs={}
    assert json.loads((j/'stage3-harness.json').read_text())['kind']=='K1-vs-v1'
    for arm in (a.arm,'init'):
        values=[];pair_keys=[]
        for i in range(600):
            f=j/'stage3/cases'/f'fallback-{arm}-{i:04d}.json';r=json.loads(f.read_text())
            assert (r['mode'],r['arm'],r['index'],r['seed'],r['seat'],r['terminal'],r['freeze_sha256'])==(
                'fallback',arm,i,4503601517370496+i,i%2,True,sha(j/'freeze.json'))
            assert r['harness_sha256']==sha(j/'stage3-harness.json')
            assert r['opponent']=='v1-policy' and r['own_fallback']=='released v1'
            assert r['adapter_sha256']==sha(j/'ops/k_stage3_v2.py')
            pair_keys.append((r['seed'],r['seat'],r['own_deck'],r['opponent_deck']))
            values.append(r['loss'])
        losses[arm]=values;pairs[arm]=pair_keys
    assert pairs[a.arm]==pairs['init'], 'Arm/control seed, seat or decks differ'
    interval=paired_interval(losses[a.arm],losses['init']);survives=interval['ci95'][1]<0
    write_json(j/'stage3'/f'{a.arm}.json',dict(arm=a.arm,stage=3,paired=interval,survives=survives,opponent='v1-policy',
        comparison='student-hooked K1 minus empty-hook K1, both versus v1',
        kill_reasons=[] if survives else ['paired loss-change upper CI >=0'],
        lane='exploration; no multiplicity adjustment',harness_sha256=sha(j/'stage3-harness.json')))

if __name__=='__main__':main()
