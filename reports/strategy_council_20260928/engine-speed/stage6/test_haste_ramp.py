"""Haste must advance a continuous channel's lock timer with combat work."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class HasteRamp(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation
    def test_hasted_inferno_lock_damage_and_imports(self):
        cards=('InfernoDragon','Giant','Rage','Knight');cfg=config(cards)
        for seat in (0,1):
            b=initial(669527,cards=cards)
            b.players[seat].elixir=10
            self.assertTrue(b.deploy_card(seat,'InfernoDragon',Position(13.5,13.5 if seat==0 else 18.5)))
            source=b.entities[b.next_entity_id-1];source.apply_haste(8,1.3,1.3,1.3)
            b.players[1-seat].elixir=10
            self.assertTrue(b.deploy_card(1-seat,'Giant',Position(13.5,18.5 if seat==0 else 13.5)))
            r=clasher_core.BattleState(snapshot(b,cfg))
            for _ in range(400):
                b.step();r.step();self.same(b,r)
                if b.tick in (30,70,100):self.continuation(b,cfg,140)

if __name__=='__main__':unittest.main()
