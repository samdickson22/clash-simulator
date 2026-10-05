"""Stage 6 reduced oracle comparisons; no reference engine mutation."""
import unittest

import clasher_core
from differential import Position, battle_digest, config, initial, snapshot


class EarlyCards(unittest.TestCase):
    def same(self, b, r):
        self.assertEqual(battle_digest(b), r.digest(), f'tick {b.tick}')
        words, index = r.rng_state()
        self.assertEqual(b.rng.getstate()[1], tuple(words) + (index,))

    def continuation(self, b, cfg, ticks=80):
        r = clasher_core.BattleState(snapshot(b, cfg))
        original = battle_digest(b)
        copy, child = b.clone(), r.clone()
        self.same(copy, child)
        for _ in range(ticks):
            copy.step(); child.step(); self.same(copy, child)
        self.assertEqual(original, battle_digest(b))
        self.assertEqual(original, r.digest())

    def test_ordinary_ground_air_splash_and_live_import(self):
        for card in ('SpearGoblins', 'Bomber', 'Barbarians', 'MegaMinion', 'Pekka'):
            cfg = config((card, 'Knight', 'Archers', 'Giant'))
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    b = initial(660001, cards=(card, 'Knight', 'Archers', 'Giant'))
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    for owner, name, y in ((seat, card, 13.5 if seat == 0 else 18.5),
                                           (1-seat, 'Knight', 18.5 if seat == 0 else 13.5)):
                        self.assertTrue(b.deploy_card(owner, name, Position(13.5, y)))
                        self.assertTrue(r.apply_action(owner, name, 13.5, y))
                        self.same(b, r)
                    for _ in range(220):
                        b.step(); r.step(); self.same(b, r)
                        if b.tick in (1, 19, 23, 80, 170):
                            self.continuation(b, cfg)

    def test_production_and_zero_radius_death_children_both_seats(self):
        for card in ('GoblinCage', 'Tombstone', 'Witch'):
            cfg = config((card, 'Fireball', 'Knight', 'Giant'))
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    b = initial(660002, cards=(card, 'Fireball', 'Knight', 'Giant'))
                    b.players[seat].elixir = 10
                    y = 13.5 if seat == 0 else 18.5
                    self.assertTrue(b.deploy_card(seat, card, Position(13.5, y)))
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    for _ in range(1000):
                        if b.tick == 350:
                            b.players[1-seat].elixir = 10
                            r = clasher_core.BattleState(snapshot(b, cfg))
                            self.assertTrue(b.deploy_card(1-seat, 'Fireball', Position(13.5, y)))
                            self.assertTrue(r.apply_action(1-seat, 'Fireball', 13.5, y))
                        b.step(); r.step(); self.same(b, r)
                        if b.tick in (1, 20, 21, 22, 70, 71, 80, 350, 360, 600):
                            self.continuation(b, cfg)


if __name__ == '__main__':
    unittest.main()
