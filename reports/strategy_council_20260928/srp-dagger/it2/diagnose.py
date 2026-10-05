"""Pilot provenance, recurrent probabilities, and live action/tick checks."""
import sys,json
from pathlib import Path
from collections import Counter,defaultdict
from dataclasses import fields
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit
from kit import np,torch
from clasher.rl.structured_obs import ActorObservation
from clasher.rl.public_observation import ConfidenceAwareActorObservation
from clasher.rl.imitation import _imitation_evaluation_batches
from clasher.rl.common import NUM_TILES,BOARD_WIDTH
from clasher.rl.action_space import DiscreteTileActionSpace
OUT=Path(__file__).resolve().parent

def packet(a,row):
    kw={f.name:a[f.name][row] for f in fields(ActorObservation) if f.name in a}
    kw.update(terminal=bool(a['terminal_status'][row]),board_rotated=bool(a['board_rotated'][row]))
    obs=ActorObservation(**kw)
    return ConfidenceAwareActorObservation(obs,**{k:a[k][row] for k in ('entity_id_confidence','entity_feature_confidence','hand_id_confidence','global_feature_confidence')},opponent_history_confidence=np.ones_like(obs.opponent_history_ages),opponent_seen_card_confidence=np.ones_like(obs.opponent_seen_card_ids,dtype=np.float32))

@torch.no_grad()
def main():
    torch.set_num_threads(1)
    loaded=kit.ev.load_policy_checkpoint(kit.INITIAL,device=kit.DEVICE,decks_path=kit.TRAINING)
    bot=kit.PublicScriptedOpponent(loaded.builder,style='balanced')
    counts=Counter(); random_tiles=0; space=DiscreteTileActionSpace(); samples=[]
    for path in sorted((kit.HERE/'games').glob('game-*.npz')):
        meta,a=kit.load_corpus(path)
        with np.load(path) as data:
            ids,rows=data['root_candidate_ids'],data['root_candidate_rows']
            ticks=data['submitted_ticks']
            assert np.allclose(a['global_features'][:-1,0],ticks/6000,atol=1e-7)
            assert np.array_equal(a['previous_actions'][1:],data['submitted_actions'])
            for row in np.flatnonzero(a['expert_action_supervision_valid']):
                p=packet(a,row); ranked=bot._ranked_actions(p,all_plays=True)
                script=[int(bot.decide(p).action_id)]+[int(x.action_id) for x in ranked[:4]]
                label=int(a['expert_actions'][row]); candidates=ids[rows==row]
                assert label in candidates
                kind='no-op' if label==space.no_op_action else 'script' if label in script else 'random'
                counts[kind]+=1
                if kind=='random': random_tiles+=1
                if label<space.no_op_action:
                    seat=int(json.loads(meta.provenance)['seat']); sel=space.decode_action(label,seat)
                    assert space.encode_action(sel.slot,int(sel.position.x),int(sel.position.y),seat)==label
                    if len(samples)<8 or (seat==1 and not any(x['seat']==1 for x in samples)):
                        samples.append(dict(game=path.stem,row=int(row),tick=int(ticks[row]),seat=seat,label=label,slot=sel.slot,card=meta.token_names[a['hand_ids'][row,sel.slot]],world_xy=[sel.position.x,sel.position.y],source=kind))
        kit.log(dict(event='provenance',game=path.stem,counts=dict(counts)))
    result=dict(provenance=dict(counts),roundtrip_examples=samples,tick_alignment='All 40 games: global progress equals submitted tick / 6000; previous actions match executed actions; all play labels round-trip for both seats.')
    kit.write_json(OUT/'diagnostics.json',result)
    _,a=kit.load_corpus(kit.HERE/'aggregate.npz'); rows=np.flatnonzero(a['expert_action_supervision_valid'])
    heldout=set(json.loads((kit.HERE/'split.json').read_text())['heldout_games'])
    for name,checkpoint in [('initial',kit.INITIAL),('it1',kit.FINAL)]:
        model=kit.ev.load_policy_checkpoint(checkpoint,device=kit.DEVICE,decks_path=kit.TRAINING).model
        vals=defaultdict(lambda:defaultdict(list))
        for selected,_,out in _imitation_evaluation_batches(model,a,rows,batch_size=128,device=kit.DEVICE,trim_entity_padding=True):
            logits=out.joint_logits[:,0]; probs=logits.softmax(-1).numpy(); targets=a['expert_actions'][selected]
            for j,row in enumerate(selected):
                if targets[j]>=2304:continue
                p=probs[j]; target=int(targets[j]); pred=int(p.argmax()); bestplay=int(p[:2304].argmax()); slot=target//NUM_TILES
                tile=target%NUM_TILES; besttile=bestplay%NUM_TILES
                conditional_tile=int(p[slot*NUM_TILES:(slot+1)*NUM_TILES].argmax())
                marginal=p[:2304].reshape(4,NUM_TILES).sum(-1)
                m=dict(teacher_probability=float(p[target]),teacher_nll=float(-np.log(max(p[target],1e-38))),wait_probability=float(p[2304]),argmax_play=float(pred<2304),argmax_slot_agreement=float(pred<2304 and pred//NUM_TILES==slot),conditional_play_slot_agreement=float(marginal.argmax()==slot),teacher_slot_probability=float(marginal[slot]),best_play_tile_distance=float(np.hypot(tile%BOARD_WIDTH-besttile%BOARD_WIDTH,tile//BOARD_WIDTH-besttile//BOARD_WIDTH)),teacher_slot_tile_distance=float(np.hypot(tile%BOARD_WIDTH-conditional_tile%BOARD_WIDTH,tile//BOARD_WIDTH-conditional_tile//BOARD_WIDTH)))
                for split in ('all','heldout' if int(a['episode_ids'][row]) in heldout else 'train'):
                    for key,value in m.items():vals[split][key].append(value)
        result[name]={split:{k:dict(mean=float(np.mean(v)),median=float(np.median(v)),n=len(v)) for k,v in metrics.items()} for split,metrics in vals.items()}
        kit.write_json(OUT/'diagnostics.json',result);kit.log(dict(event='probabilities',model=name,metrics=result[name]))
    # Live replays establish that stored packets, hands, ticks and chosen labels share a boundary.
    live=[]
    for game in (0,1):
        path=kit.HERE/'games'/f'game-{game:03d}.npz';meta,a=kit.load_corpus(path); prov=json.loads(meta.provenance)
        env=kit.setup(loaded,kit.HOG,meta.seed,game%2); opponent=kit.PublicScriptedOpponent(loaded.builder,style=prov['opponent_style'])
        planner=kit.RecordedPlanner(env,bot,seed=meta.seed*2+game%2+7919,opponent_model=kit.StrategyBot('balanced'),backend='native')
        checked=0
        with np.load(path) as data:
            for row,action in enumerate(data['submitted_actions']):
                packets=[kit.project(loaded.builder.build_actor(env.battle,s)) for s in (0,1)]
                assert env.battle.tick==data['submitted_ticks'][row]
                assert np.array_equal(packets[game%2].observation.hand_ids,a['hand_ids'][row])
                assert np.array_equal(packets[game%2].observation.global_features,a['global_features'][row])
                masks={s:bot.mask_builder.build(kit.PublicActionMaskInput.from_confidence_observation(packets[s])) for s in (0,1)}
                if a['expert_action_supervision_valid'][row]:
                    legal=np.flatnonzero(masks[game%2]&env.action_space.legal_action_mask(env.battle,game%2))
                    teacher=planner.select_action(env.battle,game%2,legal)
                    assert teacher==a['expert_actions'][row]
                    chosen=env.action_space.decode_action(teacher,game%2)
                    if not chosen.is_no_op:
                        assert env.battle.players[game%2].hand[chosen.slot]==meta.token_names[a['hand_ids'][row,chosen.slot]]
                        checked+=1
                        live.append(dict(game=game,row=row,tick=env.battle.tick,action=teacher,card=env.battle.players[game%2].hand[chosen.slot],world_xy=[chosen.position.x,chosen.position.y]))
                    if checked==4:break
                with kit.maybe_silence_stdio(True):env.step({game%2:int(action),1-game%2:int(opponent.select_action(packets[1-game%2]))},pre_action_masks=masks)
    result['live_replay']=live;kit.write_json(OUT/'diagnostics.json',result)

if __name__=='__main__':main()
