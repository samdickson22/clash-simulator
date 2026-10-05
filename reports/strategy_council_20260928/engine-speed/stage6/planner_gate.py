"""Early-scope planner qualification on fresh replays of pinned group games."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import cloudpickle
import numpy as np
from clasher.rl.c56_rollout_planner import C56RolloutPlanner
from clasher.rl.public_action_mask import PublicActionMaskInput
from c56_controller import CARDS, verify
from controller import EARLY, resources
from differential import Position, config, battle_digest
from stage2 import fingerprint
from stage2_matches import battle
import clasher_core


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def native_candidates(planner, root, packet, seat):
    mask = planner.bots['balanced'].mask_builder.build(PublicActionMaskInput.from_confidence_observation(packet))
    ranked = planner.native.ranked_actions(root, seat, 'balanced')
    pool = np.flatnonzero(mask[:2304])
    samples = planner.rng.choice(pool, min(planner.config.samples, len(pool)), replace=False).tolist()
    proposals = [ranked[0][0], 2304] + [r[0] for r in ranked[:planner.config.script_top]]
    if mask[2305]: proposals.append(2305)
    proposals += samples
    return list(dict.fromkeys(int(a) for a in proposals if mask[int(a)])), mask


def main():
    p=argparse.ArgumentParser();p.add_argument('--games',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--calls',type=int,default=100)
    args=p.parse_args()
    native_path=Path(clasher_core.__file__).resolve()
    assert native_path.parent==Path(__file__).resolve().parent/'native'
    pins=dict(source=fingerprint(), native=hashlib.sha256(native_path.read_bytes()).hexdigest(),
              games=hashlib.sha256(args.games.read_bytes()).hexdigest(),
              drivers={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                       for n in ('planner_gate.py','controller.py')})
    out=dict(pins=pins,calls=args.calls,results={})
    if args.output.exists():
        old=json.loads(args.output.read_text());assert old['pins']==pins and old['calls']==args.calls;out=old
    builder,meta,scripts,bots=resources();cfg=config(tuple(dict.fromkeys((*CARDS,*EARLY))))
    records=json.loads(args.games.read_text())['results']
    count=0
    for game_id,rec in sorted(records.items(),key=lambda kv:int(kv[0])):
        assert rec['ok'] and rec['terminal']
        b=battle(rec['episode'],builder.loader);actions=defaultdict(list)
        for a in rec['actions']:actions[a[0]].append(a)
        times={i['tick'] for i in rec['imports']}
        while not b.game_over:
            for a in actions[b.tick]:
                assert b.deploy_card(a[1],a[3],Position(a[4],a[5]))==a[6]
            if b.tick in times and count<args.calls:
                seat=count%2;key=str(count);count+=1
                if not out['results'].get(key,{}).get('ok'):
                    py=C56RolloutPlanner(builder,bots,seed=662000+int(key))
                    native=C56RolloutPlanner(builder,bots,seed=662000+int(key),backend='native',native=scripts,native_config=cfg)
                    root=native.import_root(b)
                    public=verify(b,root,builder,scripts,bots,seat)
                    packet=builder.build_public(b,seat)
                    pc,pm=py.candidates(packet);nc,nm=native_candidates(native,root,packet,seat)
                    try:
                        assert public['ok'],public
                        assert pc==nc and np.array_equal(pm,nm),('candidate order',pc,nc)
                        pa=py.score_candidates(b,seat,pc,trace=True)
                        na=native.score_candidates(root,seat,nc,trace=True)
                        assert (pa,py.last)==(na,native.last),'planner action/score/trace mismatch'
                        result=dict(ok=True,game=game_id,tick=b.tick,seat=seat,candidates=pc,action=pa,
                                    scores=py.last['scores'],trace_sha256=digest(py.last['traces']),root=battle_digest(b))
                    except Exception as exc:
                        args.output.with_suffix('.failure.pkl').write_bytes(cloudpickle.dumps((b,seat)))
                        args.output.with_suffix('.failure.json').write_text(json.dumps(dict(error=str(exc),public=public,python=py.last,native=native.last),indent=2)+'\n')
                        raise
                    assert fingerprint()==pins['source'],'source changed during gate'
                    out['results'][key]=result
                    tmp=args.output.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2)+'\n');tmp.replace(args.output)
                    print('PASS',key,'game',game_id,'tick',b.tick,'candidates',len(pc),flush=True)
            b.step()
        assert battle_digest(b)==rec['digest'],'replayed game changed'
        if count>=args.calls:break
    assert len(out['results'])==args.calls
    print('PASS',args.calls,'planner calls',flush=True)


if __name__=='__main__':main()
