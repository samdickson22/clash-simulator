"""Nested death/production payloads and imported continuations, both seats."""
import unittest
import clasher_core
from differential import Position,config,initial,snapshot
import test_early


class Payloads(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_production_nested_splits_explosive_children_and_live_imports(self):
        for card in ('DarkWitch','SkeletonBalloon','LavaHound','ElixirGolem','BarbarianHut'):
            cards=(card,'Fireball','Knight','Archers');cfg=config(cards)
            for seat in (0,1):
                with self.subTest(card=card,seat=seat):
                    b=initial(669500,cards=cards)
                    for p in b.players:p.elixir=10
                    pos=Position(13.5,13.5 if seat==0 else 18.5)
                    self.assertTrue(b.deploy_card(seat,card,pos));parent=b.next_entity_id-1
                    r=clasher_core.BattleState(snapshot(b,cfg));dead=False
                    for _ in range(800):
                        if b.tick==100 and parent in b.entities:
                            b.entities[parent].hitpoints=1
                            b.players[1-seat].elixir=10
                            r=clasher_core.BattleState(snapshot(b,cfg))
                            self.assertTrue(b.deploy_card(1-seat,'Fireball',pos))
                            self.assertTrue(r.apply_action(1-seat,'Fireball',pos.x,pos.y))
                        b.step();r.step();self.same(b,r)
                        dead|=parent not in b.entities
                        if b.tick in (20,60,110,160,300,600):self.continuation(b,cfg,100)
                    self.assertTrue(dead)


if __name__=='__main__':unittest.main()
