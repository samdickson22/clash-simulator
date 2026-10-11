"""S6 W-screen8 teacher games, public v6 rows, and deterministic action replay."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
import numpy as np

R = PRIOR = POLICY = None


def initialize(checkpoint=None):
    global R, PRIOR, POLICY
    from clasher.rl.wait_screen8 import load_native
    load_native(os.environ['CLASHER_DELAY_NATIVE_DIR'])
    from imitation.evaluation.paths import ROOT, COUNCIL, setup
    setup()
    sys.path.insert(0, str(COUNCIL/'search-noise-s6'))
    import torch
    torch.set_num_threads(1)
    from fair_player import Resources
    from quickwin_resources import cached_resources
    R = cached_resources(Resources)()
    PRIOR = json.loads((COUNCIL/'c56/engine/root-v3/human_deck_catalog.json').read_text())
    if checkpoint:
        from imitation.model.inference import load_policy
        POLICY = load_policy(checkpoint)
    return R


def decks():
    from clasher.analysis.loss_review.metrics import archetype
    selected = [max((d for d in PRIOR['decks'] if archetype(d['cards']) == f),
                    key=lambda d: d['frequency'])['cards']
                for f in ('bridge_wincon', 'siege', 'beatdown', 'bait', 'chip')]
    selected += [['HogRider','Musketeer','Cannon','Fireball','Log','IceGolem','IceSpirit','Skeletons'],
        ['Xbow','Tesla','Knight','Archers','Fireball','Log','Skeletons','ElectroSpirit'],
        ['RoyalHogs','FirespiritHut','GoblinHut','Berserker','Ghost','Fireball','Log','ElectroSpirit']]
    return selected


def player(seed, w=True):
    from fair_player import PublicPlanner
    from delay import DelayAwarePlanner
    from imitation.evaluation.fast_prior import ExactFastPrior
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    p = PublicPlanner(R, PRIOR, seed)
    p.belief.__class__ = ExactFastPrior
    p.core = DelayAwarePlanner(R.builder, R.bots, backend='native', seed=seed+1,
        native=R.native, native_config=R.config, command_delay=27, delay_aware=True,
        config=C56SearchConfig(threads=1, wait_screen8=w))
    return p


def stopped(path):
    return bool(path and Path(path).exists())


def run_game(seed, index, directory, opponent='script', stop=None, acceptance=False, max_ticks=6001):
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from imitation.evaluation.d1 import D1Tracker, model_packet
    from imitation.evaluation.events import PublicRecorder
    from imitation.evaluation.standalone import StandalonePlayer
    from imitation.model.features import build_row
    from .rows import observation, feature_bytes, seal, write_json, WAIT

    selected = decks()
    own, other = list(selected[index%8]), list(selected[(index//8)%8])
    rng = random.Random(seed)
    rng.shuffle(own); rng.shuffle(other)
    seat = index%2
    ep = dict(seed=seed, decks=[own, other] if seat == 0 else [other, own])
    b = battle(ep, R.builder.loader)
    teacher = player(seed+100000)
    enemy = player(seed+100002, opponent=='W') if opponent in ('W','baseline') else None
    channels = [CommandQueue(27, 1), CommandQueue(27, 1)]
    until = [0,0]
    tracker = D1Tracker(R.builder, R.costs, seat, own)
    mask_builder = ContractV5ActionMaskBuilder(R.builder)
    costs = np.zeros(360, np.float32)
    for name,cost in R.costs.items():
        costs[R.builder.token_id(name, namespace='card_action')] = cost

    class Capture:
        from types import SimpleNamespace
        import torch
        model = SimpleNamespace(temperatures=torch.ones(3))
        def sample(self, packet, d1, generator):
            self.features = build_row(packet, d1, costs)
            return WAIT
    capture = Capture()
    oracle = StandalonePlayer(capture, R.builder, R.costs, seat, own, seed) if acceptance else None
    v1 = StandalonePlayer(POLICY, R.builder, R.costs, 1-seat, other, seed+13) if opponent=='v1' else None
    if opponent=='v1' and POLICY is None:
        raise ValueError('v1 opponent requires an explicit released checkpoint')
    rows, scores, commands, observations, submissions = [], [], [], [], []
    decisions = 0
    cpu0, wall0 = time.process_time(), time.monotonic()
    with PublicRecorder(R.builder) as recorder:
        recorder.bind(b)
        while not b.game_over and b.tick < max_ticks:
            if stopped(stop):
                return None  # In-flight games are expendable, never sealed.
            for actor,ch in enumerate(channels):
                while ch.ready(b.tick):
                    c = ch.pending[0]
                    ok = teacher.core.space.apply_action(b, actor, c.action)
                    commands.append([b.tick, actor, c.action, bool(ok)])
                    ch.finish(ok)
            if b.tick%5 == 0:
                packet = R.builder.build_public(b, seat)
                mask = mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                d1 = tracker.update(b.tick, recorder.public_events)
                row = observation(packet, mask, d1, R.builder)
                if oracle:
                    _, refmask = oracle.decide(b.tick, packet, recorder.public_events)
                    assert mask.tobytes() == refmask.tobytes()
                    for k,v in d1.items():
                        assert v.tobytes() == oracle.last_d1[k].tobytes(), k
                    rebuilt = feature_bytes(row, costs)
                    for k,v in rebuilt.items():
                        assert v.tobytes() == capture.features[k].tobytes(), k
                    from clasher.rl.public_policy_contract import PublicPolicySequence
                    raw=PublicPolicySequence.from_observations(R.builder,[packet]).arrays
                    for k in ('hand_ids','hand_levels','global_features','opponent_history_ids','opponent_history_ages',
                              'opponent_seen_card_ids','own_last_play_ids','own_last_play_features','board_rotated','terminal_status'):
                        assert row[k].tobytes()==raw[k][0].astype(row[k].dtype).tobytes(),k
                action, chosen, why = WAIT, WAIT, 'poll_wait'
                root_scores = dict(candidates=[], scores=[])
                for actor in (0,1):
                    ch = channels[actor]
                    p = teacher if actor==seat else enemy
                    move = WAIT
                    if v1 and actor!=seat:
                        # Gate-c actor still consumes every 5-tick public poll.
                        proposed,_ = v1.decide(b.tick, R.builder.build_public(b,actor), recorder.public_events)
                    else:
                        proposed = WAIT
                    if b.tick >= 90 and ch.available and b.tick >= until[actor]:
                        info = observe(b, R.builder, actor, [PublicEvent(**{k:e[k] for k in PublicEvent.__dataclass_fields__})
                            for e in recorder.public_events if e['seat'] != actor])
                        if p and b.tick%10 == 0:
                            p.belief.update(info.tick, info.events)
                            p.core.info, p.core.costs = info, R.costs
                            candidates,_ = p.core.candidates(info.packet)
                            candidates = [a for a in candidates if a != 2305]
                            root = R.root(info, p.belief.sample(p.rng), p.rng)
                            selected_action = p.core.score_candidates(root, actor, candidates)
                            move = WAIT if selected_action >= WAIT else selected_action
                            if actor==seat:
                                decisions += 1
                                chosen,why = selected_action,'search'
                                root_scores = {k:p.core.last[k] for k in ('candidates','scores')}
                                for a,v in zip(root_scores['candidates'],root_scores['scores']):
                                    if v is not None and a<2400 and not mask[a]:
                                        raise AssertionError('scored candidate outside gate-c mask')
                            until[actor] = b.tick + getattr(p.core,'selected_wait_ticks',0)
                        elif not p:
                            if v1:
                                move = proposed if proposed < WAIT else WAIT
                            elif b.tick%10 == 0:
                                move = int(R.bots[('balanced','pressure','defense')[index%3]].select_action(info.packet))
                                if move >= WAIT: move = WAIT
                        if move < WAIT:
                            ch.submit(info, int(move), R.costs, R.builder)
                            submissions.append([b.tick,actor,int(move)])
                    if actor==seat:
                        action = move
                        if why != 'search':
                            why = 'pending' if not ch.available else 'timed_wait' if b.tick < until[actor] else 'poll_wait'
                if not mask[action]:
                    raise AssertionError('teacher selected a masked gate-c action')
                row.update(expert_actions=np.int16(action), expert_action_supervision_valid=np.bool_(True),
                    submitted_ticks=np.int32(b.tick), teacher_search_action=np.int16(chosen),
                    teacher_root=np.bool_(why=='search'), teacher_wait_kind=np.int8(
                        {'search':0,'poll_wait':1,'timed_wait':2,'pending':3}[why]))
                position=teacher.core.space.decode_action(action,seat).position
                xy=[np.nan,np.nan] if position is None else [position.x,position.y]
                row.update(recorded_play_ticks=np.int32(-1 if action==WAIT else b.tick+27),
                    recorded_world_positions=np.array(xy,np.float32),submitted_world_positions=np.array(xy,np.float32),
                    recorded_millitiles=np.array([-1,-1] if position is None else [round(position.x*1000),round(position.y*1000)],np.int32))
                rows.append(row); scores.append(root_scores)
                observations.append(hashlib.sha256(b''.join(row[k].tobytes() for k in sorted(row)
                    if k not in ('expert_actions','expert_action_supervision_valid','teacher_search_action','teacher_root','teacher_wait_kind'))).hexdigest())
            b.step()
        if not b.game_over:
            raise RuntimeError('truncated game cannot supply a final outcome')
        outcome = 0. if b.winner is None else 1. if b.winner==seat else -1.
        receipt = dict(seed=seed, index=index, seat=seat, opponent=opponent, episode=ep,
            outcome=outcome, winner=b.winner, ticks=b.tick, rows=len(rows), root_decisions=decisions,
            cpu_seconds=time.process_time()-cpu0, wall_seconds=time.monotonic()-wall0,
            gate_c_byte_equal=bool(oracle), byte_checks=len(rows) if oracle else 0,
            plays=sum(int(r['expert_actions'])<WAIT for r in rows), commands=commands,
            observation_hashes=observations, submissions=submissions, events=recorder.public_events)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory/'replay.json', receipt)
    if acceptance:
        replay(ep, seat, receipt, rows, costs)
        receipt['replay_exact'] = True
    seal(directory, rows, scores, receipt)
    print(json.dumps({k:receipt[k] for k in ('seed','rows','root_decisions','plays','cpu_seconds','wall_seconds','outcome')}), flush=True)
    return receipt


def replay(ep, seat, receipt, rows, costs):
    from fair_player import observe
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from stage2_matches import battle
    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from imitation.evaluation.events import PublicRecorder
    from imitation.evaluation.d1 import D1Tracker
    from .rows import observation
    b = battle(ep, R.builder.loader)
    tracker = D1Tracker(R.builder, R.costs, seat, ep['decks'][seat])
    mask_builder = ContractV5ActionMaskBuilder(R.builder)
    space = DiscreteTileActionSpace()
    cursor = row_index = sub_index = 0
    channels=[CommandQueue(27,1),CommandQueue(27,1)]
    with PublicRecorder(R.builder) as recorder:
        recorder.bind(b)
        while b.tick < receipt['ticks']:
            for actor,ch in enumerate(channels):
                while ch.ready(b.tick):
                    action=ch.pending[0].action
                    ok=bool(space.apply_action(b,actor,action))
                    assert [b.tick,actor,action,ok]==receipt['commands'][cursor]
                    ch.finish(ok);cursor+=1
            if b.tick%5 == 0:
                packet = R.builder.build_public(b,seat)
                mask = mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                actual = observation(packet,mask,tracker.update(b.tick,recorder.public_events),R.builder)
                expected = rows[row_index]
                for k,v in actual.items():
                    assert v.tobytes()==expected[k].tobytes(), (b.tick,k)
                submitted=[]
                while sub_index<len(receipt['submissions']) and receipt['submissions'][sub_index][0]==b.tick:
                    _,actor,action=receipt['submissions'][sub_index]
                    submitted.append((actor,action))
                    info=observe(b,R.builder,actor,())
                    channels[actor].submit(info,action,R.costs,R.builder)
                    sub_index+=1
                label=int(expected['expert_actions'])
                assert [(a,x) for a,x in submitted if a==seat]==([] if label==2304 else [(seat,label)])
                row_index += 1
            b.step()
        assert b.game_over and b.winner==receipt['winner'] and cursor==len(receipt['commands'])
        assert sub_index==len(receipt['submissions'])
        assert recorder.public_events == receipt['events']
        assert row_index==len(rows)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',required=True); p.add_argument('--checkpoint')
    p.add_argument('--seed',type=int,default=4503599707370496)
    p.add_argument('--index',type=int,default=0)
    p.add_argument('--opponent',choices=['W','baseline','v1','script'],default='script')
    p.add_argument('--acceptance',action='store_true'); p.add_argument('--stop')
    a=p.parse_args(); initialize(a.checkpoint)
    run_game(a.seed,a.index,a.out,a.opponent,a.stop,a.acceptance)


if __name__=='__main__': main()
