"""Small all-C56 public-action controls for baseline-clock attribution."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import traceback

import differential as D
import mixed_games as M
from sanitize_results import scrub


def deck(front):
    return list(dict.fromkeys(front+['Knight','Giant','Goblins','Zap','Musketeer','Archer','Skeletons','Fireball','Prince','Tesla']))[:8]


CASES = [
    dict(name='xbow-idle-giant',decks=[deck(['Xbow']),deck(['Giant'])],
         commands=[[0,0,'Xbow',7.5,11.5],[120,1,'Giant',4.5,18.0]]),
    dict(name='xbow-idle-skeletonarmy',decks=[deck(['Xbow']),deck(['SkeletonArmy'])],
         commands=[[0,0,'Xbow',7.5,11.5],[120,1,'SkeletonArmy',4.5,18.0]]),
    dict(name='xbow-idle-skeletons',decks=[deck(['Xbow']),deck(['Skeletons'])],
         commands=[[0,0,'Xbow',7.5,11.5],[120,1,'Skeletons',4.5,18.0]]),
    dict(name='inferno-retarget',decks=[deck(['Musketeer','Minions','GoblinBarrel']),deck(['Arrows','InfernoTower','Goblins'])],
         commands=[[0,0,'Musketeer',12.5,6.5],[0,1,'Arrows',13.5,7.5],
                   [40,0,'Minions',12.5,6.5],[40,1,'InfernoTower',7.5,20.5],
                   [80,0,'GoblinBarrel',13.5,25.5],[80,1,'Goblins',12.5,25.5]]),
    dict(name='inferno-giant-knight',decks=[deck(['InfernoTower']),deck(['Giant','Knight'])],
         commands=[[0,0,'InfernoTower',7.5,11.5],[0,1,'Giant',4.5,18.0],[160,1,'Knight',4.5,18.0]]),
    dict(name='valkyrie-delayed-goblins',decks=[deck(['Goblins']),deck(['Valkyrie'])],
         commands=[[0,1,'Valkyrie',5.5,25.5],[120,0,'Goblins',4.5,14.0]]),
    dict(name='valkyrie-giant-goblins',decks=[deck(['Giant','Goblins']),deck(['Valkyrie'])],
         commands=[[0,1,'Valkyrie',5.5,25.5],[0,0,'Giant',4.5,14.0],[120,0,'Goblins',4.5,14.0]]),
]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    assert hashlib.sha256(Path(D.clasher_core.__file__).read_bytes()).hexdigest()==M.PIN
    cfg=json.loads(args.config.read_text())
    for i,case in enumerate(CASES):
        path=args.output/(case['name']+'.json')
        if path.exists():continue
        game=dict(game=700+i,seed=9140000+i,decks=case['decks'])
        actions=[];first=None
        b,native=M.setup(game,cfg)
        commands=defaultdict(list)
        for t,s,c,x,y in case['commands']:commands[t].append((s,c,x,y))
        try:
            for _ in range(3600):
                if b.game_over:break
                for s,c,x,y in commands[b.tick]:
                    pa=bool(b.deploy_card(s,c,D.Position(x,y)));ra=bool(native.apply_action(s,c,x,y))
                    actions.append([b.tick,s,c,x,y,pa,ra])
                    assert pa and ra,actions[-1]
                b.step();native.step()
                if first is None and D.battle_digest(b)!=native.digest():
                    first=dict(kind='digest',tick=b.tick,detail=M.focus_detail(b,native))
            row=dict(name=case['name'],game=game,first=first,ticks=b.tick,actions=actions,
                     status='mismatch' if first else 'match')
            if first:row['triage']=M.replay_triage(game,cfg,first,actions)
        except BaseException:
            row=dict(name=case['name'],game=game,status='exception',error=traceback.format_exc(),actions=actions)
        M.atomic(path,scrub(row))
        print(case['name'],row['status'],(row.get('first') or {}).get('tick'),flush=True)


if __name__=='__main__':main()
