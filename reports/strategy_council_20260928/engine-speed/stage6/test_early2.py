"""Both-seat combat and live imports for the next low-arena generic bodies."""
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
import test_early

CARDS=('SkeletonDragons','Mortar','DartBarrell','SkeletonWarriors','RoyalGiant',
       'ThreeMusketeers','RoyalRecruits')


class Early2(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_missing_serialized_speed_skips_deployment_snap(self):
        cards=('ThreeMusketeers','Knight','Archers','Giant');cfg=config(cards)
        for seat in (0,1):
            for x in (4.5,13.5):
                b=initial(cards=cards);b.players[seat].elixir=10
                r=clasher_core.BattleState(snapshot(b,cfg));y=10.5 if seat==0 else 21.5
                self.assertTrue(b.deploy_card(seat,cards[0],Position(x,y)))
                self.assertTrue(r.apply_action(seat,cards[0],x,y))
                self.assertEqual((b.entities[7].position.x,b.entities[7].position.y),(x,y))
                self.same(b,r)

    def test_recruits_recompute_line_clipping_and_tower_avoidance(self):
        cards=('RoyalRecruits','Knight','Archers','Giant');cfg=config(cards)
        for seat in (0,1):
            for x in (0.5,4.5,8.5,13.5,17.5):
                for y0 in (2.5,5.5,8.5,13.5):
                    y=y0 if seat==0 else 32-y0
                    with self.subTest(seat=seat,x=x,y=y):
                        b=initial(cards=cards);b.players[seat].elixir=10
                        r=clasher_core.BattleState(snapshot(b,cfg))
                        accepted=b.deploy_card(seat,cards[0],Position(x,y))
                        self.assertEqual(accepted,r.apply_action(seat,cards[0],x,y))
                        self.same(b,r)
                        if accepted:self.continuation(b,cfg,40)

    def test_shields_formations_siege_air_and_imports(self):
        for card in CARDS:
            cards=(card,'Knight','Archers','Giant');cfg=config(cards)
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(665000,cards=cards);b.players[seat].elixir=10
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    x=8.5 if card=='RoyalRecruits' else 13.5
                    for owner,name,y in ((seat,card,13.5 if seat==0 else 18.5),
                                          (1-seat,'Knight',18.5 if seat==0 else 13.5)):
                        self.assertTrue(b.deploy_card(owner,name,Position(x,y)))
                        self.assertTrue(r.apply_action(owner,name,x,y));self.same(b,r)
                    for _ in range(500):
                        b.step();r.step();self.same(b,r)
                        if b.tick in (1,19,23,80,170,300,420):self.continuation(b,cfg)


if __name__=='__main__':unittest.main()
