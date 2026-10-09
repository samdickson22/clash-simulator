"""Paired search opponents using existing fair roots and delay-fixes channels."""
import argparse
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
R = CAT = PRIOR = OPTIONS = None


def initialize():
    global R, CAT, PRIOR
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
    return clasher_core.__file__


def make_player(seed, arm):
    from fair_player import PublicPlanner
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from planner import planner_class
    p = PublicPlanner(R, PRIOR, seed)
    p.core = planner_class(DelayAwarePlanner)(R.builder, R.bots, backend='native',
        seed=seed+1, native=R.native, native_config=R.config, catalog=CAT,
        config=C56SearchConfig(threads=1, horizon=320 if arm == 'H16' else 160,
                              wait_screen8=False),  # Frozen wrapper adds W itself.
        command_delay=27, delay_aware=True, symmetric_opponent=True,
        opponent_delay=27, opponent_interval=10, opponent_capacity=1,
        max_outstanding=1, arm='W' if arm == 'S8' else arm, variant='screen8' if arm == 'S8' else 'full')
    return p


def run_game(case):
    from fair_player import observe
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from clasher.analysis.loss_review.delay_fixes import CommandQueue
    from clasher.analysis.loss_review.metrics import Game, archetype, extract
    from clasher.analysis.loss_review.human import write
    from clasher.rl.public_observation import REAL_PLAY_ENTITY_FEATURE_INDICES
    pair, seed, arm, own, other = case
    seat = pair % 2
    start, cpu = time.perf_counter(), time.process_time()
    rng = random.Random(seed)
    own, other = list(own), list(other)
    rng.shuffle(own); rng.shuffle(other)
    b = battle(dict(seed=seed, decks=[own, other] if seat == 0 else [other, own]), R.builder.loader)
    players = {seat: make_player(seed+100000, 'W' if arm == 'WW' else arm),
               1-seat: make_player(seed+100002, 'W' if arm == 'WW' else '0')}
    channels = {a: CommandQueue(27, 1) for a in (0, 1)}
    waits = {0: 0, 1: 0}
    public_events = {0: [], 1: []}
    latencies = {a: [] for a in (0, 1)}
    cpu_latencies = {a: [] for a in (0, 1)}
    ticks, globals_, hands, queues, entities, ids, offsets, plays = [], [], [], [], [], [], [0], []
    cols = sorted(REAL_PLAY_ENTITY_FEATURE_INDICES)

    def act(actor, command):
        if b.players[actor].hand[command.action//576] != command.card:
            raise AssertionError('pending slot changed')
        core = players[actor].core
        choice = core.space.decode_action(command.action, actor)
        elixir = b.players[actor].elixir
        ok = core.space.apply_action(b, actor, command.action)
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
        if b.tick % 5 == 0:
            ob = R.builder.build_public(b, seat).observation
            ticks.append(b.tick); globals_.append(ob.global_features.copy()); hands.append(ob.hand_ids.copy())
            q = list(b.players[seat].cycle_queue)
            queues.append([R.builder.token_id(n, namespace='card_action') for n in q] + [0]*(8-len(q)))
            ef = ob.entity_features[ob.entity_mask][:, cols].copy()
            entities.append(ef); ids.append(ob.entity_ids[ob.entity_mask].copy()); offsets.append(offsets[-1]+len(ef))
        for actor in (0, 1): complete(actor)
        if b.tick >= 90 and b.tick % 10 == 0:
            # No physical mutation between these decisions: every command has d=27.
            for actor in (0, 1):
                ch, p = channels[actor], players[actor]
                if not ch.available or b.tick < waits[actor]:
                    ch.blocked += 1
                    continue
                wall0, cpu0 = time.perf_counter(), time.process_time()
                info = observe(b, R.builder, actor, public_events[actor])
                p.belief.update(info.tick, info.events)
                reserved = ch.own_packet(info, R.builder)
                p.core.info, p.core.costs, p.core.pending = info, R.costs, tuple(ch.pending)
                candidates, mask = p.core.candidates(reserved.packet)
                candidates = [a for a in candidates if a != 2305]
                if len(candidates) > 1:
                    root = R.root(info, p.belief.sample(p.rng), p.rng)
                    action = p.core.score_candidates(root, actor, candidates)
                    if p.core.selected_wait_ticks:
                        waits[actor] = b.tick + p.core.selected_wait_ticks
                    for name in p.core.attrition:
                        slots = np.flatnonzero(info.packet.observation.hand_ids[:4] == CAT['cards'][name]['token'])
                        if any(a < 2304 and a//576 in slots for a in candidates):
                            p.core.attrition[name]['scored_opportunities'] += 1
                            p.core.attrition[name]['selected'] += action < 2304 and action//576 in slots
                    if action < 2304: ch.submit(info, int(action), R.costs, R.builder)
                latencies[actor].append(time.perf_counter()-wall0)
                cpu_latencies[actor].append(time.process_time()-cpu0)
        b.step()
    terminal = b.game_over
    loss = None if not terminal else float(b.winner is not None and b.winner != seat)
    ident = f'sim-{pair:04d}-d27-{arm}'
    game = Game(ident, f'sim-{pair:04d}', 'search_d27', 'exploration',
        archetype(own)+' vs '+archetype(other), own, loss, np.asarray(ticks), np.asarray(globals_),
        np.asarray(hands), np.asarray(offsets), np.concatenate(entities), np.concatenate(ids), plays,
        dict(seed=seed, seat=seat, style='baseline-search', terminal=terminal, winner=b.winner,
             delay_ticks=27, opponent_delay=27, own_deck=own, opponent_deck=other,
             channel=channels[seat].diagnostics(), opponent_channel=channels[1-seat].diagnostics(),
             arm=arm, abilities='disabled both sides', opponent='baseline-search' if arm != 'WW' else 'W-search',
             fair_information='public observation + own HUD + accepted enemy events; independent sampled hidden states/RNG'),
        np.asarray(queues))
    result = extract(game, CAT)
    core = players[seat].core
    result.update(cohort=arm, wall_seconds=time.perf_counter()-start, cpu_seconds=time.process_time()-cpu)
    result['search_ab'] = dict(latency_seconds=latencies[seat], raw_wall_latency_seconds=latencies[seat],
        cpu_latency_seconds=cpu_latencies[seat], attrition={k: dict(v) for k, v in core.attrition.items()},
        wait_counts=core.wait_counts, opponent_latency_seconds=latencies[1-seat],
        decision_scope='public observation + belief + candidates + public root + full scoring + submission')
    write(Path(OPTIONS['out'])/'games'/f'{ident}.json', result)
    print(json.dumps(dict(game=ident, terminal=terminal, loss=loss, ticks=b.tick,
                          cpu=result['cpu_seconds'], wall=result['wall_seconds'])), flush=True)
    return dict(game=ident, terminal=terminal, cpu=result['cpu_seconds'])


def main():
    global OPTIONS
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=50)
    ap.add_argument('--pairs', type=int)
    ap.add_argument('--offset', type=int, default=0)
    ap.add_argument('--smoke', action='store_true')
    a = ap.parse_args()
    assert socket.gethostname() == '127x03' and 1 <= a.workers <= 50
    cfg = json.loads(a.config.read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    OPTIONS = dict(out=str(a.out), max_ticks=cfg['max_ticks'])
    native_path = initialize()
    from clasher.analysis.loss_review.metrics import archetype
    selected = [max((d for d in PRIOR['decks'] if archetype(d['cards']) == f),
                    key=lambda d: d['frequency'])['cards']
                for f in ('bridge_wincon', 'siege', 'beatdown', 'bait', 'chip')]
    count = a.pairs or cfg['paired_seeds']
    base = cfg['seed_ranges']['smoke' if a.smoke else 'reporting']['base']
    cases = [(i, base+i, arm, selected[i%5], selected[(i//5)%5])
             for i in range(a.offset, a.offset+count)
             for arm in cfg['arms'] + (['WW'] if i < cfg['ww_pairs'] and not a.smoke else [])]
    schedule = dict(config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(), cases=cases,
                    native_path=native_path, native_sha256=hashlib.sha256(Path(native_path).read_bytes()).hexdigest())
    path = a.out/'schedule.json'
    if path.exists():
        assert json.loads(path.read_text()) == json.loads(json.dumps(schedule))
    else: path.write_text(json.dumps(schedule)+'\n')
    pending = []
    for c in cases:
        f = a.out/'games'/f'sim-{c[0]:04d}-d27-{c[2]}.json'
        if f.exists():
            r = json.loads(f.read_text())
            assert r['metadata']['seed'] == c[1] and r['metadata']['terminal']
        else: pending.append(c)
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=multiprocessing.get_context('fork'),
                             initializer=pin_worker) as pool:
        results = list(pool.map(run_game, pending, chunksize=1))
    (a.out/'receipt.json').write_text(json.dumps(dict(games=len(cases), fresh=len(results),
        cpu_seconds=sum(r['cpu'] for r in results), wall_seconds=time.perf_counter()-start,
        terminal=all(r['terminal'] for r in results)))+'\n')


def pin_worker():
    # One physical core per worker; reserve 59 for builds and 60–63 for profiling.
    ident = multiprocessing.current_process()._identity[0]
    os.sched_setaffinity(0, {(ident-1) % 50})


if __name__ == '__main__': main()
