"""S-default K1 arm/control plus descriptive K0, all versus released v1."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from imitation.exit_r1.rows import sha,write_json
from imitation.exit_r1.screen import load_student
from sdefault import student_choice,select_default,poll_before_search
from postkill_admission import labelled

def run_case(job,arm,index,seed,checkpoints,harness,*,smoke=False):
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
    student_arm=arm not in ('C-v1','K0')
    assigned=load_student(checkpoints[arm]) if student_arm else None
    default_source='student_argmax' if student_arm else ('v1_polled' if arm=='C-v1' else 'K0_frozen')
    defaults={}
    seat=index%2;cores={};original_make=k.make_player
    def make_player(player_seed,unused_arm,*args,**kwargs):
        p=original_make(player_seed,'0' if arm=='K0' else 'W',False,1,160)
        assert player_seed==seed+100000, 'Only the own K1 search player is permitted'
        cores[seat]=p.core
        if arm!='K0':
            original_score=p.core.score_candidates
            def score_candidates(root,actor,candidates,*,trace=False,deadline=None,fallback=2304):
                action=original_score(root,actor,candidates,trace=trace,deadline=deadline,fallback=fallback)
                return select_default(p.core,action,defaults.get(actor,fallback),default_source,deadline)
            p.core.score_candidates=score_candidates
        if student_arm:
            original_candidates=p.core.candidates
            def candidates(packet,*args,**kwargs):
                return original_candidates(packet,list(p.core.refine_proposals))
            p.core.candidates=candidates
        return p
    k.make_player=make_player
    # Label the original K writer before it emits any raw game, including failures.
    import clasher.analysis.loss_review.human as human
    original_write=human.write
    def labelled_write(path,record):
        labelled(record);meta=labelled(record.setdefault('metadata',{}))
        record.update(threads=1,coarse_horizon=160,default_source=default_source)
        meta.update(threads=1,coarse_horizon=160,default_source=default_source,return_reserve_seconds=.008,scheduler='SCHED_OTHER',nice=os.getpriority(os.PRIO_PROCESS,0),smoke=smoke)
        original_write(path,record)
    human.write=labelled_write
    def labelled_print(value,*args,**kwargs):
        try: value=json.dumps(labelled(json.loads(value)))
        except (ValueError,TypeError):value='EXPLORATION; NEVER ADOPTABLE '+str(value)
        print(value,*args,**kwargs)
    k.print=labelled_print
    import policy
    original_policy=policy.V1Policy
    from imitation.evaluation.d1 import D1Tracker
    from clasher.rl.public_action_mask import PublicActionMaskInput
    proposal_latencies=[]
    class XPolicy(original_policy):
        def __init__(self,initial,builder,costs,actor,own_order,policy_seed):
            super().__init__(initial,builder,costs,actor,own_order,policy_seed)
            self.actor=actor
            if student_arm and actor==seat:
                self.student_tracker=D1Tracker(builder,costs,actor,own_order)
        def poll(self,tick,packet,public_events):
            if self.actor==seat:
                return poll_before_search(self,tick,packet,public_events,
                    assigned if student_arm else None,cores[self.actor],defaults,
                    super().poll,proposal_latencies,time.monotonic)
            return super().poll(tick,packet,public_events)
    policy.V1Policy=XPolicy
    stage=j/('postkill-sdefault-smoke' if smoke else 'postkill-sdefault')
    raw=stage/'k-raw'/arm
    k.OPTIONS=dict(out=str(raw),max_ticks=6001,return_reserve_seconds=.008,
        arms={arm:dict(own='baseline' if arm=='K0' else 'W-screen8',opponent='v1-policy',threads=1,coarse_horizon=160,deadline_seconds=.2)})
    try:
        decks=__import__('imitation.exit_r1.emitter',fromlist=['decks'])
        decks.PRIOR=k.PRIOR;selected=decks.decks()[:5]
        r=k.run_game((index,seed,arm,selected[index%5],selected[(index//5)%5]))
    finally:
        policy.V1Policy=original_policy;human.write=original_write
    path=raw/'games'/f"{r['game']}.json";record=json.loads(path.read_text());meta=record['metadata']
    assert r['terminal'] and meta['terminal'] and meta['seed']==seed and meta['seat']==seat
    assert meta['opponent']=='v1-policy'
    assert set(cores)=={seat}, 'Opponent must have no search core'
    record.update(threads=1,coarse_horizon=160,default_source=default_source)
    meta.update(threads=1,coarse_horizon=160,default_source=default_source,return_reserve_seconds=.008,
        scheduler='SCHED_OTHER',nice=os.getpriority(os.PRIO_PROCESS,0),smoke=smoke)
    record['search_ab']['default_source']=default_source
    for stats in record['search_ab']['deadline_stats']:
        stats.setdefault('default_source',default_source)
        stats.setdefault('default_used',bool(stats['hit'] and stats['fallback']))
    write_json(path,labelled(record))
    write_json(stage/'cases'/f'sdefault-{arm}-{index:04d}.json',labelled(dict(mode='sdefault',arm=arm,index=index,
        seed=seed,seat=seat,terminal=True,winner=meta['winner'],loss=record['loss'],
        win=float(meta['winner']==seat),draw=meta['winner'] is None,
        cpu_seconds=record['cpu_seconds'],wall_seconds=record['wall_seconds'],
        freeze_sha256=sha(j/'freeze.json'),harness_sha256=sha(j/'postkill-sdefault-addendum.json'),
        raw_game_sha256=sha(path),search_ab=record['search_ab'],proposal_seconds=proposal_latencies,
        opponent='v1-policy', own_v1_poll='released v1', own_fallback=default_source,
        own_deck=meta['own_deck'],opponent_deck=meta['opponent_deck'],
        adapter_sha256=sha(Path(__file__)),
        threads=1,coarse_horizon=160,default_source=default_source,smoke=smoke,
        native_sha256=harness['native_sha256'],scheduler='SCHED_OTHER',nice=os.getpriority(os.PRIO_PROCESS,0),
        student_checkpoint_sha256=sha(checkpoints[arm]) if student_arm else None,
        condition=arm+' S-default design versus v1',
        student_hooks='order all coarse plays; add top8 to candidate union and refinement; no eligibility restriction')))
