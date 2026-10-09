"""Freeze public decision states and verify the private WAIT extension."""
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import random
import sys
import time
import run


def capture(out, config):
    from fair_player import observe, PublicPlanner
    from stage2_matches import battle
    from derived_public_state import PublicEvent
    from clasher.analysis.loss_review.metrics import archetype
    from delay import DelayAwarePlanner
    from planner import legacy_class
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    r = run.R
    selected = [max((d for d in run.PRIOR['decks'] if archetype(d['cards']) == f),
                    key=lambda d: d['frequency'])['cards']
                for f in ('bridge_wincon', 'siege', 'beatdown', 'bait', 'chip')]
    rows = []
    for pair in range(config['seed_ranges']['latency']['count']):
        seed = config['seed_ranges']['latency']['base'] + pair
        rng = random.Random(seed)
        decks = [list(selected[pair%5]), list(selected[(pair//5)%5])]
        for deck in decks: rng.shuffle(deck)
        seat = pair % 2
        if seat: decks.reverse()
        b = battle(dict(seed=seed, decks=decks), r.builder.loader)
        p = PublicPlanner(r, run.PRIOR, seed+100000)
        core = legacy_class(DelayAwarePlanner)(r.builder, r.bots, backend='native',
            seed=seed+100001, native=r.native, native_config=r.config, catalog=run.CAT,
            config=C56SearchConfig(threads=1), command_delay=27, delay_aware=True)
        events = []
        while not b.game_over and b.tick <= max(config['latency']['capture_ticks']):
            if b.tick in config['latency']['capture_ticks']:
                info = observe(b, r.builder, seat, events)
                p.belief.update(info.tick, info.events)
                root = r.root(info, p.belief.sample(p.rng), p.rng)
                actions, _ = core.candidates(info.packet)
                actions = [a for a in actions if a != 2305]
                rows.append(dict(id=f'{pair}:{b.tick}:{seat}', info=info, root=root.snapshot(),
                                 root_digest=root.digest(), candidates=actions, seed=seed))
            if b.tick >= 90 and b.tick % 10 == 0:
                for actor in (0, 1):
                    action = int(r.bots[('balanced','pressure','defense')[(pair//5)%3]].select_action(
                        r.builder.build_public(b, actor)))
                    if action < 2304:
                        card = b.players[actor].hand[action//576]
                        if core.space.apply_action(b, actor, action) and actor != seat:
                            events.append(PublicEvent(b.tick, 'card', card))
            b.step()
        print(json.dumps(dict(capture_pair=pair, states=len(rows), tick=b.tick)), flush=True)
    out.mkdir(parents=True, exist_ok=True)
    path = out/'states.pkl'
    if path.exists(): raise ValueError('state corpus already exists')
    path.write_bytes(pickle.dumps(rows, protocol=5))
    meta = dict(count=len(rows), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                states=[dict(id=v['id'], seed=v['seed'], root_digest=v['root_digest'],
                             candidates=v['candidates'], elixir=v['info'].own['elixir']) for v in rows])
    (out/'state-manifest.json').write_text(json.dumps(meta, indent=2)+'\n')
    return rows


def reference(root, seat, action, style, horizon, trace=True):
    """Independent Python schedule for capacity-1 d27 channels, native combat."""
    sim = root.clone()
    origin = json.loads(sim.snapshot())['tick']
    wait = {2400:10,2401:20,2402:40}.get(action, 0)
    action = 2304 if wait else action
    queues = {0:[],1:[]}; events = []
    def submit(actor, action, tick):
        if action == 2304: return
        card = json.loads(sim.snapshot())['players'][actor]['hand'][action//576]
        queues[actor].append((origin+tick+27, action, card))
        if trace: events.append(('submit', origin+tick, actor, action, True, card))
    submit(seat, action, 0)
    submit(1-seat, run.R.native.select_action(sim, 1-seat, style), 0)
    for tick in range(horizon):
        if json.loads(sim.snapshot())['game_over']: break
        if tick > 0 and tick % 10 == 0:
            for actor in (seat,1-seat):
                if not queues[actor] and (actor != seat or tick >= wait):
                    submit(actor, run.R.native.select_action(sim, actor, 'balanced' if actor == seat else style), tick)
        for actor in (seat,1-seat):
            if queues[actor] and queues[actor][0][0] <= origin+tick:
                due, a, card = queues[actor].pop(0)
                ok = bool(run.R.native.apply_discrete(sim, actor, a))
                if trace: events.append(('execute', origin+tick, actor, a, ok, card))
        sim.step(1)
    return run.R.native.evaluate(sim, seat, 1.), events, sim


def verify(rows, out):
    import clasher_core
    from delay import DelayAwarePlanner
    from clasher.analysis.loss_review.tempo import planner_class as tempo_class
    from clasher.analysis.loss_review.search_ab import planner_class as audit_class
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from planner import legacy_class
    checks = []
    # Diverse early/late, both seats; all styles and all WAIT durations.
    selected = rows[::max(1,len(rows)//10)][:10]
    for row in selected:
        root = clasher_core.BattleState(row['root']); seat=row['info'].seat
        actions = [2304,2400,2401,2402] + [a for a in row['candidates'] if a < 2304][:2]
        for style in ('balanced','pressure','defense'):
            for a in actions:
                value, events, sim = run.R.native.rollout_commands(root,seat,a,[],style,
                    27,27,1,1,160,10,10,1.,True,False,True)
                v, ev, ref = reference(root,seat,a,style,160)
                assert value == v and events == ev and sim.digest() == ref.digest(), (row['id'], a, style)
                checks.append(dict(id=row['id'], action=a, style=style, score=value, digest=sim.digest()))
        kw = dict(backend='native',seed=11,native=run.R.native,native_config=run.R.config,
                  config=C56SearchConfig(threads=1),command_delay=27,delay_aware=True,catalog=run.CAT)
        old = tempo_class(audit_class(DelayAwarePlanner))(run.R.builder,run.R.bots,
                timed_waits=True,wait_prior=.01,**kw)
        new = legacy_class(DelayAwarePlanner)(run.R.builder,run.R.bots,**kw)
        for p in (old,new): p.info=row['info'];p.costs=run.R.costs
        a = old.score_candidates(root,seat,row['candidates'])
        b = new.score_candidates(root,seat,row['candidates'])
        assert a == b and old.last['scores'] == new.last['scores'], row['id']
        optimized = legacy_class(DelayAwarePlanner)(run.R.builder,run.R.bots,variant='native-full',**kw)
        optimized.info=row['info'];optimized.costs=run.R.costs
        c = optimized.score_candidates(root,seat,row['candidates'])
        assert a == c and old.last['scores'] == optimized.last['scores'], ('native-original-W',row['id'])
        assert root.digest() == row['root_digest']
    (out/'qualification.json').write_text(json.dumps(dict(passed=True, native_wait_checks=len(checks),
        original_W_exact_states=len(selected), native_original_W_exact_states=len(selected), checks=checks), indent=2)+'\n')
    print(json.dumps(dict(passed=True, native_wait_checks=len(checks), original_W_exact_states=len(selected))),flush=True)


def ordinary(rows, out):
    import clasher_core
    result=[]
    for row in rows[::max(1,len(rows)//10)][:10]:
        root=clasher_core.BattleState(row['root']);seat=row['info'].seat
        for style in ('balanced','pressure','defense'):
            for action in [2304]+[a for a in row['candidates'] if a < 2304][:3]:
                value,events,sim=run.R.native.rollout_commands(root,seat,action,[],style,
                    27,27,1,1,160,10,10,1.,True,False,True)
                result.append(dict(id=row['id'], action=action, style=style, value=value,
                                   events=events, digest=sim.digest()))
    (out/'ordinary.json').write_text(json.dumps(result)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--verify-only',action='store_true')
    p.add_argument('--ordinary-only',action='store_true');p.add_argument('--states',type=Path)
    a=p.parse_args();run.initialize();cfg=json.loads(a.config.read_text())
    if a.ordinary_only:
        a.out.mkdir(parents=True,exist_ok=True)
        ordinary(pickle.loads(a.states.read_bytes()),a.out)
        sys.exit(0)
    rows=pickle.loads((a.out/'states.pkl').read_bytes()) if a.verify_only else capture(a.out,cfg)
    verify(rows,a.out)
