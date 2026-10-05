"""Report-only scalar development feasibility; no native calls or continuation outcomes."""
from __future__ import annotations
import contextlib
import gzip
import io
import json
import random
import time
from collections import Counter,deque
from pathlib import Path

from clasher.battle import BattleState
from clasher.data import CardDataLoader
from clasher.player import PlayerState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_public_observation import NativeProjectileCatalog,public_reference_builder
from clasher.rl.public_action_mask import PublicActionMaskBuilder,PublicActionMaskInput
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
from clasher.rl.readiness_execution import canonical_sha,file_sha,packet_sha
from clasher.rl.readiness_native_config import config_for_request,load_verified_template
from clasher.rl.readiness_root_bank import RootBank,context_matches,generate_root_bank,select_root,apply_prefix_owner_reserve
from clasher.rl.training_readiness_v2 import generate_candidates

ROOT=Path(__file__).resolve().parent
SEED=260928903
OWNER_PREFIX_ELIXIR_RESERVE=8.0
CAPTURE=Path('artifacts/worktree-data/clasher-simulator-fidelity-20260913/reports/calibration_development_20260915/expanded-deck-development/forward-0').resolve()
PROSPECTIVE=Path('reports/strategy_council_20260928/m0/root-bank/native-configs/root-bank.json').resolve()
RUN_PLAN=Path('reports/strategy_council_20260928/m0/readiness/paired-repetition-run-v6/execution-plan.json')


def write(path,value):
    with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')


class CachedRootController(PublicScriptedOpponent):
    def ranked_plays(self,packet):
        if getattr(self,'_packet',None) is not packet:
            self._plays=super().ranked_plays(packet)
            self._packet=packet
        return self._plays


def main():
    output=ROOT/f'seed-{SEED}'
    output.mkdir(exist_ok=False)
    bank=generate_root_bank(SEED)
    prospective=RootBank.model_validate_json(PROSPECTIVE.read_text())
    for key in ('source_episode_id','family_id','episode_seed','episode_design_sha256'):
        assert not {getattr(r,key) for r in bank.requests}&{getattr(r,key) for r in prospective.requests},key
    loader=CardDataLoader(CAPTURE/'gamedata.json')
    assert file_sha(loader.data_file)=='daa58b28cf4e45d753e83ca69a76794285b63704e62363ee58e617af3a30ecc3'
    prior=json.loads(RUN_PLAN.read_text())
    catalog=NativeProjectileCatalog.from_csv(Path(prior['catalog_path']),expected_sha256=prior['catalog_sha256'])
    builder=public_reference_builder(loader,catalog,public_contract_version=4)
    space=DiscreteTileActionSpace();mask_builder=PublicActionMaskBuilder(builder)
    template=load_verified_template(CAPTURE,file_sha(CAPTURE/'plan.json'))
    prospective_manifest=json.loads((PROSPECTIVE.parent/'manifest.json').read_text())
    reserved_configs={r['config_sha256'] for r in prospective_manifest['episodes'] if r['status']=='configured'}
    source_paths=[*Path('src/clasher').rglob('*.py'),Path(__file__)]
    source_pins={str(p.resolve()):file_sha(p) for p in sorted(source_paths)}
    write(output/'root-bank.json',bank.model_dump(mode='json'))
    write(output/'study-design.json',{
        'evidence_role':'opened_scalar_development','master_seed':SEED,
        'scope':'root-selection design feasibility only; no continuation outcomes, native coverage or training labels',
        'scalar_initial_realization':'declared ordered deck first four cards in hand, remaining four in cycle; native shuffle equivalence unproven',
        'prefix':'two public controllers at five-tick cadence from tick90; root selector balanced; first eligible focal/context root',
        'no_replacement':True,
        'owner_prefix_elixir_reserve':OWNER_PREFIX_ELIXIR_RESERVE,
        'generator_revision':'root-bank-v2 offensive enemy_backline, stop3600, declared shared prefix reserve',
        'reserve_rule':'Only root owner prefix actions become wait while own public elixir<8; other player unchanged; candidate generation and future continuation controllers unchanged',
        'scope_note':'Prefix-only high-resource exploration design; selected root elixir is recorded rather than assuming all selected roots are high resource','continuation_conditions_declared_not_executed':list(bank.conditions),
        'native_data_authority':str(loader.data_file),'gamedata_sha256':file_sha(loader.data_file),
        'catalog_path':prior['catalog_path'],'catalog_sha256':prior['catalog_sha256'],
        'excluded_prospective_bank':str(PROSPECTIVE),'excluded_prospective_bank_sha256':file_sha(PROSPECTIVE),
        'source_pins':source_pins})
    results=[];started=time.monotonic()
    for index,request in enumerate(bank.requests):
        folder=output/request.family_id;folder.mkdir()
        native_config=config_for_request(request,template,loader,loader)
        assert canonical_sha(native_config) not in reserved_configs
        write(folder/'request.json',request.model_dump(mode='json'))
        write(folder/'unexecuted-native-config.json',native_config)
        players=[PlayerState(owner,deck=list(deck),hand=list(deck[:4]),cycle_queue=deque(deck[4:])) for owner,deck in enumerate(request.decks)]
        battle=BattleState(players=players,rng=random.Random(request.episode_seed),card_loader=loader)
        prefix=[PublicScriptedOpponent(builder,style=style) for style in request.prefix_styles]
        root_controller=CachedRootController(builder,style='balanced')
        counts=Counter();selected_views=[];commands=0;start=time.monotonic()
        failure=None;selection=None
        with gzip.open(folder/'prefix.jsonl.gz','xt') as log,contextlib.redirect_stdout(io.StringIO()):
            def packets():
                nonlocal commands,selected_views
                while battle.tick<90:battle.step()
                for tick in range(90,request.stop_tick+1,5):
                    assert battle.tick==tick or battle.game_over
                    views=[reference_public_observation(builder.build_actor(battle,owner)) for owner in (0,1)]
                    selected_views=views
                    view=views[request.root_owner]
                    masks=[mask_builder.build(PublicActionMaskInput.from_confidence_observation(p)) for p in views]
                    focal=builder.token_id(request.focal_card,namespace='card_action')
                    counts['observed_packets']+=1
                    if focal in view.observation.hand_ids[:4]:counts['focal_in_current_hand']+=1
                    if focal not in view.observation.hand_ids[:4]:counts['focal_absent_current_hand']+=1
                    affordable_identities={int(token) for slot,token in enumerate(view.observation.hand_ids[:4]) if token>1 and masks[request.root_owner][slot*576:(slot+1)*576].any()}
                    if len(affordable_identities)<2:counts['two_affordable_distinct_cards_absent']+=1
                    focal_slots=[slot for slot,token in enumerate(view.observation.hand_ids[:4]) if token==focal]
                    if any(masks[request.root_owner][slot*576:(slot+1)*576].any() for slot in focal_slots):counts['focal_public_legal']+=1
                    context=context_matches(request.context,root_controller,view)
                    if not context:counts['context_absent']+=1
                    if not context:counts['first_failed_condition_context_absent']+=1
                    elif focal not in view.observation.hand_ids[:4]:counts['first_failed_condition_focal_absent']+=1
                    elif len(affordable_identities)<2:counts['first_failed_condition_two_affordable_absent']+=1
                    else:counts['context_focal_and_two_affordable_present']+=1
                    if context:
                        counts['context_matches']+=1
                        try:candidates=generate_candidates(root_controller,view)
                        except ValueError as exc:
                            if not str(exc).startswith('ineligible root:'):raise
                            counts['candidate_set_ineligible']+=1
                        else:
                            counts['candidate_set_available']+=1
                            if focal in {c.card_token for c in candidates}:counts['focal_in_candidates']+=1
                            else:counts['eligible_candidates_omit_focal']+=1
                    yield battle.tick,view
                    if tick==request.stop_tick or battle.game_over:return
                    original_actions=[bot.select_action(packet) for bot,packet in zip(prefix,views)]
                    actions=[apply_prefix_owner_reserve(request,owner,packet,action) for owner,(packet,action) in enumerate(zip(views,original_actions))]
                    own_elixir=float(views[request.root_owner].observation.global_features[5])*10
                    reserve_active=own_elixir<request.prefix_owner_min_elixir
                    if reserve_active:
                        counts['owner_prefix_reserve_active']+=1
                        if actions[request.root_owner]!=2304:counts['owner_prefix_play_replaced_by_declared_wait']+=1
                    log.write(json.dumps({'tick':tick,'actions':actions,'ordinary_prefix_actions':original_actions,'reserve_active':reserve_active,'owner_elixir':own_elixir,'public_sha256':[packet_sha(p) for p in views]},separators=(',',':'))+'\n')
                    for owner,action in enumerate(actions):
                        if not masks[owner][action]:raise ValueError('public prefix controller selected illegal command')
                        choice=space.decode_action(action,owner)
                        if choice.is_no_op:continue
                        name=builder.card_name_for_token_id(int(views[owner].observation.hand_ids[choice.slot]))
                        if not battle.deploy_card(owner,name,choice.position):raise ValueError('scalar rejected public-legal prefix command')
                        commands+=1
                    for _ in range(5):
                        if not battle.game_over:battle.step()
            try:
                selection=select_root(request,root_controller,packets())
                if selection.status=='selected':
                    for owner,view in enumerate(selected_views):
                        PublicPolicySequence.from_observations(builder,[view]).save(folder/f'root-owner-{owner}.npz')
            except Exception as exc:failure={'type':type(exc).__name__,'message':str(exc)}
        result={'request':request.model_dump(mode='json'),'selection':None if selection is None else selection.model_dump(mode='json'),
            'failure':failure,'owner_prefix_elixir_reserve':OWNER_PREFIX_ELIXIR_RESERVE,
            'selected_root_own_elixir':None if selection is None or selection.status!='selected' else float(selected_views[request.root_owner].observation.global_features[5])*10,
            'diagnostics':dict(counts),'scalar_prefix_commands':commands,
            'scalar_last_tick':battle.tick,'elapsed_seconds':time.monotonic()-start,'native_config_sha256':canonical_sha(native_config)}
        write(folder/'selection-result.json',result);results.append(result)
        status='error' if failure else selection.status
        print(f'{index+1}/32 {request.focal_card} seat{request.root_owner} {request.context}: {status} tick{battle.tick}',flush=True)
    statuses=Counter('error' if row['failure'] else row['selection']['status'] for row in results)
    by_context={context:dict(Counter('error' if row['failure'] else row['selection']['status'] for row in results if row['request']['context']==context)) for context in sorted({r.context for r in bank.requests})}
    changed=[path for path,digest in source_pins.items() if file_sha(Path(path))!=digest]
    summary={'evidence_role':'opened_scalar_development','master_seed':SEED,'owner_prefix_elixir_reserve':OWNER_PREFIX_ELIXIR_RESERVE,'requests':32,'status_counts':dict(statuses),
        'by_context':by_context,'elapsed_seconds':time.monotonic()-started,'source_changes_during_study':changed,
        'continuations_executed':0,'native_calls':0,'outcome_or_training_labels_produced':0,'results':results}
    write(output/'summary.json',summary)
    print(json.dumps({key:value for key,value in summary.items() if key!='results'},indent=2),flush=True)


if __name__=='__main__':main()
