"""Active Skeleton swarms at clipped boundaries and across formation lanes."""
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class SkeletonEdges(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_active_ring_at_edges_and_middle_for_both_seats(self):
        cards=('SkeletonKing','Knight','Zap','Archers');cfg=config(cards)
        for seat in (0,1):
            for x in (0.5,8.5,9.5,17.5):
                with self.subTest(seat=seat,x=x):
                    b=initial(669562,cards=cards);b.players[seat].elixir=10
                    self.assertTrue(b.deploy_card(seat,'SkeletonKing',Position(x,4.5 if seat==0 else 27.5)))
                    actor=b.entities[max(b.entities)]
                    mechanic=next(m for m in actor.mechanics if type(m).__name__=='SkeletonKingSoulCollector')
                    mechanic.souls_collected=30
                    for _ in range(25):b.step()
                    b.players[seat].elixir=10
                    r=clasher_core.BattleState(snapshot(b,cfg));first=b.next_entity_id
                    self.assertTrue(b.activate_champion_ability(seat))
                    self.assertTrue(r.activate_champion_ability(seat))
                    self.assertEqual(b.next_entity_id-first,45);self.same(b,r)
                    self.assertFalse(b.activate_champion_ability(seat))
                    self.assertFalse(r.activate_champion_ability(seat))
                    self.continuation(b,cfg,40)
                    for _ in range(40):b.step();r.step();self.same(b,r)
