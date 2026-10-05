"""Arena8 slows, one-time Freeze recipients and serialized spawn areas."""
import unittest
import hashlib
import json
from pathlib import Path
import cloudpickle

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class Arena8(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_combat_births_join_avoidance_before_later_movers(self):
        folder=Path(__file__).resolve().parent;root=folder.parents[3]
        p=folder/'arena8-root3239-r8.pkl';pins=json.loads(p.with_suffix('.meta.json').read_text())
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),pins['root_sha256'])
        for name,expected in pins['reference'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),expected,name)
        b=cloudpickle.loads(p.read_bytes())
        cfg=config(tuple(dict.fromkeys(c for player in b.players for c in player.deck)))
        r=clasher_core.BattleState(snapshot(b,cfg))
        for _ in range(140):
            b.step();r.step();self.same(b,r)
            if b.tick==3240:self.assertEqual((b.entities[337].position.x,b.entities[337].position.y),(15.081,18.688))

    def test_snowball_slows_tombstone_fractional_production_and_import(self):
        cards=('Snowball','Tombstone','Knight','Giant');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(668001,cards=cards)
                for p in b.players:p.elixir=10
                y=19.5 if seat==0 else 12.5
                self.assertTrue(b.deploy_card(1-seat,'Tombstone',Position(4.5,y)))
                r=clasher_core.BattleState(snapshot(b,cfg))
                self.assertTrue(b.deploy_card(seat,'Snowball',Position(4.5,y)))
                self.assertTrue(r.apply_action(seat,'Snowball',4.5,y))
                slowed=False
                for _ in range(260):
                    b.step();r.step();self.same(b,r)
                    slowed |= bool(getattr(b.entities.get(7),'_slow_effects',[]))
                    if b.tick in (5,30,40,70,120,200):self.continuation(b,cfg)
                self.assertTrue(slowed)

    def test_freeze_snapshots_death_children_and_ignores_late_arrivals(self):
        cards=('Freeze','Golem','Knight','Goblins');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(668002,cards=cards)
                for p in b.players:p.elixir=10
                y=21.5 if seat==0 else 10.5
                self.assertTrue(b.deploy_card(1-seat,'Golem',Position(4.5,y)))
                for _ in range(30):b.step()
                source=b.entities[7];source.hitpoints=1
                x,y=source.position.x,source.position.y
                r=clasher_core.BattleState(snapshot(b,cfg))
                self.assertTrue(b.deploy_card(seat,'Freeze',Position(x,y)))
                self.assertTrue(r.apply_action(seat,'Freeze',x,y))
                for _ in range(10):b.step();r.step();self.same(b,r)
                children=[e for e in b.entities.values() if getattr(e.card_stats,'name','')=='Golemite']
                self.assertEqual(len(children),2)
                self.assertTrue(all(e.freeze_expiry_time>b.time for e in children))
                b.players[1-seat].elixir=10
                r=clasher_core.BattleState(snapshot(b,cfg))
                late_y=19.5 if seat==0 else 12.5
                late_id=b.next_entity_id
                self.assertTrue(b.deploy_card(1-seat,'Knight',Position(5.5,late_y)))
                self.assertTrue(r.apply_action(1-seat,'Knight',5.5,late_y))
                for _ in range(100):
                    b.step();r.step();self.same(b,r)
                    late=b.entities.get(late_id)
                    if late:self.assertEqual(late.freeze_expiry_time,0)
                    if b.tick in (41,50,70,100):self.continuation(b,cfg)

    def test_healer_spawn_area_lifetime_matches_oracle_without_invented_healing(self):
        cards=('BattleHealer','Knight','Archers','Giant');cfg=config(cards)
        for seat in (0,1):
            b=initial(668003,cards=cards);b.players[seat].elixir=10
            y=10.5 if seat==0 else 21.5
            self.assertTrue(b.deploy_card(seat,'Knight',Position(5.5,y)))
            knight=b.entities[7];knight.hitpoints=100
            self.assertTrue(b.deploy_card(seat,'BattleHealer',Position(4.5,y)))
            r=clasher_core.BattleState(snapshot(b,cfg));seen=False
            for _ in range(80):
                b.step();r.step();self.same(b,r)
                seen |= any(getattr(e,'spell_name','')=='BattleHealerSpawnHeal' for e in b.entities.values())
                self.assertEqual(knight.hitpoints,100)
                if b.tick in (20,21,30,39):self.continuation(b,cfg)
            self.assertTrue(seen)


if __name__=='__main__':unittest.main()
