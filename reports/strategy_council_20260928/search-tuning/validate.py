"""Baseline equivalence, public-input isolation and native loop checks."""
from experiment import *
import importlib.util


def main():
    spec=importlib.util.spec_from_file_location('original_public_planner',HERE.parent/'srp-public/public_planner.py')
    original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
    ctx=Context();r=Resources(ctx)
    roots=pickle.loads((HERE/'roots.pkl').read_bytes())
    comparisons=0;leaf_checks=0
    for j,(info,_,_) in enumerate(roots[::3]):
        a=original.PublicPlanner(r,prior(),k=1,seed=999+j,policy=True)
        b=Planner(r,prior(),CURRENT,seed=999+j)
        aa,am=a.decide(info,0);ba,bm=b.decide(info,0)
        assert aa==ba and np.array_equal(am,bm) and a.last==b.last
        comparisons+=1
        b.belief.update(info.tick,info.history)
        root,_=r.root(info,b.belief.sample(b.rng),b.rng)
        for style in ('sb-balanced','balanced','pressure','defense'):
            action=r.native.select_action(root,info.seat,'balanced')
            other=r.native.select_action(root,1-info.seat,style)
            c=Planner(r,prior(),Config('loop-check',tower_weight=1e-30),seed=j)
            expected=r.native.rollout(root,info.seat,action,other,'balanced',style,160,10,1.)[0]
            actual=c.score(root,info.seat,action,other,style)
            assert abs(expected-actual)<1e-12,(expected,actual)
            leaf_checks+=1
    # The planner accepts only a public Information object; no environment or
    # true opponent fields are available to either score path.
    assert not hasattr(r,'env') and not hasattr(r,'battle')
    # Terminal draws override asymmetric tower HP just like wins/losses.
    payload=json.loads(root.snapshot())
    payload.update(game_over=True,winner=None)
    tower=next(e for e in payload['entities'] if e['stats']['name']=='Tower')
    tower['hp']*=.3
    terminal=r.native_class(json.dumps(payload))
    leaf=Planner(r,prior(),Config('terminal-check',tower_weight=.5,terminal=4.))
    assert leaf.score(terminal,info.seat,r.no_op,r.no_op,'sb-balanced')==0.
    for winner in (0,1):
        payload['winner']=winner
        terminal=r.native_class(json.dumps(payload))
        assert leaf.score(terminal,info.seat,r.no_op,r.no_op,'sb-balanced')==(4. if winner==info.seat else -4.)
    import tomllib
    cfg=tomllib.loads((HERE/'config.toml').read_text())
    assert cfg==dict(workers=3,stage_games=[48,96,192],confirmation_games=256,
                     holdout_script_games_each=128,hog_script_games_each=64,max_wall_seconds=.25)
    assert len(stage_specs(1,48))==48 and sum(s['role']=='hog26' for s in stage_specs(1,48))==16
    assert len(confirmation_specs())==640
    # Descriptive lower cost estimate only: full policy continuations also need
    # model-state-to-public-packet projection at every imagined decision.
    info=roots[0][0];p=Planner(r,prior());mask=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(info.packet))
    samples=[]
    for _ in range(64):
        t=time.perf_counter();p.policy_top(info,mask);samples.append(time.perf_counter()-t)
    write(HERE/'policy-continuation-cost.json',dict(inference_min=min(samples),inference_median=float(np.median(samples)),
          continuation_calls_13_candidates_h160_i20=91,
          inference_only_estimate_seconds_13_candidates_h160_i20=91*float(np.median(samples)),
          status='not admitted: no validated native endpoint to policy packet adapter; inference-only estimate is not a full latency qualification'))
    write(HERE/'validation.json',dict(baseline_comparisons=comparisons,
          native_leaf_loop_comparisons=leaf_checks,terminal_regressions=3,passed=True))
    progress(f'Validation passed: {comparisons} original-player comparisons; {leaf_checks} native-loop leaf comparisons.')


if __name__=='__main__':main()
