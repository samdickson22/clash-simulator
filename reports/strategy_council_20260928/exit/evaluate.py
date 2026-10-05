"""Standard six-cell policy evaluation and paired public-search comparisons."""
import argparse
import importlib.util
import time
from common import *
from clasher.rl.public_action_mask import PublicActionMaskInput


def policy(iteration, which):
    verify()
    spec = importlib.util.spec_from_file_location('shared_run_eval',COUNCIL/'human-prior-p16/scripts/run_eval.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.RUNTIME = ROOT; module.OUT = HERE
    checkpoint = CHECKPOINT if which == 'initial' else folder(iteration)/'student.pt'
    sys.argv = ['run_eval.py','--checkpoint',str(checkpoint),'--name',f'exit-it{iteration}-{which}',
        '--parallel',str(config().workers),'--games','32','--trace-games','0',
        '--seed',str(config().evaluation_seed+iteration*100000000)]
    module.main(); verify()


def search_specs(iteration):
    base = config().evaluation_seed+iteration*100000000
    for r,role in enumerate(('holdout','hog26')):
        for s,style in enumerate(STYLES):
            for g in range((12,10,10)[s]):
                for which in ('initial','student'):
                    yield dict(role=role,style=style,game=g,seed=base+30000000+r*1000000+s*100000,which=which,mode='scripts')
        for g in range(32):
            yield dict(role=role,style='search',game=g,seed=base+50000000+r*1000000,which='student',mode='h2h')


def identifier(spec):
    return f"{spec['mode']}-{spec['which']}-{spec['role']}-{spec['style']}-{spec['game']:03d}"

@torch.no_grad()
def search_game(contexts, resources, spec):
    which=spec['which'];ctx=contexts[which];r=resources[which]
    seed=spec['seed']+(spec['game']//2)*1009;seat=spec['game']%2;h2h=spec['mode']=='h2h'
    env,decks=reset(ctx,spec['role'],seed,seat,symmetric=h2h)
    train_prior=json.loads(TRAIN_DECKS.read_text())
    if h2h:
        prior=dict(decks=sum([json.loads(p.read_text())['decks'] for p in (TRAIN_DECKS,DEV_DECKS,HOG_DECKS)],[]))
    else:prior=train_prior
    planner=PublicPlanner(r,prior,k=1,seed=seed*2+seat+7919,policy=True)
    other=PublicPlanner(resources['initial'],prior,k=1,seed=seed*2+1-seat+7919,policy=True) if h2h else None
    started=time.perf_counter();maximum=0.;failed=0
    for decision in range(1300):
        t=time.perf_counter();action,mask=planner.decide(observe(env,seat),decision)
        maximum=max(maximum,time.perf_counter()-t)
        if h2h:oa,om=other.decide(observe(env,1-seat),decision)
        else:
            packet=observe(env,1-seat).packet
            om=r.mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
            oa=int(ctx.bot(spec['style']).select_action(packet))
        assert mask[action] and om[oa]
        with maybe_silence_stdio(True):_,done,step=env.step({seat:action,1-seat:oa},pre_action_masks={seat:mask,1-seat:om})
        failed+=int(action!=r.no_op and not step.action_success[seat])
        if done:break
    else:raise RuntimeError('incomplete search evaluation')
    assert env.battle.game_over
    outcome='draw' if env.battle.winner is None else 'win' if env.battle.winner==seat else 'loss'
    return dict(spec=spec,matchup_seed=seed,seat=seat,world_decks=decks,outcome=outcome,
        score={'win':1.,'draw':.5,'loss':0.}[outcome],ticks=env.battle.tick,decisions=decision+1,
        planner_calls=planner.calls,failed_plays=failed,decision_wall_max=maximum,
        wall_s=time.perf_counter()-started,manifest_sha256=sha(HERE/'manifest.json'))

def search(iteration,worker):
    verify();contexts={name:Context(checkpoint) for name,checkpoint in [('initial',CHECKPOINT),('student',folder(iteration)/'student.pt')]}
    resources={name:Resources(ctx) for name,ctx in contexts.items()}
    for spec in list(search_specs(iteration))[worker::config().workers]:
        path=folder(iteration)/'search'/f'{identifier(spec)}.json'
        if path.exists():continue
        verify();rec=search_game(contexts,resources,spec)
        rec['checkpoint_sha256']={name:sha(CHECKPOINT if name=='initial' else folder(iteration)/'student.pt') for name in contexts}
        write_json(path,rec);log(dict(id=identifier(spec),outcome=rec['outcome'],wall_s=rec['wall_s']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,required=True);p.add_argument('--kind',choices=['policy','search'],required=True)
    p.add_argument('--which',choices=['initial','student']);p.add_argument('--worker',type=int,default=0);a=p.parse_args()
    if a.kind=='policy':policy(a.iteration,a.which)
    else:search(a.iteration,a.worker)
