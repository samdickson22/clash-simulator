"""Bounded immutable scalar DEVELOPMENT branches; no native calls or training."""
from __future__ import annotations
import argparse
import contextlib
import gzip
import io
import json
import multiprocessing
import os
import random
import time
import traceback
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path

import numpy as np
from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_public_observation import NativeProjectileCatalog,public_reference_builder
from clasher.rl.public_action_mask import PublicActionMaskBuilder,PublicActionMaskInput
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.readiness_execution import canonical_sha,file_sha,packet_sha,condition_styles
from clasher.rl.training_readiness_v2 import CONDITIONS,ROLES

BASE=Path(__file__).resolve().parent
SELECTED=BASE/'seed-260928903'
OUTPUT=BASE/'continuations-seed-260928903'
RL_DEPENDENCIES={'__init__.py','action_space.py','public_action_mask.py','public_scripted_opponent.py',
 'public_observation.py','structured_obs.py','card_semantics.py','deck_pool.py','common.py','own_card_history.py',
 'native_public_observation.py','public_policy_contract.py','model.py','joint_action_value.py','structured_memory.py',
 'readiness_execution.py','training_readiness_v2.py','readiness_root_bank.py'}


def write_new(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')


def dependencies():
    package=Path('src/clasher').resolve()
    paths=[p for p in package.rglob('*.py') if p.relative_to(package).parts[0] not in {'rl','torch_sim'}
           or (p.parent==package/'rl' and p.name in RL_DEPENDENCIES)]
    paths.append(Path(__file__).resolve())
    return {str(p):file_sha(p) for p in sorted(paths)}


def check_pins(pins):
    changed=[name for name,digest in pins.items() if file_sha(Path(name))!=digest]
    if changed:raise ValueError('required dependency/input changed: '+repr(changed))


def prepare():
    if OUTPUT.exists():
        plan=json.loads((OUTPUT/'study-plan.json').read_text());check_pins(plan['source_pins']);check_pins(plan['input_pins']);return plan
    design=json.loads((SELECTED/'study-design.json').read_text())
    rows=json.loads((SELECTED/'summary.json').read_text())['results']
    if len(rows)!=32 or any(r['failure'] or r['selection']['status']!='selected' for r in rows):
        raise ValueError('all32 immutable selected development roots required')
    pins=dependencies()
    for path,digest in pins.items():
        if path in design['source_pins'] and design['source_pins'][path]!=digest:
            raise ValueError('selected-root dependency changed before replay: '+path)
    native=CardDataLoader(design['native_data_authority']);workspace=CardDataLoader()
    spell_pins={}
    for name in ('Fireball','Log','Zap'):
        a=native.get_card(name)._raw_entry;b=workspace.get_card(name)._raw_entry
        if a!=b:raise ValueError('global spell source differs for pilot spell '+name)
        spell_pins[name]=canonical_sha(a)
    input_paths=[SELECTED/'study-design.json',SELECTED/'root-bank.json',SELECTED/'summary.json',
                 native.data_file,workspace.data_file,Path(design['catalog_path'])]
    for row in rows:
        folder=SELECTED/row['request']['family_id']
        input_paths.extend(folder/name for name in ('prefix.jsonl.gz','selection-result.json','root-owner-0.npz','root-owner-1.npz'))
    input_pins={str(p.resolve()):file_sha(p) for p in input_paths}
    package=Path('src/clasher').resolve()
    broad={str(p):file_sha(p) for p in package.rglob('*.py')}
    plan={'schema':'scalar-development-continuations-v1','evidence_role':'opened_scalar_development',
          'development_master_seed':260928903,'families':32,'roles':list(ROLES),'conditions':list(CONDITIONS),
          'branches':512,'maximum_workers':2,'decision_interval_ticks':5,'terminal_tick_limit':6001,
          'score_separation_floor':0.,'nonwait_margin_separation_threshold':0.01,'starting_owner_crown_hp':10928,
          'no_replacement':True,'native_calls':0,'training_labels':False,
          'initial_hands':'scalar-only first-four declared deck; native shuffle equivalence unproven',
          'native_gamedata_path':str(native.data_file.resolve()),'workspace_global_spell_gamedata_path':str(workspace.data_file.resolve()),
          'identical_pilot_spell_entry_hashes':spell_pins,'catalog_path':design['catalog_path'],'catalog_sha256':design['catalog_sha256'],
          'source_pins':pins,'input_pins':input_pins,'broad_source_snapshot':broad,'selected_requests':rows}
    OUTPUT.mkdir();write_new(OUTPUT/'study-plan.json',plan)
    return plan


def resources(plan):
    loader=CardDataLoader(plan['native_gamedata_path'])
    catalog=NativeProjectileCatalog.from_csv(Path(plan['catalog_path']),expected_sha256=plan['catalog_sha256'])
    builder=public_reference_builder(loader,catalog,public_contract_version=4)
    return loader,builder,PublicActionMaskBuilder(builder),DiscreteTileActionSpace()


def views_for(battle,builder):
    return [reference_public_observation(builder.build_actor(battle,owner)) for owner in (0,1)]


def deploy_actions(battle,views,actions,builder,mask_builder,space):
    deployed=0
    for owner,action in enumerate(actions):
        mask=mask_builder.build(PublicActionMaskInput.from_confidence_observation(views[owner]))
        if type(action) is not int or not 0<=action<len(mask) or not mask[action]:
            raise ValueError('public-illegal selected command')
        choice=space.decode_action(action,owner)
        if choice.is_no_op:continue
        if choice.is_ability:raise ValueError('ability outside declared scope')
        name=builder.card_name_for_token_id(int(views[owner].observation.hand_ids[choice.slot]))
        if not battle.deploy_card(owner,name,choice.position):raise ValueError('scalar rejected public-legal command')
        deployed+=1
    return deployed


def advance(battle,target):
    while battle.tick<target and not battle.game_over:battle.step()


def replay_root(row,loader,builder,mask_builder,space):
    request=row['request'];folder=SELECTED/request['family_id']
    players=[PlayerState(owner,deck=list(deck),hand=list(deck[:4]),cycle_queue=deque(deck[4:])) for owner,deck in enumerate(request['decks'])]
    battle=BattleState(players=players,rng=random.Random(request['episode_seed']),card_loader=loader)
    count=0
    with gzip.open(folder/'prefix.jsonl.gz','rt') as stream:
        for line in stream:
            prefix=json.loads(line);advance(battle,prefix['tick'])
            if battle.tick!=prefix['tick'] or battle.game_over:raise ValueError('prefix terminated before recorded root')
            views=views_for(battle,builder)
            if [packet_sha(v) for v in views]!=prefix['public_sha256']:raise ValueError('prefix public packet hash differs')
            deploy_actions(battle,views,prefix['actions'],builder,mask_builder,space);count+=1
    advance(battle,row['selection']['root_tick'])
    if battle.game_over:raise ValueError('selected root became terminal')
    views=views_for(battle,builder)
    if packet_sha(views[request['root_owner']])!=row['selection']['public_packet_sha256']:
        raise ValueError('selected root public hash differs')
    for owner in (0,1):
        stored=PublicPolicySequence.load(folder/f'root-owner-{owner}.npz',token_names=builder.token_names)
        rebuilt=PublicPolicySequence.from_observations(builder,[views[owner]])
        for name,array in stored.arrays.items():np.testing.assert_array_equal(array,rebuilt.arrays[name])
    return battle,{'verified_prefix_boundaries':count,'root_tick':battle.tick,'both_root_archives_identical':True,
                  'public_packet_sha256':row['selection']['public_packet_sha256']}


def execute_branch(plan,row,root,builder,mask_builder,space,condition,candidate,folder,claim):
    check_pins(plan['source_pins'])
    battle=root.clone();owner=row['request']['root_owner'];styles=condition_styles(condition,owner)
    controllers=[PublicScriptedOpponent(builder,style=style) for style in styles]
    decisions=commands=0;started=time.monotonic()
    denominator=sum(battle._starting_tower_hps[owner].values())
    if denominator!=10928:raise ValueError('unexpected root owner initial crown HP')
    with gzip.open(folder/'decisions.jsonl.gz','xt') as stream:
        for boundary in range(root.tick,6001,5):
            advance(battle,boundary)
            if battle.game_over:break
            if battle.tick!=boundary:raise ValueError('scalar continuation boundary mismatch')
            views=views_for(battle,builder)
            actions=[int(bot.select_action(view)) for bot,view in zip(controllers,views)]
            if boundary==root.tick:actions[owner]=candidate['action_id']
            stream.write(json.dumps({'tick':boundary,'actions':actions,'public_sha256':[packet_sha(v) for v in views]},separators=(',',':'))+'\n')
            commands+=deploy_actions(battle,views,actions,builder,mask_builder,space);decisions+=1
            advance(battle,min(boundary+5,6001))
    advance(battle,6001)
    if not battle.game_over:raise ValueError('scalar branch did not reach true terminal by6001')
    winner=battle.winner
    if winner not in (None,-1,0,1):raise ValueError('unknown winner')
    hp=[sum(max(0,float(e.hitpoints)) for e in battle.entities.values() if e.player_id==seat and e.entity_kind==1 and e.card_stats.name in ('Tower','KingTower')) for seat in (0,1)]
    check_pins(plan['source_pins'])
    return {'status':'complete','claim':claim,'terminal':True,'terminal_tick':battle.tick,'winner':winner,
            'score':.5 if winner in (None,-1) else float(winner==owner),'own_remaining_hp':hp[owner],
            'enemy_remaining_hp':hp[1-owner],'starting_owner_crown_hp':denominator,
            'normalized_hp_margin':(hp[owner]-hp[1-owner])/denominator,'decision_boundaries':decisions,
            'accepted_scalar_commands':commands,'elapsed_seconds':time.monotonic()-started,
            'decisions_sha256':file_sha(folder/'decisions.jsonl.gz')}


def family_worker(index):
    import torch
    torch.set_num_threads(1)
    plan=json.loads((OUTPUT/'study-plan.json').read_text());row=plan['selected_requests'][index]
    folder=OUTPUT/row['request']['family_id'];folder.mkdir(exist_ok=True)
    loader,builder,mask_builder,space=resources(plan)
    root=None;root_failure=None
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            root,replay=replay_root(row,loader,builder,mask_builder,space)
            if not (folder/'root-replay.json').exists():write_new(folder/'root-replay.json',replay)
        except Exception as exc:root_failure={'type':type(exc).__name__,'message':str(exc)}
        for condition_index,condition in enumerate(CONDITIONS):
            for candidate in row['selection']['candidates']:
                branch=folder/f'condition-{condition_index}-{candidate["role"]}'
                claim={'evidence_role':'opened_scalar_development','study_plan_sha256':file_sha(OUTPUT/'study-plan.json'),
                       'family_id':row['request']['family_id'],'root_owner':row['request']['root_owner'],
                       'root_public_sha256':row['selection']['public_packet_sha256'],'candidate':candidate,
                       'condition':condition,'decision_interval_ticks':5,'engine':'scalar'}
                if branch.exists():
                    if (branch/'result.json').exists():
                        result=json.loads((branch/'result.json').read_text())
                        if result['claim']!=claim:raise ValueError('completed branch claim changed')
                        if result['status']=='complete' and result['decisions_sha256']!=file_sha(branch/'decisions.jsonl.gz'):
                            raise ValueError('completed branch trace changed')
                        continue
                    old_claim=json.loads((branch/'claim.json').read_text())
                    if old_claim!=claim:raise ValueError('unfinished branch claim changed')
                    write_new(branch/'result.json',{'status':'failure','claim':claim,'failure':{'type':'InterruptedClaim','message':'retained; not rerun'}})
                    continue
                branch.mkdir();write_new(branch/'claim.json',claim)
                try:
                    if root_failure:raise ValueError('root replay failed: '+repr(root_failure))
                    result=execute_branch(plan,row,root,builder,mask_builder,space,condition,candidate,branch,claim)
                except Exception as exc:
                    result={'status':'failure','claim':claim,'failure':{'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}}
                write_new(branch/'result.json',result)
    return row['request']['family_id']


def summarize(plan):
    results=[];class_best=Counter();by_card={};complete=informative=0;failures=[]
    for row in plan['selected_requests']:
        family=row['request']['family_id'];branches={};missing=[]
        for index,condition in enumerate(CONDITIONS):
            for role in ROLES:
                path=OUTPUT/family/f'condition-{index}-{role}'/'result.json'
                if not path.exists():missing.append((condition,role));continue
                value=json.loads(path.read_text())
                if value['status']!='complete':failures.append({'family_id':family,'condition':condition,'role':role,'failure':value['failure']});missing.append((condition,role));continue
                branches[condition,role]=value
        result={'family_id':family,'focal_card':row['request']['focal_card'],'context':row['request']['context'],
                'complete':not missing,'missing_or_failed':missing}
        if not missing:
            complete+=1
            means={role:{'score':sum(branches[c,role]['score'] for c in CONDITIONS)/4,
                         'normalized_hp_margin':sum(branches[c,role]['normalized_hp_margin'] for c in CONDITIONS)/4} for role in ROLES}
            nonwait=[role for role in ROLES if role!='wait']
            ds=max(v['score'] for k,v in means.items() if k in nonwait)-min(v['score'] for k,v in means.items() if k in nonwait)
            dm=max(v['normalized_hp_margin'] for k,v in means.items() if k in nonwait)-min(v['normalized_hp_margin'] for k,v in means.items() if k in nonwait)
            qualified=ds>0 or dm>0.01;informative+=int(qualified)
            best=max((v['score'],v['normalized_hp_margin']) for v in means.values())
            best_roles=[role for role,v in means.items() if (v['score'],v['normalized_hp_margin'])==best]
            class_best.update(best_roles)
            result.update(means=means,nonwait_score_separation=ds,nonwait_margin_separation=dm,
                          scalar_nonwait_informative=qualified,scalar_preferred_roles=best_roles)
            bucket=by_card.setdefault(row['request']['focal_card'],{'complete':0,'scalar_nonwait_informative':0});bucket['complete']+=1;bucket['scalar_nonwait_informative']+=int(qualified)
        results.append(result)
    unrelated=[name for name,digest in plan['broad_source_snapshot'].items() if name not in plan['source_pins'] and file_sha(Path(name))!=digest]
    summary={'evidence_role':'opened_scalar_development','expected_branches':512,'complete_families':complete,
             'scalar_nonwait_informative_families':informative,'frozen_margin_threshold':.01,'score_floor':0.,
             'per_focal_card':by_card,'scalar_best_class_exposures_including_ties':dict(class_best),'failures':failures,
             'unrelated_source_drift':unrelated,'families':results,'native_admission':False,'training_labels':False}
    write_new(OUTPUT/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=2);parser.add_argument('--summarize-only',action='store_true');args=parser.parse_args()
    if not 1<=args.workers<=2:parser.error('maximum2CPUworkers')
    plan=prepare()
    if not args.summarize_only:
        started=time.monotonic()
        with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            pending={pool.submit(family_worker,i):i for i in range(32)}
            for future in as_completed(pending):print(f'family {pending[future]} complete: {future.result()} elapsed{time.monotonic()-started:.1f}s',flush=True)
    check_pins(plan['source_pins']);check_pins(plan['input_pins'])
    summary=summarize(plan)
    print(json.dumps({k:v for k,v in summary.items() if k!='families'},indent=2),flush=True)


if __name__=='__main__':main()
