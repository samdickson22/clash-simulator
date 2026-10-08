"""Full terminal games, timings and exact recorded-stream D1 skew receipts.

Synthetic results intentionally omit winners/scores. Accepted actions and public
streams are retained for deterministic replays; timing includes all serving work.
"""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import time
import numpy as np
import torch
from .paths import setup, COUNCIL
from .snapshot import provenance
setup()
from fair_player import Resources, observe
from deadline_player import DeadlinePublicPlanner
from derived_public_state import PublicEvent as SearchEvent
from stage2_matches import battle
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.public_action_mask import PublicActionMaskInput
from sidecar_observer import SidecarObserver
from imitation.model import load_policy
from imitation.model.features import build_row
from .search import ImitationDeadlinePlayer, MatchedDeadlinePlayer
from .standalone import StandalonePlayer
from .d1 import model_packet


def write_new(path, value):
    with open(path, 'x') as f:
        json.dump(value, f, sort_keys=True)
        f.write('\n')


def equality(a, b):
    assert set(a) == set(b), (set(a), set(b))
    for key in a:
        aa, bb = np.asarray(a[key]), np.asarray(b[key])
        assert aa.dtype == bb.dtype and aa.shape == bb.shape and aa.tobytes() == bb.tobytes(), key


def play(r, prior, policy, ep, seat, *, search=True, skew=False, arm="B", head_to_head=False, plumbing_only=True):
    b = battle(dict(seed=ep['seed'], decks=ep['decks']), r.builder.loader)
    own = b.players[seat]
    order = list(own.hand)+list(own.cycle_queue)
    player = (ImitationDeadlinePlayer(r, prior, ep['seed']+100000+seat, policy, seat, order)
              if search else StandalonePlayer(policy, r.builder, r.costs, seat, order, ep['seed']+271828+seat))
    baseline = MatchedDeadlinePlayer(r, prior, ep['seed']+100000+(1-seat)) if head_to_head else None
    if search and arm == 'A':
        player = MatchedDeadlinePlayer(r, prior, ep['seed']+100000+seat)
    space = DiscreteTileActionSpace()
    times, proposal_times, actions = [], [], []
    baseline_times = []
    rejected = [0, 0]
    illegal = [0, 0]
    checks = 0
    # Warm CPU kernels with this public opening state; reconstruct player after.
    opening = r.builder.build_public(b, seat)
    mask = r.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(opening))
    if not search or arm == 'B':
        d = player.d1.update(0, [])
        policy.propose(model_packet(opening, mask), d, 8)
    with SidecarObserver(r.builder) as sensor:
        sensor.audit_counters = {'opponent_elixir_topup_total': 0.}
        sensor(b, seat, None)
        while not b.game_over:
            if b.tick >= 90 and b.tick % 5 == 0:
                # Sidecar is the independent train path, evaluated outside timing.
                if skew:
                    sensor(b, seat, None)
                moves = {}
                for actor in (0, 1):
                    if actor != seat:
                        if baseline is None:
                            packet = r.builder.build_public(b, actor)
                            moves[actor] = int(r.bots[ep['style']].select_action(packet))
                        else:
                            start = time.perf_counter()
                            enemy_events = [SearchEvent(e['tick'],e['kind'],e['name'],e['amount'])
                                            for e in sensor.public_events if e['seat'] != actor]
                            info = observe(b,r.builder,actor,enemy_events)
                            moves[actor], _ = baseline.decide(info,(b.tick-90)//5,deadline=start+.2)
                            baseline_times.append((time.perf_counter()-start)*1000)
                        continue
                    start = time.perf_counter()
                    if search:
                        enemy_events = [SearchEvent(e['tick'], e['kind'], e['name'], e['amount'])
                                        for e in sensor.public_events if e['seat'] != seat]
                        info = observe(b, r.builder, seat, enemy_events)
                        kwargs = {'public_events':sensor.public_events} if arm == 'B' else {}
                        action, _ = player.decide(info, (b.tick-90)//5, deadline=start+.2, **kwargs)
                        proposal_times.append(player.proposal_ms if arm == 'B' else 0.)
                    else:
                        packet = r.builder.build_public(b, seat)
                        action, _ = player.decide(b.tick, packet, sensor.public_events)
                    times.append((time.perf_counter()-start)*1000)
                    moves[actor] = int(action)
                    if skew:
                        equality(player.last_d1, sensor.rows[-1])
                        packet = r.builder.build_public(b, seat)
                        mask = r.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                        equality(build_row(model_packet(packet, mask), player.last_d1, policy.costs),
                                 build_row(model_packet(packet, mask), sensor.rows[-1], policy.costs))
                        checks += 1
                for actor in (0, 1):
                    packet = r.builder.build_public(b, actor)
                    mask = r.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                    action = moves[actor]
                    illegal[actor] += int(not mask[action])
                    if action == 2304:
                        continue
                    ok = space.apply_action(b, actor, action)
                    rejected[actor] += int(not ok)
                    actions.append([b.tick, actor, action, bool(ok)])
            b.step()
    result = dict(plumbing_only=plumbing_only, seed=ep['seed'], seat=seat, decks=ep['decks'],
                arm=arm, baseline_timings_ms=baseline_times,
                style=ep['style'], terminal=b.game_over, ticks=b.tick, actions=actions,
                public_events=sensor.public_events, timings_ms=times, proposal_ms=proposal_times,
                illegal=illegal, rejected=rejected, skew_checks=checks,
                host={'name': os.uname().nodename, 'load': os.getloadavg(),
                      'nice': os.getpriority(os.PRIO_PROCESS, 0), 'threads': 2 if search else 1})
    if not plumbing_only:
        result.update(winner=b.winner, score=.5 if b.winner is None else float(b.winner==seat))
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--prior', type=Path, default=COUNCIL/'c56/engine/root-v3/human_deck_catalog.json')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--games', type=int, default=20)
    p.add_argument('--worker', type=int, default=0)
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--seed', type=int, default=68175001)
    p.add_argument('--standalone', action='store_true')
    p.add_argument('--skew-games', type=int, default=8)
    args = p.parse_args()
    source_pin=provenance()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    policy = load_policy(args.checkpoint)
    checkpoint_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    r = Resources()
    prior = json.loads(args.prior.read_text())
    source_pin['prior_sha256']=hashlib.sha256(args.prior.read_bytes()).hexdigest()
    if args.standalone:
        from decks import catalogs
        chosen = sorted(catalogs()['eval']['decks'], key=lambda d: -d['frequency'])
    else:
        chosen = sorted(prior['decks'], key=lambda d: -d['frequency'])
    opponent_chosen = sorted(prior['decks'], key=lambda d: -d['frequency'])
    args.output.mkdir(parents=True, exist_ok=True)
    for i in range(args.games):
        if i % args.workers != args.worker:
            continue
        path = args.output/f'game-{i:03d}.json'
        if path.exists():
            row = json.loads(path.read_text())
            assert row['checkpoint_sha256'] == checkpoint_sha and row['terminal']
            continue
        rng = np.random.default_rng(args.seed+i*1009)
        ep = dict(seed=args.seed+i*1009, style=('balanced','pressure','defense')[i%3],
                  decks=[rng.permutation(chosen[i % len(chosen)]['cards']).tolist(),
                         rng.permutation(opponent_chosen[(i+3) % len(opponent_chosen)]['cards']).tolist()])
        if args.standalone and i%2:
            ep['decks'].reverse()  # Keep eval-role deck with the candidate in either seat.
        row = play(r, prior, policy, ep, i%2, search=not args.standalone, skew=i<args.skew_games)
        row['checkpoint_sha256'] = checkpoint_sha
        row.update(source_pin)
        write_new(path, row)
        print(json.dumps({k: row[k] for k in ('seed','terminal','ticks','illegal','rejected','skew_checks')}), flush=True)
        gc.collect()
    write_new(args.output/f'worker-{args.worker}-done.json', {'complete': True})


if __name__ == '__main__':
    main()
