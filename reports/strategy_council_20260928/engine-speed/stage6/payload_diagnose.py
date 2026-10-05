"""Retain Skeleton Barrel's first explosive-child continuation mismatch."""
import argparse
import json
from pathlib import Path
import clasher_core
from differential import Position,config,initial,snapshot,battle_digest
from diagnostics import detail

parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
folder=Path(__file__).resolve().parent
cards=('SkeletonBalloon','Fireball','Knight','Archers');cfg=config(cards)
b=initial(669500,cards=cards)
for p in b.players:p.elixir=10
assert b.deploy_card(0,'SkeletonBalloon',Position(13.5,13.5))
for _ in range(20):b.step()
r=clasher_core.BattleState(snapshot(b,cfg))
for _ in range(180):
    b.step();r.step()
    if battle_digest(b)!=r.digest():
        data=detail(b,r);path=folder/f'barrel{b.tick}-{args.label}.json'
        assert not path.exists();path.write_text(json.dumps(data,indent=2)+'\n')
        print(b.tick,data['field_diff'][:35],flush=True);break
