"""Read-only recursive character and explosive payload templates."""
from differential import entity


def export_payloads(source, battle, output, seen=None):
    seen=set() if seen is None else seen
    key=(type(source).__name__,source.card_stats.name)
    if key in seen:return
    seen.add(key)

    def children(first):
        result=[]
        for id in range(first,battle.next_entity_id):
            child=battle.entities[id];row=entity(child)
            target=row['death_travel'] or (row['x'],row['y'])
            row['x']=round(target[0]-source.position.x,3)
            row['y']=round(target[1]-source.position.y,3)
            result.append(row)
        return result

    death=next((m for m in source.mechanics if type(m).__name__=='DeathSpawn'),None)
    if death is not None:
        first=battle.next_entity_id;death.on_death(source)
        ids=list(range(first,battle.next_entity_id))
        output['death_children'][source.card_stats.name]=children(first)
        for id in ids:export_payloads(battle.entities[id],battle,output,seen)

    production=next((m for m in source.mechanics if type(m).__name__=='PeriodicSpawner'),None)
    if production is not None:
        first=battle.next_entity_id
        production._spawn_units(source,count=1,start_index=0,wave_size=production.count)
        output['production_children'][source.card_stats.name]=entity(battle.entities[first])
        export_payloads(battle.entities[first],battle,output,seen)

    if type(source).__name__=='TimedExplosive' and source.death_spawn_name:
        first=battle.next_entity_id;source._spawn_death_units(battle)
        output.setdefault('bomb_children',{})[source.card_stats.name]=children(first)
