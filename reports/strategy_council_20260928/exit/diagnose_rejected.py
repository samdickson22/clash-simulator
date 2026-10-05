"""Read-only replay diagnostics; the planner still receives only public inputs."""
from common import *
from evaluate import search_game

def main():
    verify()
    path=folder(1)/'search/h2h-student-hog26-search-026.json'
    original=json.loads(path.read_text())
    contexts={'initial':Context(CHECKPOINT),'student':Context(folder(1)/'student.pt')}
    resources={name:Resources(ctx) for name,ctx in contexts.items()}
    env=contexts['student'].envs('hog26',original['matchup_seed'])[0]
    original_step=env.step;failures=[];applications=[]
    original_apply=env.action_space.apply_action
    def apply(battle,seat,action):
        if battle.tick==3280:
            from clasher.battle import building_anchor
            decoded=env.action_space.decode_action(action,seat)
            name=battle.players[seat].hand[decoded.slot]
            _,stats,_=battle.resolve_card_play(seat,name)
            position=building_anchor(decoded.position,battle._building_footprint_size_tiles(stats))
            applications.append(dict(seat=seat,action=action,card=name,
                position=[position.x,position.y],
                engine_legal=bool(env.action_space.legal_action_mask(battle,seat)[action]),
                building_occupied=battle.is_building_placement_occupied(position,stats),
                payload_occupied=battle.is_deployment_payload_occupied(position,card_stats=stats)))
        return original_apply(battle,seat,action)
    env.action_space.apply_action=apply
    def step(actions,**kwargs):
        before=dict(tick=env.battle.tick,game_over=env.battle.game_over,
            actions=actions,public_legal={s:bool(kwargs['pre_action_masks'][s][a]) for s,a in actions.items()},
            own=[dict(hand=list(p.hand),elixir=p.elixir,refill=p.next_card_refill_cooldown_ms) for p in env.battle.players])
        if env.battle.tick==3280:
            before['engine_legal_before']={s:bool(env.action_space.legal_action_mask(env.battle,s)[a]) for s,a in actions.items()}
        result=original_step(actions,**kwargs)
        info=result[2]
        if any(a!=resources['student'].no_op and not info.action_success[s] for s,a in actions.items()):
            rec=dict(before=before,after_tick=env.battle.tick,game_over=env.battle.game_over,
                action_success=info.action_success,winner=env.battle.winner)
            failures.append(rec);log(rec)
        return result
    env.step=step
    replay=search_game(contexts,resources,original['spec'])
    for key in ('world_decks','score','ticks','decisions','planner_calls','failed_plays'):
        assert json.loads(json.dumps(replay[key]))==original[key],key
    write_json(folder(1)/'rejected-play-diagnosis.json',dict(original=original,replay=replay,failures=failures,applications=applications,
        note='Private own-player records for both seats are read by the diagnostic wrapper only, after each planner has chosen. No data is passed into the planners; game state and RNG are never changed.'))
if __name__=='__main__':main()
