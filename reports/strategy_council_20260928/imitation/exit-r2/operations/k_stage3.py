"""X adapter over K's immutable run_game; all inference is inside its timer."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from imitation.exit_r1.rows import sha,write_json
from imitation.exit_r1.screen import load_student

def run_case(job,arm,index,seed,checkpoints,harness):
    j=Path(job);directory=j/'source/reports/explore/k-anytime'
    for relative,expected in harness['source_files'].items():
        assert sha(j/'source'/relative)==expected,'K source changed: '+relative
    os.environ['CLASHER_DELAY_NATIVE_DIR']=str(j/'k-native')
    assert sha(j/'k-native/clasher_core.abi3.so')==harness['native_sha256']
    sys.path[:0]=[str(directory),str(j/'source/reports/explore/e1')]
    spec=importlib.util.spec_from_file_location('exit_r2_k_runner',directory/'run.py')
    k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
    # Reuse K's resources/initial policy initialization, then bind the X pins.
    k.initialize();k.POLICY=load_student(checkpoints['init'])
    assigned=load_student(checkpoints[arm]) if arm!='init' else k.POLICY
    seat=index%2;cores={};original_make=k.make_player
    def make_player(player_seed,unused_arm,*args,**kwargs):
        p=original_make(player_seed,'W',False,1,160)
        actor=seat if player_seed==seed+100000 else 1-seat
        cores[actor]=p.core
        if actor==seat and arm!='init':
            original_candidates=p.core.candidates
            def candidates(packet,*args,**kwargs):
                return original_candidates(packet,list(p.core.refine_proposals))
            p.core.candidates=candidates
        return p
    k.make_player=make_player
    import policy
    original_policy=policy.V1Policy
    from imitation.evaluation.d1 import model_packet
    proposal_latencies=[]
    class XPolicy(original_policy):
        def __init__(self,initial,builder,costs,actor,own_order,policy_seed):
            super().__init__(assigned if actor==seat else initial,builder,costs,actor,own_order,policy_seed)
            self.actor=actor
        def poll(self,tick,packet,public_events):
            fallback=super().poll(tick,packet,public_events)
            if self.actor==seat and arm!='init' and tick%10==0:
                begin=time.monotonic()
                proposals=assigned.propose(model_packet(packet,self.mask),self.player.last_d1,k=2304)
                core=cores[self.actor];core.coarse_order=tuple(p['action'] for p in proposals)
                core.refine_proposals=core.coarse_order[:8]
                proposal_latencies.append(time.monotonic()-begin)
            return fallback
    policy.V1Policy=XPolicy
    raw=j/'stage3/k-raw'/arm
    k.OPTIONS=dict(out=str(raw),max_ticks=6001,return_reserve_seconds=.008,
        arms={arm:dict(own='W-screen8',opponent='baseline',threads=1,coarse_horizon=160,deadline_seconds=.2)})
    try:
        decks=__import__('imitation.exit_r1.emitter',fromlist=['decks'])
        decks.PRIOR=k.PRIOR;selected=decks.decks()[:5]
        r=k.run_game((index,seed,arm,selected[index%5],selected[(index//5)%5]))
    finally:policy.V1Policy=original_policy
    path=raw/'games'/f"{r['game']}.json";record=json.loads(path.read_text());meta=record['metadata']
    assert r['terminal'] and meta['terminal'] and meta['seed']==seed and meta['seat']==seat
    write_json(j/'stage3/cases'/f'fallback-{arm}-{index:04d}.json',dict(mode='fallback',arm=arm,index=index,
        seed=seed,seat=seat,terminal=True,winner=meta['winner'],loss=record['loss'],
        win=float(meta['winner']==seat),draw=meta['winner'] is None,
        cpu_seconds=record['cpu_seconds'],wall_seconds=record['wall_seconds'],
        freeze_sha256=sha(j/'freeze.json'),harness_sha256=sha(j/'stage3-harness.json'),
        raw_game_sha256=sha(path),search_ab=record['search_ab'],proposal_seconds=proposal_latencies,
        opponent='K1 with released v1; one thread horizon160',
        student_hooks='order all coarse plays; add top8 to candidate union and refinement; no eligibility restriction'))
