"""Read-only rejected-command replay after both public planners choose."""
from experiment import *

path=HERE/'games/1/tower-hog26-search-006-candidate.json'
original=json.loads(path.read_text())
verify();ctx=Context();r=Resources(ctx)
env=ctx.envs(original['spec']['role'],original['matchup_seed'])[original['seat']]
step=env.step;apply=env.action_space.apply_action;failures=[];applications=[]


def traced_apply(battle,seat,action):
    if action==r.no_op:return apply(battle,seat,action)
    decoded=env.action_space.decode_action(action,seat)
    name=battle.players[seat].hand[decoded.slot]
    before=dict(tick=battle.tick,seat=seat,action=action,card=name,
                engine_legal=bool(env.action_space.legal_action_mask(battle,seat)[action]))
    result=apply(battle,seat,action)
    applications.append(dict(**before,accepted=bool(result)))
    return result


def traced_step(actions,**kwargs):
    before=dict(tick=env.battle.tick,actions=actions,
                public_legal={s:bool(kwargs['pre_action_masks'][s][a]) for s,a in actions.items()},
                engine_legal={s:bool(env.action_space.legal_action_mask(env.battle,s)[a]) for s,a in actions.items()})
    start=len(applications);result=step(actions,**kwargs)
    if any(a!=r.no_op and not result[2].action_success[s] for s,a in actions.items()):
        failures.append(dict(**before,applications=applications[start:],action_success=result[2].action_success))
    return result


env.action_space.apply_action=traced_apply;env.step=traced_step
replayed=play(ctx,r,Config(**original['config']),original['spec'])
for k in ('world_decks','outcome','score','ticks','failed','matchup_seed','seat'):
    assert json.loads(json.dumps(replayed[k]))==original[k],k
write(HERE/'rejected-play-diagnosis.json',dict(exact_replay=True,original=str(path.relative_to(HERE)),failures=failures,
      note='Diagnostic reads occur after both planners choose; no private state is passed into a planner, and no state/RNG is changed.'))
print(json.dumps(failures),flush=True)
progress('Rejected-command game replay reproduced exact decks, outcome, ticks and failure counts. See rejected-play-diagnosis.json.')
