"""Clone recipient eligibility, shields, suppressed spawn hooks and payloads."""
import json
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class Clone(unittest.TestCase):
    same = test_early.EarlyCards.same
    continuation = test_early.EarlyCards.continuation

    def test_fresh_clones_and_recursive_payloads_both_seats(self):
        for card in ('Knight', 'DarkPrince', 'Witch', 'ElixirGolem',
                     'SkeletonBalloon', 'MegaKnight', 'BattleHealer', 'LavaHound'):
            cards = (card, 'Clone', 'Fireball', 'Archers')
            cfg = config(cards)
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    b = initial(669540, cards=cards)
                    b.players[seat].elixir = 10
                    pos = Position(13.5, 13.5 if seat == 0 else 18.5)
                    self.assertTrue(b.deploy_card(seat, card, pos))
                    for _ in range(30): b.step()
                    source = next(e for e in b.entities.values()
                                  if e.player_id == seat and type(e).__name__ == 'Troop')
                    pos = Position(source.position.x, source.position.y)
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    self.assertTrue(b.deploy_card(seat, 'Clone', pos))
                    self.assertTrue(r.apply_action(seat, 'Clone', pos.x, pos.y))
                    self.same(b, r)
                    self.assertTrue(any(e.is_clone for e in b.entities.values()))
                    self.continuation(b, cfg, 100)
                    for _ in range(650):
                        if b.tick == 50:
                            b.players[1-seat].elixir = 10
                            r = clasher_core.BattleState(snapshot(b, cfg))
                            self.assertTrue(b.deploy_card(1-seat, 'Fireball', pos))
                            self.assertTrue(r.apply_action(1-seat, 'Fireball', pos.x, pos.y))
                        b.step(); r.step(); self.same(b, r)
                        if b.tick in (60, 150, 300): self.continuation(b, cfg, 80)

    def test_broken_shield_and_existing_clone_are_not_restored(self):
        cards = ('DarkPrince', 'Clone', 'Knight', 'Fireball')
        cfg = config(cards)
        for seat in (0, 1):
            b = initial(669541, cards=cards)
            b.players[seat].elixir = 10
            pos = Position(13.5, 13.5 if seat == 0 else 18.5)
            self.assertTrue(b.deploy_card(seat, 'DarkPrince', pos))
            source = b.entities[max(b.entities)]
            source.take_damage(1000)
            b.players[seat].elixir = 10
            r = clasher_core.BattleState(snapshot(b, cfg))
            self.assertTrue(b.deploy_card(seat, 'Clone', pos))
            self.assertTrue(r.apply_action(seat, 'Clone', pos.x, pos.y))
            self.same(b, r)
            clones = [e for e in json.loads(r.snapshot())['entities'] if e['is_clone']]
            self.assertEqual(len(clones), 1)
            self.assertEqual(clones[0]['shield'], 0)
            b.players[seat].hand[0] = 'Clone'
            b.players[seat].elixir = 10
            r = clasher_core.BattleState(snapshot(b, cfg))
            before = b.next_entity_id
            self.assertTrue(b.deploy_card(seat, 'Clone', pos))
            self.assertTrue(r.apply_action(seat, 'Clone', pos.x, pos.y))
            self.assertEqual(b.next_entity_id, before+1)
            self.same(b, r)
            self.continuation(b, cfg, 120)
