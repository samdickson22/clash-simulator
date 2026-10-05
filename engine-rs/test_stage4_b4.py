"""B4 building and deploy-anywhere differential reductions."""

import unittest
import json
import clasher_core
import test_stage4
from differential import CARDS, Position, config, initial, snapshot
from stage2 import focused_case


class B4Regressions(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def test_piercing_ledger_excludes_underground_and_birth_immune_targets(self):
        from clasher.entities import Projectile

        cards = ("Miner", "Knight", "Zap", "Archers")
        cfg = config(cards)
        for mode in ("underground", "death_immunity"):
            with self.subTest(mode=mode):
                b = initial(cards=cards)
                b.deploy_card(0, "Knight", Position(4.5, 10.5))
                b.deploy_card(1, "Miner", Position(4.5, 13.5))
                miner = b.entities[8]
                miner.position = miner._underground_destination = Position(4.5, 13.5)
                miner._underground_travel_duration = 0.0
                miner.deploy_delay_remaining = miner.placement_delay_total = 0.05
                if mode == "death_immunity":
                    miner._underground_deployment = False
                    miner._special_move_active = False
                    miner._death_spawn_target_immunity_elapsed_ms = 0
                shot = Projectile(
                    id=b.next_entity_id,
                    position=Position(4.5, 13.5),
                    player_id=0,
                    card_stats=None,
                    hitpoints=1,
                    max_hitpoints=1,
                    damage=50,
                    range=0,
                    sight_range=0,
                    target_position=Position(4.5, 14.5),
                    travel_speed=0,
                    splash_radius=1,
                    pierces=True,
                    source_entity=b.entities[7],
                )
                shot.battle_state = b
                b.entities[shot.id] = shot
                b.next_entity_id += 1
                r = clasher_core.BattleState(snapshot(b, cfg))
                for tick in range(8):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    native_shot = next(
                        e
                        for e in json.loads(r.snapshot())["entities"]
                        if e["id"] == shot.id
                    )
                    self.assertEqual(shot.hit_entity_ids, set(native_shot["hit_ids"]))
                self.assertIn(miner.id, shot.hit_entity_ids)

    def test_miner_enemy_side_travel_immunity_crown_damage_and_imports(self):
        cards = ("Miner", "Zap", "Knight", "Archers")
        cfg = config(cards)
        for seat in (0, 1):
            for x in (0.5, 8.5, 17.5):
                with self.subTest(seat=seat, x=x):
                    b = initial(cards=cards)
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    y = 23.5 if seat == 0 else 8.5
                    self.assertTrue(b.deploy_card(seat, "Miner", Position(x, y)))
                    self.assertTrue(r.apply_action(seat, "Miner", x, y))
                    self.assert_same(b, r)
                    saw_surface = False
                    for t in range(200):
                        if t == 5:
                            miner = b.entities[7]
                            hp = miner.hitpoints
                            pos = miner.position
                            self.assertTrue(
                                b.deploy_card(1 - seat, "Zap", Position(pos.x, pos.y))
                            )
                            self.assertTrue(
                                r.apply_action(1 - seat, "Zap", pos.x, pos.y)
                            )
                        b.step()
                        r.step()
                        self.assert_same(b, r)
                        if t == 5:
                            self.assertEqual(b.entities[7].hitpoints, hp)
                            self.assertEqual(b.entities[7].stun_timer, 0)
                        if 7 in b.entities:
                            saw_surface |= not b.entities[7]._underground_deployment
                        if t in (1, 20, 35, 60):
                            copy = b.clone()
                            imported = clasher_core.BattleState(snapshot(b, cfg))
                            for _ in range(80):
                                copy.step()
                                imported.step()
                                self.assert_same(copy, imported)
                    self.assertTrue(saw_surface)
                    enemy_crowns = [
                        e
                        for e in b.entities.values()
                        if e.player_id != seat and type(e).__name__ == "Building"
                    ]
                    damage = sum(e.max_hitpoints - e.hitpoints for e in enemy_crowns)
                    self.assertGreater(damage, 0)
                    self.assertEqual(damage % 39, 0)

    def test_goblin_barrel_flight_formations_edges_and_imports(self):
        cards = ("GoblinBarrel",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            for x in (0.5, 4.5, 9.5, 17.5):
                with self.subTest(seat=seat, x=x):
                    b = initial(cards=cards)
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    y = 27.5 if seat == 0 else 4.5
                    self.assertTrue(b.deploy_card(seat, "GoblinBarrel", Position(x, y)))
                    self.assertTrue(r.apply_action(seat, "GoblinBarrel", x, y))
                    self.assert_same(b, r)
                    max_children = 0
                    for t in range(100):
                        b.step()
                        r.step()
                        self.assert_same(b, r)
                        max_children = max(
                            max_children,
                            sum(
                                type(e).__name__ == "Troop" for e in b.entities.values()
                            ),
                        )
                        if t in (5, 12, 20, 40):
                            copy = b.clone()
                            imported = clasher_core.BattleState(snapshot(b, cfg))
                            for _ in range(60):
                                copy.step()
                                imported.step()
                                self.assert_same(copy, imported)
                    self.assertEqual(max_children, 3)

    def test_death_bomb_blocks_troop_and_building_placement_until_expiry(self):
        cards = ("BombTower", "Knight", "Cannon", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "BombTower", Position(4.5, 12.5))
        b.entities[7].take_damage(b.entities[7].hitpoints)
        b.players[0].elixir = 10
        for card, x, y, accepted in (
            ("Knight", 4.5, 12.5, False),
            ("Cannon", 4.5, 12.5, False),
            ("Knight", 6.5, 12.5, True),
            ("Zap", 4.5, 12.5, True),
        ):
            with self.subTest(card=card, x=x):
                copy = b.clone()
                r = clasher_core.BattleState(snapshot(copy, cfg))
                self.assertEqual(copy.deploy_card(0, card, Position(x, y)), accepted)
                self.assertEqual(r.apply_action(0, card, x, y), accepted)
                self.assert_same(copy, r)
        for _ in range(60):
            b.step()
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.deploy_card(0, "Knight", Position(4.5, 12.5)))
        self.assertTrue(r.apply_action(0, "Knight", 4.5, 12.5))
        self.assert_same(b, r)

    def test_bomb_tower_lifetime_death_creates_delayed_bomb_and_imports(self):
        cards = ("BombTower",) + CARDS
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "BombTower", Position(4.5, 12.5))
        for _ in range(20):
            b.step()
        b.entities[7].hitpoints = 1
        r = clasher_core.BattleState(snapshot(b, cfg))
        seen = False
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)
            bombs = [
                e for e in b.entities.values() if type(e).__name__ == "TimedExplosive"
            ]
            if bombs and not seen:
                seen = True
                self.assertNotIn(7, b.entities)
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(80):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertTrue(seen)
        self.assertFalse(
            any(type(e).__name__ == "TimedExplosive" for e in b.entities.values())
        )

    def test_inferno_stages_stun_reset_and_live_import(self):
        cards = ("InfernoTower", "Giant", "Zap", "Knight")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "InfernoTower", Position(4.5, 13.5))
        b.deploy_card(1, "Giant", Position(4.5, 18.5))
        b.entities[7].hitpoints = b.entities[8].hitpoints = 100000
        r = clasher_core.BattleState(snapshot(b, cfg))
        stages = set()
        for t in range(250):
            if t == 140:
                b.players[1].elixir = 10
                # Reimport after the explicit fixture-only elixir write.
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.deploy_card(1, "Zap", Position(4.5, 13.5)))
                self.assertTrue(r.apply_action(1, "Zap", 4.5, 13.5))
            b.step()
            r.step()
            self.assert_same(b, r)
            stages.add(b.entities[7].damage)
            if t == 140:
                ramp = b.entities[7].mechanics[0]
                self.assertEqual(ramp._current_target_ms, 0)
                self.assertEqual(b.entities[7].damage, 43)
            if t in (60, 100, 145, 190):
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertEqual(stages, {43, 158, 847})

    def test_xbow_zero_first_hit_seeds_force_due_without_extra_work(self):
        result = focused_case("Xbow", 2, config((*CARDS, "Xbow")), ticks=77)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_xbow_does_not_acquire_crown_outside_attack_reach(self):
        result = focused_case("Xbow", 0, config((*CARDS, "Xbow")), ticks=247)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")


if __name__ == "__main__":
    unittest.main()
