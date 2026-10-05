"""Electro Wizard's committed recipients, duplicate bolt and hit statuses."""
import unittest
import hashlib
import json
from pathlib import Path
import cloudpickle

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class Ranged(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_lethal_secondary_stun_cancels_eligible_hunter_shot(self):
        folder=Path(__file__).resolve().parent
        path=folder/'ranged-root4862-r11b.pkl'
        pins=json.loads(path.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),pins['root_sha256'])
        root=folder.parents[3]
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected)
        b,cfg,_=cloudpickle.loads(path.read_bytes())
        self.assertEqual(b.tick,4862)
        r=clasher_core.BattleState(snapshot(b,cfg));self.same(b,r)
        b.step();r.step();self.same(b,r)
        self.assertNotIn(546,b.entities)
        self.assertEqual(b.next_entity_id,562)
        self.continuation(b,cfg,160)

    def fixture(self, seat, extra):
        cards=('ElectroWizard','Knight','Golem','Minions');cfg=config(cards)
        b=initial(669001,cards=cards);sign=1 if seat==0 else -1;ay=10.0 if seat==0 else 22.0
        def spawn(owner,name,x,y):
            id=b.next_entity_id
            b._spawn_unit_at_position(Position(x,y),owner,b.card_loader.get_card(name),deploy_delay_override=0,snap_to_valid=False)
            return id
        actor=spawn(seat,'ElectroWizard',9.0,ay)
        first=spawn(1-seat,'Golem' if extra=='death' else 'Knight',9.0,ay+sign*4.8)
        others=[]
        if extra=='split':
            others=[spawn(1-seat,'Minions',x,ay+sign*4.8) for x in (8.0,10.0)]
        if extra=='death':
            b.entities[first].hitpoints=1
            others=[spawn(1-seat,'Knight',9.0,ay+sign*5.5)]
        return b,cfg,actor,first,others

    def test_unused_bolt_hits_primary_and_distinct_targets_receive_stun(self):
        for seat in (0,1):
            for extra in ('single','split'):
                with self.subTest(seat=seat,extra=extra):
                    b,cfg,actor,first,others=self.fixture(seat,extra)
                    hp={id:b.entities[id].hitpoints for id in [first,*others]}
                    r=clasher_core.BattleState(snapshot(b,cfg));hit=False
                    for _ in range(100):
                        b.step();r.step();self.same(b,r)
                        changed=[id for id in hp if b.entities.get(id) and b.entities[id].hitpoints<hp[id]]
                        if changed:
                            hit=True
                            if extra=='single':self.assertEqual(hp[first]-b.entities[first].hitpoints,2*b.entities[actor].damage)
                            else:self.assertEqual(len(changed),2)
                            self.assertTrue(all(b.entities[id].stun_timer>0 for id in changed))
                            self.continuation(b,cfg,120)
                            break
                    self.assertTrue(hit)

    def test_secondary_snapshot_does_not_retarget_new_death_children(self):
        for seat in (0,1):
            with self.subTest(seat=seat):
                b,cfg,actor,first,others=self.fixture(seat,'death')
                hp=b.entities[others[0]].hitpoints;r=clasher_core.BattleState(snapshot(b,cfg));hit=False
                for _ in range(100):
                    b.step();r.step();self.same(b,r)
                    children=[e for e in b.entities.values() if getattr(e.card_stats,'name','')=='Golemite']
                    if children:
                        hit=True;self.assertEqual(len(children),2)
                        self.assertTrue(all(e.hitpoints==e.max_hitpoints for e in children))
                        self.assertEqual(hp-b.entities[others[0]].hitpoints,b.entities[actor].damage)
                        self.continuation(b,cfg,100)
                        break
                self.assertTrue(hit)

    def test_ice_wizard_projectile_slow_and_live_shot_import(self):
        for seat in (0,1):
            with self.subTest(seat=seat):
                cards=('IceWizard','Knight','Golem','Minions');cfg=config(cards)
                b=initial(669002,cards=cards);sign=1 if seat==0 else -1;ay=10 if seat==0 else 22
                b._spawn_unit_at_position(Position(9,ay),seat,b.card_loader.get_card('IceWizard'),deploy_delay_override=0,snap_to_valid=False)
                target=b.next_entity_id
                b._spawn_unit_at_position(Position(9,ay+sign*4.8),1-seat,b.card_loader.get_card('Knight'),deploy_delay_override=0,snap_to_valid=False)
                r=clasher_core.BattleState(snapshot(b,cfg));flight=slow=False
                for _ in range(160):
                    b.step();r.step();self.same(b,r)
                    if not flight and any(type(e).__name__=='Projectile' for e in b.entities.values()):
                        flight=True;self.continuation(b,cfg,100)
                    if b.entities[target].slow_multiplier<1:
                        slow=True;self.assertEqual(b.entities[target].slow_multiplier,0.7)
                        self.continuation(b,cfg,160)
                        break
                self.assertTrue(flight);self.assertTrue(slow)


if __name__=='__main__':unittest.main()
