"""Both-seat live imports for the next serialized status/ramp/spell bundle."""
import unittest
import hashlib
import json
from pathlib import Path
import cloudpickle

import clasher_core
from clasher.entities import Building
from differential import Position,config,initial,snapshot
import test_early


class Reused(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_vines_release_rejects_ground_only_committed_shot(self):
        folder=Path(__file__).resolve().parent
        path=folder/'reuse-r12-root2679.pkl'
        pins=json.loads(path.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((folder.parents[3]/name).read_bytes()).hexdigest(),expected)
        b,cfg,_=cloudpickle.loads(path.read_bytes())
        hp=b.entities[198].hitpoints
        r=clasher_core.BattleState(snapshot(b,cfg));self.same(b,r)
        b.step();r.step();self.same(b,r)
        self.assertEqual(b.entities[198].hitpoints,hp)
        self.continuation(b,cfg,160)

    def test_grounding_release_with_live_shot_both_seats(self):
        cards=('Cannon','InfernoDragon','Vines','Knight');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(669101,cards=cards);sign=1 if seat==0 else -1;ay=12.5 if seat==0 else 19.5
                b._spawn_entity(Building,Position(13.5,ay),seat,b.card_loader.get_card('Cannon'))
                target=b.next_entity_id
                b._spawn_unit_at_position(Position(13.5,ay+sign*4.5),1-seat,b.card_loader.get_card('InfernoDragon'),deploy_delay_override=0,snap_to_valid=False)
                b.entities[target]._vines_grounded=True
                shot=False
                for _ in range(80):
                    b.step()
                    if any(type(e).__name__=='Projectile' and e.player_id==seat for e in b.entities.values()):
                        shot=True;break
                self.assertTrue(shot)
                b.entities[target]._vines_grounded=False
                hp=b.entities[target].hitpoints
                self.continuation(b,cfg,80)
                r=clasher_core.BattleState(snapshot(b,cfg))
                for _ in range(20):b.step();r.step();self.same(b,r)
                self.assertEqual(b.entities[target].hitpoints,hp)

    def test_status_ramp_and_spirit_live_imports(self):
        for card in ('MiniSparkys','WitchMother','InfernoDragon','Heal'):
            cfg=config((card,'Knight','Archers','Giant'))
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(669100,cards=(card,'Knight','Archers','Giant'))
                    for p in b.players:p.elixir=10
                    for owner,name,y in ((seat,card,13.5 if seat==0 else 18.5),(1-seat,'Knight',18.5 if seat==0 else 13.5)):
                        self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    for _ in range(300):
                        b.step();r.step();self.same(b,r)
                        if b.tick in (20,80,180):self.continuation(b,cfg,100)


if __name__=='__main__':unittest.main()
