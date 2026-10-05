"""Both-seat combat and live imports for base bodies and serialized clocks."""
import unittest

import clasher_core
from differential import Position,config,initial,snapshot
import test_early


class Body(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_body_shield_charge_and_live_imports(self):
        for card in ('Elixir Collector','ZapMachine','MovingCannon','SkeletonKing','Phoenix','ElectroGiant'):
            cfg=config((card,'Knight','Archers','Giant'))
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(669200,cards=(card,'Knight','Archers','Giant'))
                    for p in b.players:p.elixir=10
                    for owner,name,y in ((seat,card,12.5 if seat==0 else 19.5),(1-seat,'Knight',18.5 if seat==0 else 13.5)):
                        self.assertTrue(b.deploy_card(owner,name,Position(13.5,y)))
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    for _ in range(500):
                        b.step();r.step();self.same(b,r)
                        if b.tick in (20,80,180,350):self.continuation(b,cfg,100)


if __name__=='__main__':unittest.main()
