"""Registered four-game prefix verification; no outcome or timing statistics.

Original receipts contain candidate counts, not candidate lists. Therefore this
checks original commands/counts and duplicate replay candidate/public-state hashes
separately. It never claims an unrecorded original hash was checked.
"""
import argparse,hashlib,json,pathlib,pickle,time
import torch
from imitation.evaluation.paths import setup,COUNCIL
setup()
from fair_player import Resources,observe
from stage2_matches import battle
from sidecar_observer import SidecarObserver
from derived_public_state import PublicEvent as SearchEvent
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskInput
from imitation.model import load_policy
from imitation.evaluation.search import ImitationDeadlinePlayer,MatchedDeadlinePlayer
from imitation.evaluation.d1 import model_packet

def once(row,resources,prior,policy):
    seat=row['seat'];b=battle(dict(seed=row['seed'],decks=row['decks']),resources.builder.loader)
    initial=hashlib.sha256(pickle.dumps([resources.builder.build_public(b,s) for s in (0,1)],protocol=4)).hexdigest()
    order=list(b.players[seat].hand)+list(b.players[seat].cycle_queue)
    player=(ImitationDeadlinePlayer(resources,prior,row['seed']+100000+seat,policy,seat,order)
            if row['arm']=='B' else MatchedDeadlinePlayer(resources,prior,row['seed']+100000+seat))
    other=MatchedDeadlinePlayer(resources,prior,row['seed']+100000+1-seat) if row['mode']=='head-to-head' else None
    if row['arm']=='B':
        opening=resources.builder.build_public(b,seat)
        mask=resources.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(opening))
        policy.propose(model_packet(opening,mask),player.d1.update(0,[]),8)
    cutoffs=[(90+5*i,seat) for i,r in enumerate(row['deadline_receipts']) if r.get('truncated')]
    if other is not None:cutoffs += [(90+5*i,1-seat) for i,r in enumerate(row['baseline_deadline_receipts']) if r.get('truncated')]
    cutoff=min(cutoffs) if cutoffs else (row['ticks'],0)
    original={(t,s):(a,ok) for t,s,a,ok in row['actions']}
    captured=[];context={};counts_index=0;decisions=0;applied=0;failures=[]
    for actor,controller in ((seat,player),(1-seat,other)):
        if controller is None:continue
        original_score=controller.core.score_candidates
        def wrap(root,root_seat,candidates,deadline=None,*,_score=original_score,_actor=actor):
            captured.append(dict(tick=b.tick,seat=_actor,candidates=list(map(int,candidates))))
            return _score(root,root_seat,candidates,deadline=deadline)
        controller.core.score_candidates=wrap
    space=DiscreteTileActionSpace()
    with SidecarObserver(resources.builder) as sensor:
        sensor.audit_counters={'opponent_elixir_topup_total':0.};sensor(b,seat,None)
        while not b.game_over and b.tick<=cutoff[0]:
            if b.tick>=90 and b.tick%5==0:
                moves={}
                for actor in (0,1):
                    if (b.tick,actor)>=cutoff:
                        return dict(seed=row['seed'],seat=seat,arm=row['arm'],initial_public_state_sha256=initial,cutoff=cutoff,decisions_checked=decisions,accepted_or_rejected_commands_checked=applied,candidates=captured,candidate_count_roots_checked=counts_index,failures=failures,passed=not failures)
                    controller=player if actor==seat else other
                    if controller is None:
                        action=int(resources.bots[row['style']].select_action(resources.builder.build_public(b,actor)));searched=False
                    else:
                        events=[SearchEvent(e['tick'],e['kind'],e['name'],e['amount']) for e in sensor.public_events if e['seat']!=actor]
                        info=observe(b,resources.builder,actor,events)
                        extra={'public_events':sensor.public_events} if actor==seat and row['arm']=='B' else {}
                        # Original roots in this prefix completed every candidate.
                        # An infinite deadline removes replay host timing as a cause
                        # of truncation; policy/search/scoring code is unchanged.
                        action,searched=controller.decide(info,(b.tick-90)//5,deadline=float('inf'),**extra)
                        if actor==seat and row['arm']=='B' and searched:
                            expected=row['candidate_count_receipts'][counts_index];actual=list(player.candidate_counts)
                            if actual!=expected:failures.append(dict(kind='candidate_count',tick=b.tick,expected=expected,actual=actual))
                            counts_index+=1
                    expected=original.get((b.tick,actor),(2304,None))[0]
                    if int(action)!=expected:failures.append(dict(kind='command',tick=b.tick,seat=actor,expected=expected,actual=int(action)))
                    moves[actor]=int(action);decisions+=1
                for actor in (0,1):
                    action=moves[actor]
                    if action==2304:continue
                    actual=bool(space.apply_action(b,actor,action));expected=original.get((b.tick,actor),(None,None))[1]
                    if actual!=expected:failures.append(dict(kind='engine_acceptance',tick=b.tick,seat=actor,expected=expected,actual=actual))
                    applied+=1
                if failures:break
            b.step()
    return dict(seed=row['seed'],seat=seat,arm=row['arm'],initial_public_state_sha256=initial,cutoff=cutoff,decisions_checked=decisions,accepted_or_rejected_commands_checked=applied,candidates=captured,candidate_count_roots_checked=counts_index,failures=failures,passed=not failures)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    policy=load_policy(a.checkpoint);resources=Resources();prior=json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text());results=[]
    names=['pair-000-B-0.json','pair-000-B-1.json','pair-320-B-0.json','pair-320-A-0.json']
    for name in names:
        raw=(a.root/name).read_bytes();row=json.loads(raw)
        runs=[once(row,resources,prior,policy) for _ in range(2)]
        exact=runs[0]==runs[1]
        results.append(dict(file=name,input_sha256=hashlib.sha256(raw).hexdigest(),duplicate_prefix_exact=exact,runs=runs,passed=exact and all(x['passed'] for x in runs)))
    value=dict(passed=all(r['passed'] for r in results),games=4,outcomes_read=False,selection='fixed first primary world bothseats plus first secondary world B0/A0; no selection on outcomes',original_candidate_list_equality_testable=False,limitation='Original candidate lists and initial-state hashes were not retained. Original recorded commands and candidate counts are checked; duplicate replay candidate lists/public-state hashes are separately checked. Stops before first originally truncated root. No score adjustments.',results=results)
    with a.output.open('x') as f:json.dump(value,f,indent=2)
    print(json.dumps({k:value[k] for k in ('passed','games','original_candidate_list_equality_testable')}))

if __name__=='__main__':main()
