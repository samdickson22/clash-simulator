"""One home CPU reporting worker using the frozen r1 adapter or K hook."""
import argparse
import json
from pathlib import Path
from imitation.exit_r1 import screen
from imitation.exit_r1.rows import sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--job',required=True);p.add_argument('--stage',type=int,required=True)
    p.add_argument('--arm',required=True);p.add_argument('--index',type=int,required=True)
    a=p.parse_args();j=Path(a.job);screen.execution_guard(str(j/'REPORTING.STOP'))
    assert a.stage in (2,3)
    audit=json.loads((j/'seed-audit.json').read_text());assert audit['passed']
    freeze=json.loads((j/'freeze.json').read_text())
    checkpoints={'init':str(j/'inputs/main02.pt')}
    if a.arm!='init':
        step=freeze['arms'][a.arm]['steps']
        decision=json.loads((j/'offline'/f'{a.arm}.json').read_text());assert decision['survives']
        checkpoints[a.arm]=str(j/'fits'/a.arm/f'step-{step:08d}.pt')
        assert sha(checkpoints[a.arm])==decision['checkpoint_sha256']
    f=dict(native=str(j/'native/clasher_core.abi3.so'),checkpoints=checkpoints)
    mode='h2h' if a.stage==2 else 'fallback'
    base=4503601507370496 if a.stage==2 else 4503601517370496
    assert 0<=a.index<(256 if a.stage==2 else 600)
    if a.stage==3:
        harness=json.loads((j/'stage3-harness.json').read_text())
        if harness['kind']=='K1':
            # K owns the anytime planner; this hook must use the same game loop,
            # public adapter and candidate union for candidate and init reference.
            from k_stage3 import run_case
            run_case(j,a.arm,a.index,base+a.index,checkpoints,harness)
            return
        assert harness['kind']=='frozen-r1-b'
    e1,policies=screen.initialize(f)
    screen.run_case(e1,policies,mode,a.arm,a.index,base+a.index,j/f'stage{a.stage}/cases',
        str(j/'REPORTING.STOP'),freeze_sha256=sha(j/'freeze.json'))

if __name__=='__main__':main()
