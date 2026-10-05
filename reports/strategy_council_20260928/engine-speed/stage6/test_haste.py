"""Nested death areas and independently timed positive speed modifiers."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class Haste(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_spell_delayed_impact_haste_and_live_imports(self):
        cards=('Rage','Knight','Tombstone','Snowball');cfg=config(cards)
        for seat in (0,1):
            with self.subTest(seat=seat):
                b=initial(669524,cards=cards);pos=Position(13.5,13.5 if seat==0 else 18.5)
                b.players[seat].elixir=10
                self.assertTrue(b.deploy_card(seat,'Knight',pos))
                b.players[seat].elixir=10
                self.assertTrue(b.deploy_card(seat,'Tombstone',Position(12.5,12.5 if seat==0 else 19.5)))
                b.players[seat].elixir=10
                r=clasher_core.BattleState(snapshot(b,cfg))
                self.assertTrue(b.deploy_card(seat,'Rage',pos))
                self.assertTrue(r.apply_action(seat,'Rage',pos.x,pos.y));self.same(b,r)
                saw_haste=False
                for _ in range(230):
                    b.step();r.step();self.same(b,r)
                    saw_haste|=any(e._haste_effects for e in b.entities.values())
                    if b.tick in (1,9,10,11,17,50,100,119,140):self.continuation(b,cfg,80)
                self.assertTrue(saw_haste)

    def test_death_area_chain_and_death_spawn_both_seats(self):
        for card in ('RageBarbarian','SuspiciousBush'):
            cards=(card,'Knight','Fireball','Tombstone');cfg=config(cards)
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(669525,cards=cards);pos=Position(13.5,13.5 if seat==0 else 18.5)
                    b.players[seat].elixir=10;self.assertTrue(b.deploy_card(seat,card,pos))
                    parent=b.next_entity_id-1
                    b.players[seat].elixir=10;self.assertTrue(b.deploy_card(seat,'Tombstone',Position(12.5,pos.y)))
                    b.entities[parent].hitpoints=1;b.players[1-seat].elixir=10
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    self.assertTrue(b.deploy_card(1-seat,'Fireball',pos))
                    self.assertTrue(r.apply_action(1-seat,'Fireball',pos.x,pos.y));self.same(b,r)
                    for _ in range(250):
                        b.step();r.step();self.same(b,r)
                        if b.tick in (1,20,21,22,23,25,30,45,90,150):self.continuation(b,cfg,80)
                    self.assertNotIn(parent,b.entities)

    def test_haste_slow_integer_composition_and_expiry(self):
        cards=('Knight','Tombstone','IceWizard','Rage');cfg=config(cards)
        for seat in (0,1):
            b=initial(669526,cards=cards);b.players[seat].elixir=10
            self.assertTrue(b.deploy_card(seat,'Knight',Position(13.5,13.5 if seat==0 else 18.5)))
            b.players[seat].elixir=10
            self.assertTrue(b.deploy_card(seat,'Tombstone',Position(12.5,12.5 if seat==0 else 19.5)))
            for e in b.entities.values():
                if e.player_id==seat:
                    e.apply_haste(1.2,1.3,1.3,1.3)
                    e.apply_haste(2.2,1.1,1.2,1.4)
                    e.apply_slow(1.7,0.7,attack_speed_multiplier=0.7,spawn_speed_multiplier=0.7)
            r=clasher_core.BattleState(snapshot(b,cfg))
            for _ in range(180):
                b.step();r.step();self.same(b,r)
                if b.tick in (20,24,34,44):self.continuation(b,cfg,80)

if __name__=='__main__':unittest.main()
