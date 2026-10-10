"""Paired search opponents using existing fair roots and delay-fixes channels."""
import argparse
import copy
from dataclasses import replace
from latency import apply_lateness
from gc_window import WINDOW
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import random
import socket
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
COUNCIL = ROOT / 'reports/strategy_council_20260928'
sys.path[:0] = [str(ROOT / 'src'), str(Path(__file__).resolve().parent)]
R = CAT = PRIOR = OPTIONS = POLICY = STUDENT = None
SLOT_CORES = None


def initialize():
    global R, CAT, PRIOR, POLICY, STUDENT
    sys.path.insert(0, os.environ['CLASHER_DELAY_NATIVE_DIR'])
    import clasher_core
    sys.path[:0] = [str(ROOT / 'engine-rs'), str(COUNCIL / 'engine-speed/stage5'),
                   str(COUNCIL / 'search-noise-s6')]
    import torch
    torch.set_num_threads(1)
    from fair_player import Resources
    from quickwin_resources import cached_resources
    from clasher.analysis.loss_review.human import make_catalog
    R = cached_resources(Resources)()
    CAT = make_catalog(R.builder)
    PRIOR = json.loads((COUNCIL / 'c56/engine/root-v3/human_deck_catalog.json').read_text())
    from imitation.model import load_policy
    cfg = json.loads((Path(__file__).parent/'plan.json').read_text())
    checkpoint = Path(cfg['policy']['checkpoint'])
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == cfg['policy']['checkpoint_sha256']
    POLICY = load_policy(checkpoint)
    assert hashlib.sha256(Path(cfg['student']['calibration']).read_bytes()).hexdigest()==cfg['student']['calibration_sha256']
    assert POLICY.model.temperatures.tolist() == [1.,1.,1.]
    from proposals import load_student
    ck=Path(cfg['student']['checkpoint'])
    assert hashlib.sha256(ck.read_bytes()).hexdigest()==cfg['student']['checkpoint_sha256']
    STUDENT=load_student(ck,cfg['student']['threshold'])
    return clasher_core.__file__


def make_player(seed, arm, reserve_floor=False, search_threads=1, coarse_horizon=160,kernel="coarse-first"):
    from fair_player import PublicPlanner
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    if kernel=="K2-anytime":
        from anchor import planner_class
    else:
        from planner import planner_class
    p = PublicPlanner(R, PRIOR, seed)
    from belief import Belief
    # Reuse the initialized frozen prior; deadline updates use copy-on-write.
    p.belief.__class__ = Belief
    p.core = planner_class(DelayAwarePlanner)(R.builder, R.bots, backend='native',
        seed=seed+1, native=R.native, native_config=R.config, catalog=CAT,
        config=C56SearchConfig(threads=1, horizon=160,
                              wait_screen8=False),  # Frozen wrapper adds W itself.
        command_delay=27, delay_aware=True, symmetric_opponent=True,
        opponent_delay=27, opponent_interval=10, opponent_capacity=1,
        max_outstanding=1, arm=arm, variant='screen8' if arm == 'W' else 'full', reserve_floor=reserve_floor, search_threads=search_threads, coarse_horizon=coarse_horizon)
    return p


def run_game(case):
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from imitation.evaluation.events import PublicRecorder
    from policy import V1Policy
    from clasher.rl.action_space import DiscreteTileActionSpace
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from clasher.analysis.loss_review.metrics import Game, archetype, extract
    from clasher.analysis.loss_review.human import write
    from clasher.rl.public_observation import REAL_PLAY_ENTITY_FEATURE_INDICES
    pair, seed, arm, own, other, seat, population, cell = case
    spec = OPTIONS['arms'][arm]
    width = 1 if spec['threads'] == 1 else spec['threads']+1
    os.sched_setaffinity(0, set(SLOT_CORES[:width]))
    WINDOW.events.clear()
    start, cpu = time.perf_counter(), time.process_time()
    rng = random.Random(seed)
    own, other = list(own), list(other)
    rng.shuffle(own); rng.shuffle(other)
    b = battle(dict(seed=seed, decks=[own, other] if seat == 0 else [other, own]), R.builder.loader)
    spec = OPTIONS['arms'][arm]
    deadline_seconds = spec['deadline_seconds']
    players = {seat: make_player(seed+100000, 'W' if spec['own']=='W-screen8' else '0', spec.get('reserve_floor',False), spec['threads'], spec['coarse_horizon'],spec['kernel'])}
    if spec['opponent'] == 'baseline':
        players[1-seat] = make_player(seed+100002, '0')
    policies = {a: V1Policy(POLICY,R.builder,R.costs,a,
        list(b.players[a].hand)+list(b.players[a].cycle_queue),seed+271828+a) for a in (0,1)}
    from cached_policy import CachedPolicy
    cfg=json.loads((Path(__file__).parent/'plan.json').read_text())
    cached=None
    capture=None
    if OPTIONS.get("corpus"):
        from corpus import Reservoir,committed_belief
        capture=Reservoir()
    # Stack assertion binds every real forward to this game's active GC/timer scope.
    def inference_check():
        frame=sys._getframe(1)
        while frame is not None and frame.f_code is not run_game.__code__:frame=frame.f_back
        assert frame is not None and 'wall0' in frame.f_locals
        assert time.monotonic()>=frame.f_locals['wall0'] and WINDOW.active
    if spec['policy']!='v1-unmodified':
        cached=CachedPolicy(POLICY if spec['policy']=='v1-cached' else STUDENT,
                            None if spec['policy']=='v1-cached' else cfg['student']['threshold'],inference_check)
        policies[seat]=V1Policy(cached,R.builder,R.costs,seat,list(b.players[seat].hand)+list(b.players[seat].cycle_queue),seed+271828+seat)
    space = DiscreteTileActionSpace()
    recorder = PublicRecorder(R.builder)
    recorder.__enter__();recorder.bind(b)
    deadline_stats = {a: [] for a in (0,1)}
    command_hash = hashlib.sha256()
    channels = {a: CommandQueue(27, 1) for a in (0, 1)}
    waits = {0: 0, 1: 0}
    available_at = {0: 0, 1: 0}
    public_events = {0: [], 1: []}
    latencies = {a: [] for a in (0, 1)}
    cpu_latencies = {a: [] for a in (0, 1)}
    ticks, globals_, hands, queues, entities, ids, offsets, plays = [], [], [], [], [], [], [0], []
    cols = sorted(REAL_PLAY_ENTITY_FEATURE_INDICES)

    def act(actor, command):
        if b.players[actor].hand[command.action//576] != command.card:
            raise AssertionError('pending slot changed')
        choice = space.decode_action(command.action, actor)
        elixir = b.players[actor].elixir
        ok = space.apply_action(b, actor, command.action)
        command_hash.update(f'{b.tick},{actor},{command.action},{int(bool(ok))};'.encode())
        if actor == seat:
            x, y = choice.position.x, choice.position.y
            if seat: x, y = 18-x, 32-y
            plays.append(dict(tick=b.tick, card=command.card, x=x, y=y,
                              accepted=bool(ok), elixir_before=elixir))
        if ok:
            public_events[1-actor].append(PublicEvent(b.tick, 'card', command.card))
        return ok

    def complete(actor):
        ch = channels[actor]
        while ch.ready(b.tick):
            ch.finish(act(actor, ch.pending[0]))

    while not b.game_over and b.tick < OPTIONS['max_ticks']:
        if b.tick%5==0:
            j=Path(os.environ.get('T1_JOB','/mpac/sdicks02/jobs/clasher/t1-20261010-r1'))
            if (j/'STOP').exists() or (j/f'STOP-{socket.gethostname()}').exists():raise InterruptedError('owned T1 stop')
        if b.tick % 5 == 0:
            ob = R.builder.build_public(b, seat).observation
            ticks.append(b.tick); globals_.append(ob.global_features.copy()); hands.append(ob.hand_ids.copy())
            q = list(b.players[seat].cycle_queue)
            queues.append([R.builder.token_id(n, namespace='card_action') for n in q] + [0]*(8-len(q)))
            ef = ob.entity_features[ob.entity_mask][:, cols].copy()
            entities.append(ef); ids.append(ob.entity_ids[ob.entity_mask].copy()); offsets.append(offsets[-1]+len(ef))
        for actor in (0, 1): complete(actor)
        if b.tick >= 90 and b.tick % 5 == 0:
            # Frozen gate(c) policy cadence, even while delayed channel is blocked.
            for actor in (0, 1):
                ch = channels[actor]
                capture_before = None
                if capture is not None and actor==seat and b.tick>=90 and b.tick%10==0 and ch.available and b.tick>=waits[actor] and b.tick>=available_at[actor]:
                    p=players[actor]
                    capture_before=dict(pending=copy.deepcopy(tuple(ch.pending)),belief_had_suspended_transaction=getattr(p.belief,"_pending",None) is not None,belief_before=committed_belief(p.belief),belief_rng_state=copy.deepcopy(p.rng.bit_generator.state),candidate_rng_state=copy.deepcopy(p.core.rng.bit_generator.state),policy_rng_state=policies[actor].player.generator.get_state().clone(),d1_before=copy.deepcopy({k:v for k,v in policies[actor].player.d1.__dict__.items() if k!='builder'}),d1_events=copy.deepcopy(recorder.public_events))
                with WINDOW:
                    wall0, cpu0 = time.monotonic(), time.process_time()
                    info = observe(b, R.builder, actor, public_events[actor])
                    reserved = ch.own_packet(info, R.builder)
                    fallback = int(policies[actor].poll(b.tick,reserved.packet,recorder.public_events))
                    if not ch.available or b.tick < waits[actor] or b.tick < available_at[actor]:
                        if actor not in players or b.tick % 10 == 0: ch.blocked += 1
                        continue
                    if actor not in players:
                        if fallback < 2304: ch.submit(info, fallback, R.costs, R.builder)
                        latencies[actor].append(time.monotonic()-wall0)
                        cpu_latencies[actor].append(time.process_time()-cpu0)
                        continue
                    if b.tick % 10:
                        continue
                    p = players[actor]
                    cutoff = None if deadline_seconds is None else wall0+deadline_seconds-OPTIONS['return_reserve_seconds']
                    unpruned_count = None
                    try:
                        p.belief.update(info.tick, info.events, deadline=cutoff)
                    except TimeoutError:
                        preparation_hit = True
                    else:
                        preparation_hit = False
                    if preparation_hit:
                        action = fallback if fallback < 2305 else 2304
                        p.core.selected_wait_ticks = 0
                        p.core.deadline_stats = dict(hit=True,fallback=True,completed=0,candidates=0,preparation_cutoff='belief')
                        if action < 2304: ch.submit(info, int(action), R.costs, R.builder)
                    else:
                        p.core.info, p.core.costs, p.core.pending = info, R.costs, tuple(ch.pending)
                        p.core.opponent_elixir = policies[actor].opponent_elixir
                        proposals=()
                        if cached is not None:
                            from imitation.evaluation.d1 import model_packet
                            proposals=cached.propose(model_packet(reserved.packet,policies[actor].mask),policies[actor].player.last_d1)
                        candidates, mask = p.core.candidates(reserved.packet,[v["action"] for v in proposals])
                        candidates = [a for a in candidates if a != 2305]
                        unpruned_count = len(candidates)
                        action = 2304
                        if len(candidates) > 1:
                            if cutoff is not None and time.monotonic() >= cutoff:
                                action = fallback if fallback < 2305 else 2304
                                p.core.selected_wait_ticks = 0
                                p.core.deadline_stats = dict(hit=True,fallback=True,completed=0,candidates=len(candidates))
                            else:
                                try:
                                    opponent = p.belief.sample(p.rng, deadline=cutoff)
                                except TimeoutError:
                                    action = fallback if fallback < 2305 else 2304
                                    p.core.selected_wait_ticks = 0
                                    p.core.deadline_stats = dict(hit=True,fallback=True,completed=0,candidates=len(candidates),preparation_cutoff='sample')
                                else:
                                    root = R.root(info, opponent, p.rng)
                                    action = p.core.score_candidates(root, actor, candidates, deadline=cutoff,
                                        fallback=fallback if fallback < 2305 else 2304)
                            if p.core.selected_wait_ticks:
                                waits[actor] = b.tick + p.core.selected_wait_ticks
                            for name in p.core.attrition:
                                slots = np.flatnonzero(info.packet.observation.hand_ids[:4] == CAT['cards'][name]['token'])
                                if any(a < 2304 and a//576 in slots for a in candidates):
                                    p.core.attrition[name]['scored_opportunities'] += 1
                                    p.core.attrition[name]['selected'] += action < 2304 and action//576 in slots
                            if action < 2304: ch.submit(info, int(action), R.costs, R.builder)
                        else:
                            p.core.deadline_stats = dict(hit=False,fallback=False,completed=0,candidates=1) if deadline_seconds is not None else None
                    elapsed = time.monotonic()-wall0
                    latencies[actor].append(elapsed)
                    cpu_latencies[actor].append(time.process_time()-cpu0)
                    if deadline_seconds is not None:
                        stats=dict(p.core.deadline_stats)
                        overrun, delayed_ticks = apply_lateness(ch, waits, available_at, actor, b.tick, elapsed, deadline_seconds)
                        stats.update(unpruned_candidate_count=unpruned_count,own_elixir=float(info.own['elixir']) if 'elixir' in info.own else float(info.packet.observation.global_features[5])*10,fallback_action=int(fallback),threads=spec['threads'],coarse_horizon=spec['coarse_horizon'],default_source=spec['policy'],wall_overrun=overrun > 0, overrun_seconds=overrun, delayed_ticks=delayed_ticks, decision_tick=b.tick, action=int(action), wall_seconds=elapsed)
                        deadline_stats[actor].append(stats)
                # Snapshot serialization/selection is excluded from the honest decision timer.
                if capture_before is not None:
                    # Reconstruct eligibility and the root from independent copies,
                    # even when this live decision timed out before candidates/root.
                    # This extra excluded-game work cannot alter either live RNG.
                    from imitation.evaluation.d1 import model_packet
                    core=copy.copy(p.core);core.rng=np.random.default_rng()
                    core.rng.bit_generator.state=copy.deepcopy(capture_before['candidate_rng_state'])
                    core.info=info;core.costs=R.costs;core.pending=capture_before['pending']
                    core.opponent_elixir=policies[actor].opponent_elixir
                    proposals=() if cached is None else cached.propose(model_packet(reserved.packet,policies[actor].mask),policies[actor].player.last_d1)
                    corpus_candidates,corpus_mask=core.candidates(reserved.packet,[v['action'] for v in proposals])
                    if len([a for a in corpus_candidates if a!=2305])>1:
                        posterior=copy.deepcopy(capture_before['belief_before'])
                        posterior.update(info.tick,info.events,deadline=None)
                        sample_rng=np.random.default_rng();sample_rng.bit_generator.state=copy.deepcopy(capture_before['belief_rng_state'])
                        opponent=posterior.sample(sample_rng,deadline=None)
                        root_rng_state=copy.deepcopy(sample_rng.bit_generator.state)
                        root=R.root(info,opponent,sample_rng)
                        elixir=float(info.own['elixir']);legal=int(np.count_nonzero(corpus_mask[:2304]))
                        from corpus import stratum
                        row=dict(capture_before,id=f"{arm}/{seed}/{info.tick}",tier=arm.split('-')[0],seed=seed,info=copy.deepcopy(info),reserved_packet=copy.deepcopy(reserved.packet),opponent_elixir=core.opponent_elixir,d1=copy.deepcopy(policies[actor].player.last_d1),root_rng_state=root_rng_state,root=root.snapshot(),root_digest=root.digest(),opponent=copy.deepcopy(opponent),strata=dict(elixir=elixir,legal_play_count=legal,bins=list(stratum(elixir,legal))))
                        capture.add(row,deadline_cut=bool(p.core.deadline_stats['hit']))
        b.step()
    if capture is not None: capture.dump(Path(OPTIONS['out'])/'capture.pkl.gz')
    for player in players.values(): player.core.close()
    recorder.__exit__(None,None,None)
    terminal = b.game_over
    loss = None if not terminal else float(b.winner is not None and b.winner != seat)
    ident = f'{population}-{pair:04d}-d27-{arm}'
    game = Game(ident, f'sim-{pair:04d}', 'search_d27', 'exploration',
        archetype(own)+' vs '+archetype(other), own, loss, np.asarray(ticks), np.asarray(globals_),
        np.asarray(hands), np.asarray(offsets), np.concatenate(entities), np.concatenate(ids), plays,
        dict(study='T1 confirmatory; SEALED',population=population,cell=cell,seed_index=pair,seed=seed, seat=seat, style='baseline-search', terminal=terminal, winner=b.winner,
             delay_ticks=27, opponent_delay=27, own_deck=own, opponent_deck=other,
             channel=channels[seat].diagnostics(), opponent_channel=channels[1-seat].diagnostics(),
             threads=spec['threads'], coarse_horizon=spec['coarse_horizon'], default_source=spec['policy']+'-if-no-complete-score', kernel=spec['kernel'],checkpoint_sha256=cfg['student']['checkpoint_sha256'] if spec['policy']=='R3a-cached' else cfg['policy']['checkpoint_sha256'], ticks_per_second=20, honest_lateness=True, belief_preparation='exact resumable4096-row cancellation', cyclic_gc='automatic collection deferred during decisions; maintenance metered',
             arm=arm, abilities='disabled both sides', opponent=spec['opponent'], deadline_seconds=deadline_seconds, reserve_floor=spec.get('reserve_floor',False),
             fair_information='public observation + own HUD + accepted enemy events; independent sampled hidden states/RNG'),
        np.asarray(queues))
    result = extract(game, CAT)
    core = players[seat].core
    result.update(cohort=arm, wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu)
    result['search_ab'] = dict(gc_maintenance=[dict(seconds=duration,generation=generation,during_decision=active) for duration,generation,active in WINDOW.events],latency_seconds=latencies[seat], raw_wall_latency_seconds=latencies[seat],
        cpu_latency_seconds=cpu_latencies[seat], attrition={k: dict(v) for k, v in core.attrition.items()},
        wait_counts=core.wait_counts, opponent_latency_seconds=latencies[1-seat],
        policy_cache_counts=None if cached is None else dict(forward=cached.forward_calls,fallback=cached.fallback_calls,proposer=cached.proposal_calls),decision_scope='public observation + charged single inference fallback/proposer + belief + candidates + public root + complete-root scoring + submission',
        deadline_stats=deadline_stats[seat], opponent_deadline_stats=deadline_stats[1-seat],
        floor_removed=core.floor_removed, policy_polls={a:policies[a].polls for a in (0,1)},
        command_sha256=command_hash.hexdigest(),
        worker_affinity=sorted(os.sched_getaffinity(0)), host=socket.gethostname(), worker_pid=os.getpid(), worker_pgid=os.getpgrp(), nice=os.getpriority(os.PRIO_PROCESS,0), scheduler=os.sched_getscheduler(0))
    result['wall_seconds']=time.perf_counter()-start
    result['cpu_seconds']=time.process_time()-cpu
    write(Path(OPTIONS['out'])/'games'/f'{ident}.json', result)
    print(json.dumps(dict(game=ident, terminal=terminal,
                          cpu=result['cpu_seconds'], wall=result['wall_seconds'])), flush=True)
    return dict(game=ident, terminal=terminal, cpu=result['cpu_seconds'])


def main():
    global OPTIONS,SLOT_CORES
    from common import plan,read,write,sha,job,utc
    from schedule import ARMS
    ap=argparse.ArgumentParser();ap.add_argument('--block',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cores',required=True);ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    cfg=plan();desc=read(a.block);j=job();host=socket.gethostname()
    assert host in cfg['compute']['hosts']
    if not a.smoke:
        from barrier import reporting_release
        reporting_release(ROOT,j/'FROZEN-T1.json',j/'REPORTING-AUTHORIZATION.json')
        assert (j/'SMOKE-PASS').exists()
    else:assert desc['population']=='smoke'
    SLOT_CORES=list(map(int,a.cores.split(',')));assert len(SLOT_CORES)==5 and len(set(SLOT_CORES))==5
    assert set(SLOT_CORES)<=set(cfg['compute']['hosts'][host]['physical_cpus'])
    assert os.sched_getaffinity(0)==set(SLOT_CORES)
    assert os.sched_getscheduler(0)==os.SCHED_OTHER and os.getpriority(os.PRIO_PROCESS,0)==10
    assert set(desc['order'])==set(ARMS) and len(desc['order'])==8
    assert not a.out.exists(),'never reuse an interrupted block directory'
    a.out.mkdir(parents=True);os.chmod(a.out,0o700)
    OPTIONS=dict(out=str(a.out),max_ticks=cfg['max_ticks'],arms=cfg['arms'],return_reserve_seconds=cfg['return_reserve_seconds'])
    native=initialize();assert sha(native)==cfg['source_reference']['native_sha256']
    decks=read(Path(__file__).parent/'guard-decks.json')
    own=decks['primary'][desc['own_index']] if desc['population'] in ('primary','smoke') else decks['l2'][desc['own_index']]
    other=decks['primary'][desc['opponent_index']] if desc['population'] in ('primary','smoke') else decks['guard'][desc['opponent_index']]['cards'] if desc['population']=='guard' else decks['l2'][desc['opponent_index']]
    write(a.out/'descriptor.json',desc)
    results=[];started=time.monotonic()
    for arm in desc['order']:
        assert not (j/'STOP').exists() and not (j/f'STOP-{host}').exists(),'owned stop file'
        results.append(run_game((desc['index'],desc['seed'],arm,own,other,desc['seat'],desc['population'],desc['cell'])))
    assert all(r['terminal'] for r in results)
    proof=dict(utc=utc(),descriptor=desc,host=host,slot_cores=SLOT_CORES,worker_pid=os.getpid(),worker_pgid=os.getpgrp(),wall_seconds=time.monotonic()-started,cpu_seconds=sum(r['cpu'] for r in results),games={r['game']+'.json':sha(a.out/'games'/(r['game']+'.json')) for r in results})
    write(a.out/'local-complete.json',proof)
    print(json.dumps(dict(block=desc['id'],complete_games=8,wall_seconds=proof['wall_seconds'])),flush=True)

if __name__ == '__main__':main()
