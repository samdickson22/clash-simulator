"""Construct recursive payloads read-only; this is not a simulation gate."""
import json
from pathlib import Path
from differential import Position,initial,entity
from stage2 import fingerprint

folder=Path(__file__).resolve().parent
output=folder/'payload-inventory-r17.json'
assert not output.exists()
rows=[];seen=set()

def visit(source,b):
    key=(type(source).__name__,getattr(source.card_stats,'name',''))
    if key in seen:return
    seen.add(key)
    rows.append(dict(kind=key,mechanics=[type(m).__name__ for m in source.mechanics]))
    for mechanic in source.mechanics:
        if type(mechanic).__name__=='DeathSpawn':
            first=b.next_entity_id;mechanic.on_death(source)
            children=[b.entities[id] for id in range(first,b.next_entity_id)]
            rows[-1]['death_children']=[dict(kind=type(e).__name__,name=getattr(e.card_stats,'name',''),hp=e.hitpoints) for e in children]
            for child in children:visit(child,b)
    if type(source).__name__=='TimedExplosive' and source.death_spawn_name:
        first=b.next_entity_id;source._spawn_death_units(b)
        children=[b.entities[id] for id in range(first,b.next_entity_id)]
        for child in children:visit(child,b)

for card in ('DarkWitch','SkeletonBalloon','LavaHound','ElixirGolem','SuspiciousBush','BarbarianHut'):
    b=initial(cards=(card,'Knight','Archers','Giant'));b.players[0].elixir=10
    assert b.deploy_card(0,card,Position(4.5,10.5));visit(b.entities[max(b.entities)],b)
output.write_text(json.dumps(dict(source=fingerprint(),rows=rows),indent=2)+'\n')
print(json.dumps(rows,indent=2),flush=True)
