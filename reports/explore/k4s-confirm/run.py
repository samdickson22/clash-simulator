"""PREREG-K4S runner: T1 frozen reporting runner (ef4c073a) plus reviewed deltas.

Deltas vs T1 run.py (see DELTA-MANIFEST.json): cell table and per-arm poll charge (r3 §2.4),
K4/K4S kernels on anchor_x with the SD1 seat poll, coarse order and cutoff default (§2.3),
8/10-arm rotated blocks (§3.1), SD1 manifest check, per-decision fields (§3.6).
The T1 corpus-capture path is removed (K4S reuses T1's frozen K4 corpus).
"""
import argparse
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
SD1_MANIFEST_SHA256 = None
GUARD_DECKS_SHA256 = '6d51628bb1262f53258e88ef6247cfb41f2762f9f13323387fcd36ad126c48ef'


def initialize():
    global R, CAT, PRIOR, POLICY, STUDENT, SD1_MANIFEST_SHA256
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
    from common import job
    cfg = json.loads((Path(__file__).parent/'plan.json').read_text())
    from sd1_manifest import check as check_sd1
    SD1_MANIFEST_SHA256 = check_sd1(job(), cfg)  # refuses to start on any SD1 manifest mismatch (r3 §2.1)
    checkpoint = job()/cfg['policy']['checkpoint']
    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == cfg['policy']['checkpoint_sha256']
    POLICY = load_policy(checkpoint)
    assert hashlib.sha256((job()/cfg['student']['calibration']).read_bytes()).hexdigest()==cfg['student']['calibration_sha256']
    assert POLICY.model.temperatures.tolist() == [1.,1.,1.]
    from proposals import load_student
    ck=job()/cfg['student']['checkpoint']
    assert hashlib.sha256(ck.read_bytes()).hexdigest()==cfg['student']['checkpoint_sha256']
    STUDENT=load_student(ck,cfg['student']['threshold'])
    return clasher_core.__file__


def make_player(seed, arm, reserve_floor=False, search_threads=1, coarse_horizon=160,kernel="coarse-first"):
    from fair_player import PublicPlanner
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    if kernel=="K4-anytime":
        from anchor_x import planner_class
    else:
        assert kernel=="K4-anytime-sdefault"
        from sdefault import planner_class
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
    from charge import make_charger
    pair, seed, arm, own, other, seat, population, cell, placement = case
    spec = OPTIONS['arms'][arm]
    assert spec['scale_mode'] == 'poll' and abs(spec['inference_scale']-200/spec['budget_ms']) < 1e-12
    assert spec.get('qualification_only') or spec['deadline_seconds'] is None or spec['deadline_seconds'] == spec['budget_ms']/1000
    charge, sleep_total = make_charger(spec['inference_scale'])
    sdefault_arm = spec['kernel'] == 'K4-anytime-sdefault'
    assert sdefault_arm == (spec['policy'] == 'SD1-cached')
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
    cfg=json.loads((Path(__file__).parent/'plan.json').read_text())
    cached=None
    # Stack assertion binds every real forward to this game's active GC/timer scope.
    def inference_check():
        frame=sys._getframe(1)
        while frame is not None and frame.f_code is not run_game.__code__:frame=frame.f_back
        assert frame is not None and 'wall0' in frame.f_locals
        assert time.monotonic()>=frame.f_locals['wall0'] and WINDOW.active
    if spec['policy']!='v1-unmodified':
        from sd1_policy import SD1Policy
        cached=SD1Policy(STUDENT,cfg['student']['threshold'],inference_check)
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
            j=Path(os.environ.get('K4S_JOB','/mpac/sdicks02/jobs/clasher/k4s-confirm-r1'))
            if (j/'STOP').exists() or (j/f'STOP-{socket.gethostname()}').exists():raise InterruptedError('owned K4S stop')
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
                with WINDOW:
                    wall0, cpu0 = time.monotonic(), time.process_time()
                    info = observe(b, R.builder, actor, public_events[actor])
                    reserved = ch.own_packet(info, R.builder)
                    poll0 = time.monotonic()
                    fallback = int(policies[actor].poll(b.tick,reserved.packet,recorder.public_events))
                    poll_seconds = time.monotonic()-poll0
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
                    # r3 §2.4: charge the seat poll at (1/c - 1) inside the timer, in every arm.
                    slept = charge(poll_seconds)
                    sd1_default = sd1_p_play = coarse_order_sha = None
                    if cached is not None:
                        sd1_default, sd1_p_play = cached.last_default, cached.last_p_play
                        assert sd1_default == fallback
                    prep_seconds = None
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
                        if cached is not None:
                            from imitation.evaluation.d1 import model_packet
                            proposals=cached.propose(model_packet(reserved.packet,policies[actor].mask),policies[actor].player.last_d1)
                            # r3 §2.3 item 2: SD1's top-8 only reorders the coarse scan; the candidate set is unchanged.
                            p.core.coarse_order=tuple(v["action"] for v in proposals)
                            coarse_order_sha=hashlib.sha256(json.dumps(list(p.core.coarse_order)).encode()).hexdigest()
                        candidates, mask = p.core.candidates(reserved.packet,[])
                        candidates = [a for a in candidates if a != 2305]
                        unpruned_count = len(candidates)
                        action = 2304
                        if len(candidates) > 1:
                            if cutoff is not None and time.monotonic() >= cutoff:
                                action = fallback if fallback < 2305 else 2304
                                p.core.selected_wait_ticks = 0
                                p.core.deadline_stats = dict(hit=True,fallback=True,completed=0,candidates=len(candidates),preparation_cutoff='prescan')
                            else:
                                try:
                                    opponent = p.belief.sample(p.rng, deadline=cutoff)
                                except TimeoutError:
                                    action = fallback if fallback < 2305 else 2304
                                    p.core.selected_wait_ticks = 0
                                    p.core.deadline_stats = dict(hit=True,fallback=True,completed=0,candidates=len(candidates),preparation_cutoff='sample')
                                else:
                                    root = R.root(info, opponent, p.rng)
                                    prep_seconds = time.monotonic()-wall0
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
                    cpu_elapsed = time.process_time()-cpu0
                    cpu_latencies[actor].append(cpu_elapsed)
                    if deadline_seconds is not None:
                        stats=dict(p.core.deadline_stats)
                        scored = prep_seconds is not None
                        if not scored:
                            prep_seconds = elapsed  # no scoring call: the whole decision was preparation
                        if 'student_default' not in stats:
                            if scored:
                                # Plain K4 scored decision: the frozen collector's own action.
                                stats['student_default'] = False
                                stats['frozen_action'] = int(action)
                            else:
                                # No scoring call (preparation cutoff or single candidate): no frozen scoring decision.
                                # Preparation cutoffs return the seat poll, which is the SD1 default in K4S.
                                stats['student_default'] = bool(sdefault_arm and stats['fallback'] and action < 2304)
                                stats['frozen_action'] = None
                        overrun, delayed_ticks = apply_lateness(ch, waits, available_at, actor, b.tick, elapsed, deadline_seconds)
                        stats.update(unpruned_candidate_count=unpruned_count,own_elixir=float(info.own['elixir']) if 'elixir' in info.own else float(info.packet.observation.global_features[5])*10,fallback_action=int(fallback),threads=spec['threads'],coarse_horizon=spec['coarse_horizon'],default_source=spec['default_source'],wall_overrun=overrun > 0, overrun_seconds=overrun, delayed_ticks=delayed_ticks, decision_tick=b.tick, action=int(action), wall_seconds=elapsed,
                                     cpu_seconds=cpu_elapsed, chosen_action=int(action), fallback_used=bool(stats['fallback']), selected_wait_ticks=p.core.selected_wait_ticks,
                                     sd1_default_action=sd1_default, sd1_p_play=sd1_p_play, coarse_order_sha256=coarse_order_sha,
                                     poll_seconds=poll_seconds, scale_sleep_seconds=slept, prep_seconds=prep_seconds, scored=scored,
                                     positive_overrun_ms=1000*overrun, charged_extra_ticks=delayed_ticks)
                        for key in ('coarse_complete','coarse_scored','plays'):stats.setdefault(key,None)
                        deadline_stats[actor].append(stats)
        b.step()
    for player in players.values(): player.core.close()
    recorder.__exit__(None,None,None)
    terminal = b.game_over
    loss = None if not terminal else float(b.winner is not None and b.winner != seat)
    ident = f'{population}-{pair:04d}-d27-{arm}'
    from common import job
    j = job()
    freeze_sha = hashlib.sha256((j/'FROZEN-K4S.json').read_bytes()).hexdigest() if (j/'FROZEN-K4S.json').exists() else None
    pin_sha = hashlib.sha256((j/'runtime-pin.json').read_bytes()).hexdigest() if (j/'runtime-pin.json').exists() else None
    game = Game(ident, f'sim-{pair:04d}', 'search_d27', 'exploration',
        archetype(own)+' vs '+archetype(other), own, loss, np.asarray(ticks), np.asarray(globals_),
        np.asarray(hands), np.asarray(offsets), np.concatenate(entities), np.concatenate(ids), plays,
        dict(study='PREREG-K4S confirmatory; SEALED',population=population,cell=cell,seed_index=pair,seed=seed, seat=seat, style='baseline-search', terminal=terminal, winner=b.winner,
             delay_ticks=27, opponent_delay=27, own_deck=own, opponent_deck=other,
             channel=channels[seat].diagnostics(), opponent_channel=channels[1-seat].diagnostics(),
             threads=spec['threads'], coarse_horizon=spec['coarse_horizon'], default_source=spec['default_source'], s_default_rule=spec['s_default_rule'], kernel=spec['kernel'],
             speed_cell=spec['speed_cell'], budget_ms=spec['budget_ms'], reserve_ms=round(1000*OPTIONS['return_reserve_seconds']), inference_scale=spec['inference_scale'], scale_mode=spec['scale_mode'],
             c_star=cfg['c_star'], freeze_manifest_sha256=freeze_sha, runtime_pin_sha256=pin_sha,
             sd1_manifest_sha256=SD1_MANIFEST_SHA256, sd1_checkpoint_sha256=cfg['student']['checkpoint_sha256'], sd1_calibration_sha256=cfg['student']['calibration_sha256'], sd1_threshold=cfg['student']['threshold'],
             opponent_checkpoint_sha256=cfg['policy']['checkpoint_sha256'], native_sha256=cfg['source_reference']['native_sha256'],
             rotation=placement['rotation'], block_id=placement['block_id'], replacement_k=placement['replacement_k'],
             slot=SLOT_CORES[0]//5, slot_cores=list(SLOT_CORES), attempt_dir=str(OPTIONS['out']),
             final_tick=b.tick, crowns=[b.players[seat].get_crown_count(), b.players[1-seat].get_crown_count()], draw=terminal and b.winner is None,
             scale_sleep_seconds=sleep_total[0], scale_sleeps=sleep_total[1],
             checkpoint_sha256=cfg['student']['checkpoint_sha256'] if sdefault_arm else cfg['policy']['checkpoint_sha256'], ticks_per_second=20, honest_lateness=True, belief_preparation='exact resumable4096-row cancellation', cyclic_gc='automatic collection deferred during decisions; maintenance metered',
             arm=arm, abilities='disabled both sides', opponent=spec['opponent'], deadline_seconds=deadline_seconds, reserve_floor=spec.get('reserve_floor',False),
             fair_information='public observation + own HUD + accepted enemy events; independent sampled hidden states/RNG'),
        np.asarray(queues))
    result = extract(game, CAT)
    core = players[seat].core
    result.update(cohort=arm, wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu)
    result['search_ab'] = dict(gc_maintenance=[dict(seconds=duration,generation=generation,during_decision=active) for duration,generation,active in WINDOW.events],latency_seconds=latencies[seat], raw_wall_latency_seconds=latencies[seat],
        cpu_latency_seconds=cpu_latencies[seat], attrition={k: dict(v) for k, v in core.attrition.items()},
        wait_counts=core.wait_counts, opponent_latency_seconds=latencies[1-seat],
        policy_cache_counts=None if cached is None else dict(forward=cached.forward_calls,fallback=cached.fallback_calls,proposer=cached.proposal_calls),decision_scope='public observation + charged single inference poll + (1/c-1) poll charge + belief + candidates + public root + complete-root scoring + submission',
        deadline_stats=deadline_stats[seat], opponent_deadline_stats=deadline_stats[1-seat],
        floor_removed=core.floor_removed, policy_polls={a:policies[a].polls for a in (0,1)},
        command_sha256=command_hash.hexdigest(),
        worker_affinity=sorted(os.sched_getaffinity(0)), host=socket.gethostname(), worker_pid=os.getpid(), worker_pgid=os.getpgrp(), nice=os.getpriority(os.PRIO_PROCESS,0), scheduler=os.sched_getscheduler(0))
    result['wall_seconds']=time.perf_counter()-start
    result['cpu_seconds']=time.process_time()-cpu
    write(Path(OPTIONS['out'])/'games'/f'{ident}.json', result)
    print(json.dumps(dict(game=ident, terminal=terminal)), flush=True)
    return dict(game=ident, terminal=terminal, cpu=result['cpu_seconds'])


def main():
    global OPTIONS,SLOT_CORES
    from common import plan,read,write,sha,job,utc
    from schedule import expected_order
    ap=argparse.ArgumentParser();ap.add_argument('--block',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--cores',required=True);ap.add_argument('--smoke',action='store_true');ap.add_argument('--qualification',action='store_true');a=ap.parse_args()
    cfg=plan();desc=read(a.block);j=job();host=socket.gethostname()
    assert host in cfg['compute']['hosts']
    assert not (a.smoke and a.qualification)
    if a.smoke:assert desc['population']=='smoke'
    elif a.qualification:assert desc['population']=='qualification'
    else:
        from barrier import reporting_release
        reporting_release(ROOT,j/'FROZEN-K4S.json',j/'REPORTING-AUTHORIZATION.json')
        assert (j/'SMOKE-PASS').exists() and desc['population'] in ('primary','guard')
    SLOT_CORES=list(map(int,a.cores.split(',')));assert len(SLOT_CORES)==5 and len(set(SLOT_CORES))==5
    assert set(SLOT_CORES)<=set(cfg['compute']['hosts'][host]['physical_cpus'])
    assert os.sched_getaffinity(0)==set(SLOT_CORES)
    # Reporting and smoke run at T1's nice 10; qualification may run at nice 19 (shared-host courtesy).
    prio=os.getpriority(os.PRIO_PROCESS,0)
    assert os.sched_getscheduler(0)==os.SCHED_OTHER and (prio==10 or (a.qualification and prio==19))
    if desc['population']!='qualification':
        from schedule import canonical
        canonical(desc)  # every field equals the frozen schedule (rotation, seed, cell, decks, order, replacement bank)
    assert desc['order']==expected_order(desc),'block order must be the frozen rotation/subsample order'
    assert not a.out.exists(),'never reuse an interrupted block directory'
    a.out.mkdir(parents=True);os.chmod(a.out,0o700)
    OPTIONS=dict(out=str(a.out),max_ticks=cfg['max_ticks'],arms=cfg['arms'],return_reserve_seconds=cfg['return_reserve_seconds'])
    native=initialize();assert sha(native)==cfg['source_reference']['native_sha256']
    decks=read(Path(__file__).parent/'guard-decks.json')
    assert hashlib.sha256((Path(__file__).parent/'guard-decks.json').read_bytes()).hexdigest()==GUARD_DECKS_SHA256
    primary_like=desc['population'] in ('primary','smoke') or (desc['population']=='qualification' and desc['qualification_population']=='primary')
    own=decks['primary'][desc['own_index']] if primary_like else decks['l2'][desc['own_index']]
    other=decks['primary'][desc['opponent_index']] if primary_like else decks['guard'][desc['opponent_index']]['cards']
    write(a.out/'descriptor.json',desc)
    placement=dict(rotation=desc['rotation'],block_id=desc['id'],replacement_k=desc.get('replacement_k'))
    results=[];started=time.monotonic()
    for arm in desc['order']:
        assert not (j/'STOP').exists() and not (j/f'STOP-{host}').exists(),'owned stop file'
        results.append(run_game((desc['index'],desc['seed'],arm,own,other,desc['seat'],desc['population'],desc['cell'],placement)))
    assert all(r['terminal'] for r in results)
    proof=dict(utc=utc(),descriptor=desc,host=host,slot_cores=SLOT_CORES,worker_pid=os.getpid(),worker_pgid=os.getpgrp(),wall_seconds=time.monotonic()-started,cpu_seconds=sum(r['cpu'] for r in results),games={r['game']+'.json':sha(a.out/'games'/(r['game']+'.json')) for r in results})
    write(a.out/'local-complete.json',proof)
    print(json.dumps(dict(block=desc['id'],complete_games=len(results),wall_seconds=proof['wall_seconds'])),flush=True)

if __name__ == '__main__':main()
