"""Outcome-suppressed terminal equivalences and per-cell timing pilots."""
import bootstrap
from bootstrap import HERE
import argparse,hashlib,importlib.util,json,sys,time,resource
from unittest.mock import patch
import torch
import evaluate
from evaluate import Resources,write
from derived_public_state import DerivedPublicState
from cells import CELLS,CHANNELS,configuration
from noise import VARIANTS

def reference():
    originals={name:sys.modules.get(name) for name in ('cells','noise','player')}
    try:
        for name in ('cells','noise','player','evaluate'):
            spec=importlib.util.spec_from_file_location('s1_reference_'+name,HERE/'reference'/f'{name}.py')
            module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
            with patch.object(torch,'set_num_threads'),patch.object(torch,'set_num_interop_threads'):spec.loader.exec_module(module)
            if name!='evaluate':sys.modules[name]=module
        return module
    finally:
        for name,old in originals.items():
            if old is None:sys.modules.pop(name,None)
            else:sys.modules[name]=old

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--equivalence',type=int);ap.add_argument('--pilot',type=int);a=ap.parse_args()
    assert not (HERE/'evaluation-manifest.json').exists()
    index=a.equivalence if a.equivalence is not None else 0
    assert index in (0,1,2)
    r=Resources();prior=json.loads((HERE/'runtime/support/human_deck_catalog.json').read_text());r.initial_belief=DerivedPublicState(prior,r.costs)
    schedule=json.loads((HERE/'schedule.json').read_text())
    ep=dict(schedule['pairs'][index],pair=-1-index,seed=9710800001+1009*index,noise_seed=9810800001+1009*index)
    if a.equivalence is not None:
        baseline=reference();proof=[]
        for alias,channels,old in (('_all',(),'A'),('_none',CHANNELS,'B-N97')):
            CELLS[alias]=configuration(channels);VARIANTS[alias]=set(CELLS[alias]['noise'])
            new=evaluate.game(r,prior,ep,index%2,alias)
            ref=baseline.game(r,prior,ep,index%2,old)
            assert new['terminal'] and ref['terminal']
            for key in ('action_sha256','action_count','ticks'):assert new[key]==ref[key],(index,alias,key)
            proof.append(dict(alias=alias,reference=old,terminal=True,action_sha256=new['action_sha256'],action_count=new['action_count'],ticks=new['ticks'],cpu_seconds=new['cpu_seconds']+ref['cpu_seconds']))
        out=dict(passed=True,seed=ep['seed'],noise_seed=ep['noise_seed'],proof=proof)
        write(HERE/f'equivalence-{index}.json',out)
    else:
        cell=list(CELLS)[a.pilot];row=evaluate.game(r,prior,ep,a.pilot%2,cell)
        assert row['terminal']
        out={k:row[k] for k in ('variant','terminal','ticks','elapsed','cpu_seconds','timing','host','action_sha256')}
        write(HERE/f'pilot-{a.pilot}.json',out)
    print(json.dumps(out),flush=True)
if __name__=='__main__':main()
