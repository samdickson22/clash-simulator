"""Compare v5/v6 default paths against the existing workspace-era references."""
import json
import os
import runpy
import sys
import tempfile
from pathlib import Path
import numpy as np
import torch
import clasher.rl.imitation as imitation


def mismatches(a, b, path=''):
    if isinstance(b, torch.Tensor):
        return [] if torch.equal(a,b) else [path]
    if isinstance(b, np.ndarray):
        return [] if np.array_equal(a,b) else [path]
    if isinstance(b, dict):
        if a.keys() != b.keys(): return [path + ': keys']
        return [d for k in b for d in mismatches(a[k], b[k], f'{path}/{k}')]
    if isinstance(b, (tuple,list)):
        return [d for i,(x,y) in enumerate(zip(a,b)) for d in mismatches(x,y,f'{path}/{i}')]
    return [] if a == b else [path]


def main():
    root=Path('/Users/sam/Desktop/code/clasher')
    os.chdir(root)
    kit=Path(__file__).resolve().parent
    ref=root/'reports/strategy_council_20260928/learner-tbptt'
    ns=runpy.run_path(str(ref/'reference.py'))
    report={}
    for name,filename in [('ppo','default-reference.pt'),('bc','bc-default-reference.pt')]:
        with tempfile.TemporaryDirectory() as tmp:
            actual=ns['tiny_update']() if name=='ppo' else ns['tiny_bc'](imitation,Path(tmp))
        original=torch.load(ref/'results'/filename,weights_only=False)
        report[name+'_vs_workspace_reference']=mismatches(actual, original)
        dest=kit/'logs'/f'default-{sys.argv[1]}-{name}.pt'
        torch.save(actual,dest)
        if sys.argv[1]=='v6':
            baseline=torch.load(kit/'logs'/f'default-v5-{name}.pt',weights_only=False)
            report[name+'_vs_v5']=mismatches(actual,baseline)
    (kit/'logs'/f'default-{sys.argv[1]}-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
