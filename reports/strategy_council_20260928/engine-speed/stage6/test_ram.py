"""Building-hit ram destruction and delayed-bomb continuation reductions."""
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
from test_early import EarlyCards


class RamAndBomb(unittest.TestCase):
    same = EarlyCards.same
    continuation = EarlyCards.continuation

    def test_ram_dies_on_building_hit_and_releases_two_riders(self):
        cards = ('BattleRam', 'Cannon', 'Knight', 'Archers')
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(660003, cards=cards)
                y = 13.5 if seat == 0 else 18.5
                self.assertTrue(b.deploy_card(seat, 'BattleRam', Position(4.5, y)))
                self.assertTrue(b.deploy_card(1-seat, 'Cannon', Position(4.5, 32-y)))
                r = clasher_core.BattleState(snapshot(b, cfg))
                witnessed = False
                for _ in range(300):
                    b.step(); r.step(); self.same(b, r)
                    riders = [e for e in b.entities.values()
                              if getattr(e.card_stats, 'name', '') == 'Barbarian']
                    if riders and not witnessed:
                        witnessed = True
                        self.assertEqual(len(riders), 2)
                        self.assertNotIn(7, b.entities)
                        self.continuation(b, cfg, 100)
                self.assertTrue(witnessed)

    def test_giant_skeleton_delayed_bomb_both_seats_and_imports(self):
        cards = ('GiantSkeleton', 'Zap', 'Knight', 'Archers')
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(660004, cards=cards)
                b.players[seat].elixir = 10
                y = 13.5 if seat == 0 else 18.5
                b.deploy_card(seat, 'GiantSkeleton', Position(4.5, y))
                for _ in range(30): b.step()
                source = b.entities[7]
                source.hitpoints = 1
                b.players[1-seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                x, y = source.position.x, source.position.y
                self.assertTrue(b.deploy_card(1-seat, 'Zap', Position(x, y)))
                self.assertTrue(r.apply_action(1-seat, 'Zap', x, y))
                seen = False
                for _ in range(140):
                    b.step(); r.step(); self.same(b, r)
                    seen |= any(type(e).__name__ == 'TimedExplosive' for e in b.entities.values())
                    if b.tick in (35, 40, 60, 85): self.continuation(b, cfg, 80)
                self.assertTrue(seen)


if __name__ == '__main__':
    unittest.main()
