"""Resumable C56 search differential. Outputs are development evidence only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import clasher_core
import numpy as np
from c56_controller import CARDS, resources
from differential import config, snapshot, battle_digest
from stage2_matches import battle
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, C56SearchConfig
from clasher.rl.reward_model import potential_breakdown_p0
from dataclasses import astuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def fingerprint():
    paths = [*Path('src/clasher').rglob('*.py'), *Path('engine-rs/src').glob('*.rs'),
             *Path('engine-rs').glob('*.py'), Path(clasher_core.__file__), Path('gamedata.json'), Path(__file__)]
    return hashlib.sha256(b''.join(str(p).encode()+p.read_bytes() for p in sorted(paths))).hexdigest()


def check(b, seat, builder, bots, scripts, cfg, index, search_cfg):
    planners = [C56RolloutPlanner(builder, bots, backend=backend, seed=880000+index,
                    native=scripts, native_config=cfg, config=search_cfg) for backend in ('python','native')]
    packet = builder.build_public(b, seat)
    ca, mask = planners[0].candidates(packet)
    cb, _ = planners[1].candidates(packet)
    assert ca == cb
    native = planners[1].import_root(b)
    pp = list(astuple(potential_breakdown_p0(b)))
    rp = scripts.evaluation_parts(native)
    assert pp == rp, ('root leaf', b.tick, [(i, x.hex(),y.hex()) for i,(x,y) in enumerate(zip(pp,rp)) if x!=y])
    results = []
    for planner, root in zip(planners,(b,native)):
        start=time.perf_counter()
        a=planner.score_candidates(root, seat, ca, trace=True)
        results.append((a, planner.last, time.perf_counter()-start))
    a,p,pt=results[0]; c,n,nt=results[1]
    if (a,p)!=(c,n):
        write(HERE/'first_difference.json', dict(index=index,tick=b.tick,seat=seat,python=p,native=n,actions=[a,c]))
        for x,y in zip(p['traces'],n['traces']):
            if x!=y:
                raise AssertionError(('rollout mismatch',index,b.tick,x[:2],x[2][0].hex(),y[2][0].hex(),x[2][1:4],y[2][1:4],x[2][5],y[2][5]))
        raise AssertionError(('decision mismatch',index,a,c))
    return dict(index=index,tick=b.tick,seat=seat,candidates=len(ca),ability_candidate=2305 in ca,
                action=a,rollouts=len(p['traces']),ticks=sum(x[2][1] for x in p['traces']),
                continuation_actions=sum(len(x[2][4]) for x in p['traces']),
                trace_sha256=hashlib.sha256(repr(p).encode()).hexdigest(), python_wall=pt,native_wall=nt)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--roots',type=int,default=200);ap.add_argument('--samples',type=int,default=16);ap.add_argument('--output',type=Path,default=HERE/'parity.json');args=ap.parse_args()
    builder,_,scripts,bots=resources();cfg=config(CARDS)
    search_cfg=C56SearchConfig(samples=args.samples)
    pin=fingerprint()
    out=dict(fingerprint=pin,driver='qualify.py',config=vars(search_cfg),results=[],complete=False,pid=os.getpid())
    if args.output.exists():
        out=json.loads(args.output.read_text());assert out['fingerprint']==pin;assert out['config']==vars(search_cfg)
    plan=json.loads((HERE.parent/'stage4/c56_human64_plan.json').read_text())
    episodes=plan.get('episodes',plan.get('cases',plan.get('games')))
    if episodes is None:
        raise ValueError(list(plan))
    episodes = [episodes[i] for j in range(16) for i in range(j, len(episodes), 16)]
    index=0
    for ep in episodes:
        b=battle(ep,builder.loader)
        accepted=0
        while not b.game_over and b.tick<3001:
            if b.tick>=200 and b.tick%100==0 and accepted<4:
                seat=index%2
                from clasher.rl.public_action_mask import PublicActionMaskInput
                packet=builder.build_public(b,seat)
                mask=bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
                if not np.any(mask[:2304]) and not mask[2305]:
                    b.step()
                    continue
                accepted+=1
                if index>=len(out['results']):
                    row=check(b,seat,builder,bots,scripts,cfg,index,search_cfg)
                    out['results'].append(row);write(args.output,out);print(json.dumps(row),flush=True)
                index+=1
                if index>=args.roots:
                    out['complete']=True;write(args.output,out);return
            if b.tick>=90 and b.tick%5==0:
                moves=[bots[ep['styles'][seat]].select_action(builder.build_public(b,seat)) for seat in (0,1)]
                for seat,a in enumerate(moves):
                    # Engine/script behaviour is unchanged. The driver also exercises
                    # accepted ability actions on these development trajectories.
                    if b.can_activate_champion_ability(seat) and b.tick%100==0:
                        a=2305
                    plannerspace.apply_action(b,seat,a)
            b.step()
    raise AssertionError(('insufficient roots',index))

if __name__=='__main__':
    from clasher.rl.action_space import DiscreteTileActionSpace
    plannerspace=DiscreteTileActionSpace()
    main()
