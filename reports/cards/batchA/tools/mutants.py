"""Mutation checks for probe_first_update_paths.py: run selected cases with a deliberately wrong Python boundary.
Usage: mutants.py MUTANT OUT.json CASE ...   MUTANT = no_death_first_update | first_update_before_freeze"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import probe_first_update_paths as P
import clasher.battle as B
from clasher.mechanics.shared import death_effects as DE

mutant = sys.argv[1]
orig = B.BattleState._first_update_spawned
if mutant == 'no_death_first_update':
    def f(self, troop, *, collide=True, hidden=frozenset()):
        if collide:  # periodic emissions keep theirs; death spawns (collide=False) lose it
            return orig(self, troop, collide=collide, hidden=hidden)
    B.BattleState._first_update_spawned = f
elif mutant == 'first_update_before_freeze':
    # Review r1's bug: step each death child at its creation, before it inherits the parent's Freeze.
    old_on_death = DE.DeathSpawn.on_death
    def on_death(self, entity):
        bs = entity.battle_state
        real_spawn = bs._spawn_unit_at_position
        def spawn(*a, **k):
            first = bs.next_entity_id
            real_spawn(*a, **k)
            orig(bs, bs.entities.get(first), collide=False)
        bs._spawn_unit_at_position = spawn
        saved, self.first_update = self.first_update, False
        try:
            if saved:
                old_on_death(self, entity)
            else:
                del bs._spawn_unit_at_position
                old_on_death(self, entity)
                return
        finally:
            self.first_update = saved
        del bs._spawn_unit_at_position
    DE.DeathSpawn.on_death = on_death
else:
    sys.exit('unknown mutant')
res = []
for n in sys.argv[3:]:
    for seat, case in (('blue', P.CASES[n]), ('red', P.mirror(P.CASES[n]))):
        r = P.one(f'{n}/{seat}', case); res.append(r)
        print(mutant, r['case'], r['native'], 'mismatch', r.get('first_mismatch'), flush=True)
json.dump(res, open(sys.argv[2], 'w'), indent=1)
