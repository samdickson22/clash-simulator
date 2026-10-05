"""Reduced C56 differentials against the read-only Python reference."""

import unittest

import clasher_core
from differential import CARDS, Position, battle_digest, config, initial, snapshot


class Stage4Regressions(unittest.TestCase):
    def test_special_weapon_pending_lethal_retarget_keeps_in_range_hit_work(self):
        from stage2 import focused_case

        result = focused_case(
            "ElectroSpirit", 1, config((*CARDS, "ElectroSpirit")), ticks=1625
        )
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_electro_spirit_still_rejects_pending_lethal_targets(self):
        from stage2 import focused_case

        cards = (*CARDS, "ElectroSpirit")
        result = focused_case("ElectroSpirit", 0, config(cards), ticks=662)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def assert_same(self, battle, native):
        self.assertEqual(battle_digest(battle), native.digest(), f"tick {battle.tick}")
        words, index = native.rng_state()
        self.assertEqual(battle.rng.getstate()[1], tuple(words) + (index,))

    def test_barrel_spawns_child_and_ticks_its_deployment_on_expiry(self):
        cards = ("BarbLog",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                r = clasher_core.BattleState(snapshot(b, cfg))
                y = 10.5 if seat == 0 else 21.5
                self.assertTrue(b.deploy_card(seat, "BarbLog", Position(4.5, y)))
                self.assertTrue(r.apply_action(seat, "BarbLog", 4.5, y))
                for _ in range(100):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if b.tick in (16, 31, 32, 33, 50):
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        copy = b.clone()
                        for _ in range(30):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)

    def test_arrows_volley_rng_shared_hits_and_live_import(self):
        cards = ("Arrows",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(560401, cards=cards)
                r = clasher_core.BattleState(snapshot(b, cfg))
                y = 25.5 if seat == 0 else 6.5
                self.assertTrue(b.deploy_card(seat, "Arrows", Position(3.5, y)))
                self.assertTrue(r.apply_action(seat, "Arrows", 3.5, y))
                self.assertEqual(len(b.entities), 36)
                self.assert_same(b, r)
                for _ in range(100):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if b.tick in (2, 8, 20, 24):
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        copy = b.clone()
                        for _ in range(40):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)

    def test_lightning_ranked_strikes_keep_distinct_targets_after_import(self):
        cards = ("Lightning", "DarkPrince", "Knight", "Giant")
        cfg = config(cards)
        b = initial(560402, cards=cards)
        for player in b.players:
            player.elixir = 10
        self.assertTrue(b.deploy_card(1, "DarkPrince", Position(4.5, 22.5)))
        self.assertTrue(b.deploy_card(1, "Knight", Position(5.5, 22.5)))
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.deploy_card(0, "Lightning", Position(4.5, 23.5)))
        self.assertTrue(r.apply_action(0, "Lightning", 4.5, 23.5))
        self.assert_same(b, r)
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)
            if b.tick in (9, 10, 19, 28):
                imported = clasher_core.BattleState(snapshot(b, cfg))
                copy = b.clone()
                for _ in range(40):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)

    def test_delivery_delay_building_immunity_and_recruit_import(self):
        cards = ("RoyalDelivery",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                r = clasher_core.BattleState(snapshot(b, cfg))
                y = 10.5 if seat == 0 else 21.5
                self.assertTrue(b.deploy_card(seat, "RoyalDelivery", Position(4.5, y)))
                self.assertTrue(r.apply_action(seat, "RoyalDelivery", 4.5, y))
                for _ in range(130):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if b.tick in (1, 40, 41, 45):
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        copy = b.clone()
                        for _ in range(50):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)

    def test_area_damage_deadlines_overlapping_slows_and_import(self):
        cards = ("Poison", "Earthquake", "Knight", "Cannon")
        cfg = config(cards)
        b = initial(560403, cards=cards)
        for player in b.players:
            player.elixir = 10
        self.assertTrue(b.deploy_card(1, "Knight", Position(4.5, 22.5)))
        self.assertTrue(b.deploy_card(1, "Cannon", Position(6.5, 22.5)))
        r = clasher_core.BattleState(snapshot(b, cfg))
        for card in ("Poison", "Earthquake"):
            self.assertTrue(b.deploy_card(0, card, Position(4.5, 23.5)))
            self.assertTrue(r.apply_action(0, card, 4.5, 23.5))
        self.assert_same(b, r)
        for _ in range(200):
            b.step()
            r.step()
            self.assert_same(b, r)
            if b.tick in (4, 5, 19, 20, 25, 59, 159):
                imported = clasher_core.BattleState(snapshot(b, cfg))
                copy = b.clone()
                for _ in range(70):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)

    def test_tornado_retains_controlled_vectors_and_damage_phase_on_import(self):
        cards = ("Tornado", "Knight", "Goblins", "Cannon")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(560404, cards=cards)
                for player in b.players:
                    player.elixir = 10
                enemy = 1 - seat
                y = 22.5 if seat == 0 else 9.5
                self.assertTrue(b.deploy_card(enemy, "Knight", Position(4.5, y)))
                self.assertTrue(b.deploy_card(enemy, "Goblins", Position(5.5, y)))
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.deploy_card(seat, "Tornado", Position(7.5, y)))
                self.assertTrue(r.apply_action(seat, "Tornado", 7.5, y))
                for _ in range(100):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if b.tick in (1, 10, 12, 20):
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        copy = b.clone()
                        for _ in range(40):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)

    def test_electro_spirit_chain_and_mid_hop_import(self):
        cards = ("ElectroSpirit", "Goblins", "Knight", "Giant")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(560405, cards=cards)
                self.assertTrue(
                    b.deploy_card(
                        seat,
                        "ElectroSpirit",
                        Position(4.5, 13.5 if seat == 0 else 18.5),
                    )
                )
                self.assertTrue(
                    b.deploy_card(
                        1 - seat, "Goblins", Position(4.5, 18.5 if seat == 0 else 13.5)
                    )
                )
                r = clasher_core.BattleState(snapshot(b, cfg))
                chain_ticks = 0
                for _ in range(160):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if any(
                        type(e).__name__ == "ChainLightning"
                        for e in b.entities.values()
                    ):
                        chain_ticks += 1
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        copy = b.clone()
                        for _ in range(20):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertGreater(chain_ticks, 0)


if __name__ == "__main__":
    unittest.main()
