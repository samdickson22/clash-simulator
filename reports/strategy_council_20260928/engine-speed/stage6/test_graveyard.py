"""Graveyard deadline, geometry and in-flight import regressions."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early

class Graveyard(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_deadlines_lane_edges_both_seats_and_live_import(self):
        cards=('Graveyard','Knight','Archers','Fireball');cfg=config(cards)
        for seat in (0,1):
            for x,y in ((4.5,10.5),(13.5,21.5),(0.5,13.5),(9.5,16.0)):
                with self.subTest(seat=seat,x=x,y=y):
                    b=initial(669522,cards=cards);b.players[seat].elixir=10
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    self.assertTrue(b.deploy_card(seat,'Graveyard',Position(x,y)))
                    self.assertTrue(r.apply_action(seat,'Graveyard',x,y));self.same(b,r)
                    for _ in range(250):
                        b.step();r.step();self.same(b,r)
                        if b.tick in (1,23,24,50,120,179):self.continuation(b,cfg,80)

if __name__=='__main__':unittest.main()
