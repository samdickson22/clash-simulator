"""Mirror accepted-history semantics and captured level12 payloads."""
import json
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class Mirror(unittest.TestCase):
    same = test_early.EarlyCards.same
    continuation = test_early.EarlyCards.continuation

    def test_oracle_unsupported_level12_spells_reject_without_payment(self):
        for card in ('Clone', 'Earthquake', 'Poison', 'Tornado'):
            cards=(card,'Mirror','Knight','Archers');cfg=config(cards)
            b=initial(669553,cards=cards);b.players[0].elixir=10
            pos=Position(13.5,13.5)
            self.assertTrue(b.deploy_card(0,card,pos))
            b.players[0].elixir=10
            r=clasher_core.BattleState(snapshot(b,cfg))
            self.assertIsNone(b.resolve_card_play(0,'Mirror'))
            self.assertFalse(b.deploy_card(0,'Mirror',pos))
            self.assertFalse(r.apply_action(0,'Mirror',pos.x,pos.y))
            self.same(b,r);self.history(b,r)
            self.assertEqual(b.players[0].elixir,10)
            self.continuation(b,cfg,100)

    def history(self, b, r):
        for p, n in zip(b.players, json.loads(r.snapshot())['players']):
            self.assertEqual(p.last_played_card, n['last_card'])
            self.assertEqual(p.last_played_card_cost, n['last_cost'])

    def test_no_history_rejections_do_not_pay_or_cycle(self):
        cards = ('Mirror', 'Knight', 'Zap', 'Archers')
        cfg = config(cards)
        for seat in (0, 1):
            b = initial(669550, cards=cards)
            r = clasher_core.BattleState(snapshot(b, cfg))
            pos = Position(13.5, 13.5 if seat == 0 else 18.5)
            self.assertFalse(b.deploy_card(seat, 'Mirror', pos))
            self.assertFalse(r.apply_action(seat, 'Mirror', pos.x, pos.y))
            self.same(b, r); self.history(b, r)
            self.assertTrue(b.deploy_card(seat, 'Knight', pos))
            self.assertTrue(r.apply_action(seat, 'Knight', pos.x, pos.y))
            b.players[seat].elixir = 0
            r = clasher_core.BattleState(snapshot(b, cfg))
            self.assertFalse(b.deploy_card(seat, 'Mirror', pos))
            self.assertFalse(r.apply_action(seat, 'Mirror', pos.x, pos.y))
            self.same(b, r); self.history(b, r)

    def test_level12_bodies_spells_children_and_imports(self):
        for card in ('Knight', 'Fireball', 'GoblinBarrel', 'Graveyard',
                     'Golem', 'Witch', 'ElectroSpirit', 'Cannon'):
            cards = (card, 'Mirror', 'Zap', 'Archers')
            cfg = config(cards)
            for seat in (0, 1):
                with self.subTest(card=card, seat=seat):
                    b = initial(669551, cards=cards)
                    b.players[seat].elixir = 10
                    y = (25.5 if seat == 0 else 6.5) if cfg['cards'][card].get('spell') else (13.5 if seat == 0 else 18.5)
                    pos = Position(13.5, y)
                    self.assertTrue(b.deploy_card(seat, card, pos))
                    for _ in range(30): b.step()
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    mirror_pos = Position(4.5, pos.y)
                    self.assertTrue(b.deploy_card(seat, 'Mirror', mirror_pos))
                    self.assertTrue(r.apply_action(seat, 'Mirror', mirror_pos.x, mirror_pos.y))
                    self.same(b, r); self.history(b, r)
                    self.assertEqual(b.players[seat].last_played_card, card)
                    self.continuation(b, cfg, 100)
                    for _ in range(700):
                        b.step(); r.step(); self.same(b, r)
                        if b.tick in (31, 50, 100, 180, 350):
                            self.continuation(b, cfg, 100)
