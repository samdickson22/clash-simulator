"""Skeleton King's active summon, misleading ready bit, ownership and imports."""
import json
import unittest

import clasher_core
from differential import Position, config, initial, snapshot
import test_early


class SkeletonAbility(unittest.TestCase):
    same=test_early.EarlyCards.same
    continuation=test_early.EarlyCards.continuation

    def test_soul_threshold_summon_cost_timers_and_both_seat_imports(self):
        cards=('SkeletonKing','Knight','Zap','Archers');cfg=config(cards)
        for seat in (0,1):
            for souls in (0,19,20,30):
                with self.subTest(seat=seat,souls=souls):
                    b=initial(669560,cards=cards);b.players[seat].elixir=10
                    self.assertTrue(b.deploy_card(seat,'SkeletonKing',Position(13.5,13.5 if seat==0 else 18.5)))
                    actor=b.entities[max(b.entities)]
                    mechanic=next(m for m in actor.mechanics if type(m).__name__=='SkeletonKingSoulCollector')
                    mechanic.souls_collected=souls
                    for _ in range(25):b.step()
                    b.players[seat].elixir=10
                    r=clasher_core.BattleState(snapshot(b,cfg))
                    self.assertEqual(b.can_activate_champion_ability(seat),r.can_activate_champion_ability(seat))
                    before=b.next_entity_id
                    expected=b.activate_champion_ability(seat)
                    self.assertEqual(expected,souls>=20)
                    self.assertEqual(expected,r.activate_champion_ability(seat))
                    self.same(b,r)
                    if expected:self.assertEqual(b.next_entity_id-before,45)
                    self.assertEqual(mechanic.souls_collected,next(e for e in json.loads(r.snapshot())['entities'] if e['id']==actor.id)['souls_collected'])
                    self.continuation(b,cfg,100)
                    for _ in range(120):
                        b.step();r.step();self.same(b,r)
                        if actor.id in b.entities:
                            native=next(e for e in json.loads(r.snapshot())['entities'] if e['id']==actor.id)['champion']['ability']
                            self.assertEqual(mechanic.ability.is_active,native['active'])
                            self.assertEqual(mechanic.ability.elixir_cost,native['cost'])

    def test_golden_knight_has_no_oracle_ability(self):
        cards=('GoldenKnight','Knight','Zap','Archers');cfg=config(cards)
        b=initial(669561,cards=cards);b.players[0].elixir=10
        self.assertTrue(b.deploy_card(0,'GoldenKnight',Position(13.5,13.5)))
        for _ in range(25):b.step()
        r=clasher_core.BattleState(snapshot(b,cfg))
        self.assertFalse(b.can_activate_champion_ability(0))
        self.assertFalse(r.can_activate_champion_ability(0))
        self.assertFalse(b.activate_champion_ability(0))
        self.assertFalse(r.activate_champion_ability(0))
        self.same(b,r)
