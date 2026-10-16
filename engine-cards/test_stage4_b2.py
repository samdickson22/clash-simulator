"""B2 reductions for air movement and splash mechanics."""

from test_stage4 import Stage4Regressions
from differential import CARDS, ES, ROOT, Position, config, initial, snapshot
import clasher_core
import unittest


class B2Regressions(unittest.TestCase):
    assert_same = Stage4Regressions.assert_same

    def test_special_windup_survives_first_distant_lock_after_freeze(self):
        cards = ("Valkyrie", "Knight", "Zap", "IceSpirit")
        cfg = config(cards)
        for card in ("Valkyrie", "Knight"):
            with self.subTest(card=card):
                b = initial(cards=cards)
                b._spawn_unit_at_position(
                    Position(4.5, 13.5),
                    0,
                    b.card_loader.get_card(card),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                b._spawn_unit_at_position(
                    Position(4.5, 15),
                    1,
                    b.card_loader.get_card("Knight"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                b.step()
                actor, enemy = b.entities[7], b.entities[8]
                self.assertTrue(actor._attack_windup_active)
                actor.apply_stun(0.2, source_kind="IceSpirit", interrupt_combat=False)
                enemy.position = Position(4.5, 18.5)
                r = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(20):
                    b.step()
                    r.step()
                    self.assert_same(b, r)

    def test_pending_retarget_uses_prior_completed_attack_latch(self):
        from clasher.entities import Projectile
        import json

        for completed in (False, True):
            cards = ("Firecracker", "Knight", "Archers", "Giant")
            b = initial(560415, cards=cards)
            b.deploy_card(0, "Firecracker", Position(4.5, 13.5))
            b.deploy_card(1, "Knight", Position(4.5, 18.5))
            old = b.entities[8]
            old.position = Position(4.5, 25.0)
            old.hitpoints = 1
            b._spawn_unit_at_position(
                Position(4.5, 14.5),
                1,
                b.card_loader.get_card("Knight"),
                deploy_delay_override=0,
                snap_to_valid=False,
            )
            e = b.entities[7]
            e.deploy_delay_remaining = 0
            e.target_id = e._last_combat_target_id = 8
            e.attack_cooldown = 0.05
            e._attack_windup_active = e._has_attacked_once = True
            e._has_attacked_current_target = completed
            shot = Projectile(
                id=b.next_entity_id,
                position=Position(4.5, 24.5),
                player_id=0,
                card_stats=b.entities[1].card_stats,
                hitpoints=1,
                max_hitpoints=1,
                damage=109,
                range=0,
                sight_range=0,
                target_position=old.position,
                primary_target=old,
                travel_speed=20,
            )
            b.entities[shot.id] = shot
            b.next_entity_id += 1
            r = clasher_core.BattleState(snapshot(b, config(cards)))
            b.step()
            r.step()
            self.assert_same(b, r)
            self.assertAlmostEqual(e.attack_cooldown, 0.6 if completed else 3.0)
            native = next(
                v for v in json.loads(r.snapshot())["entities"] if v["id"] == 7
            )
            self.assertEqual(float(e.attack_cooldown).hex(), native["cooldown"].hex())

    def test_air_knockback_does_not_recover_ground_at_river(self):
        from stage4_matches import BUNDLES, PILOT, match
        from clasher.rl.contract_v5 import ContractV5ObservationBuilder

        cfg = config(tuple(dict.fromkeys((*PILOT, *BUNDLES["B1"], *BUNDLES["B2"]))))
        result = match("B2", 11, cfg, ContractV5ObservationBuilder(), ticks=148)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_special_weapon_retarget_in_reach_restores_retarget_delay(self):
        cards = ("Firecracker", "Knight", "Archers", "Giant")
        b = initial(560414, cards=cards)
        b.deploy_card(0, "Firecracker", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        b.entities[8].position = Position(4.5, 25.0)
        b._spawn_unit_at_position(
            Position(4.5, 14.5),
            1,
            b.card_loader.get_card("Knight"),
            deploy_delay_override=0,
            snap_to_valid=False,
        )
        e = b.entities[7]
        e.deploy_delay_remaining = 0
        e.target_id = e._last_combat_target_id = 8
        e.attack_cooldown = 0.05
        e._attack_windup_active = e._has_attacked_once = True
        r = clasher_core.BattleState(snapshot(b, config(cards)))
        for _ in range(20):
            b.step()
            r.step()
            self.assert_same(b, r)

    def test_rocket_resets_special_weapon_load_and_imports_blocked_preload(self):
        cards = ("Valkyrie", "Rocket", "Knight", "Archers")
        cfg = config(cards)
        b = initial(560413, cards=cards)
        for player in b.players:
            player.elixir = 10
        b.deploy_card(0, "Valkyrie", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        b.deploy_card(1, "Rocket", Position(4.5, 13.5))
        r = clasher_core.BattleState(snapshot(b, cfg))
        imports = 0
        for _ in range(180):
            b.step()
            r.step()
            self.assert_same(b, r)
            if imports < 5 and any(
                e._attack_preload_blocked for e in b.entities.values()
            ):
                imports += 1
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(50):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertGreater(imports, 0)

    def test_visible_distance_tie_retains_current_crown_while_walking(self):
        cards = ("Firecracker", "Princess", "Knight", "Archers")
        b = initial(560412, cards=cards)
        b.deploy_card(0, "Princess", Position(13.5, 10.5))
        b.deploy_card(1, "Firecracker", Position(13.5, 21.5))
        b.entities[7].position = Position(16.5, 6.5)
        e = b.entities[8]
        e.position = Position(15.5, 14.476)
        e.deploy_delay_remaining = 0
        e.target_id = e._last_combat_target_id = 2
        r = clasher_core.BattleState(snapshot(b, config(cards)))
        b.step()
        r.step()
        self.assertEqual(e.target_id, 2)
        self.assert_same(b, r)

    def test_depleted_target_competes_with_visible_alternatives(self):
        for tower_y in (25.5, 31.5):
            cards = ("Knight", "Firecracker", "Archers", "Giant")
            b = initial(560411, cards=cards)
            for player in b.players:
                player.elixir = 10
            b.deploy_card(0, "Knight", Position(4.5, 13.5))
            b.deploy_card(1, "Knight", Position(4.5, 18.5))
            b.deploy_card(0, "Firecracker", Position(4.5, 10.5))
            for e in list(b.entities.values())[6:]:
                e.deploy_delay_remaining = 0
            b.entities[4].position.y = tower_y
            b.entities[7].attack_cooldown = 0
            b.entities[8].position = Position(4.5, 14.0)
            b.entities[8].hitpoints = 1
            e = b.entities[9]
            e.position = Position(4.5, 21.6)
            e.target_id = e._last_combat_target_id = 8
            e._attack_windup_active = e._has_attacked_once = (
                e._has_attacked_current_target
            ) = True
            e.attack_cooldown = 2.9
            r = clasher_core.BattleState(snapshot(b, config(cards)))
            for _ in range(8):
                b.step()
                r.step()
                self.assert_same(b, r)
                if b.tick == 1:
                    self.assertEqual(
                        b.entities[9].target_id, 4 if tower_y == 25.5 else None
                    )

    def test_stun_resets_special_clock_but_preserves_frozen_target_observation(self):
        import cloudpickle
        import hashlib
        import json

        source_hashes = json.loads((ES / "stage4/start_sources.json").read_text())[
            "hashes"
        ]
        for name, expected in source_hashes.items():
            if name == "gamedata.json" or name.startswith("src/clasher/"):
                self.assertEqual(
                    hashlib.sha256((ROOT / name).read_bytes()).hexdigest(),
                    expected,
                    "regenerate saved root after Python/data drift: " + name,
                )
        b, cfg = cloudpickle.loads((ES / "stage4/b2_case2_root800.pkl").read_bytes())
        r = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)

    def test_live_import_accepts_saved_flying_stop_route(self):
        cards = ("BabyDragon",) + CARDS
        cfg = config(cards)
        b = initial(560410, cards=cards)
        b.deploy_card(0, "BabyDragon", Position(4.5, 13.5))
        r = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(500):
            b.step()
            r.step()
            self.assert_same(b, r)
            if any(
                getattr(e, "_native_frozen_stop_route", None) is not None
                for e in b.entities.values()
                if e.is_air_unit
            ):
                imported = clasher_core.BattleState(snapshot(b, cfg))
                copy = b.clone()
                for _ in range(100):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
                return
        self.fail("fixture did not exercise a saved flying stop route")

    def test_finish_expiry_clears_special_weapon_target_memory(self):
        import json

        cards = ("Firecracker", "Goblins", "Knight", "Archers")
        b = initial(560409, cards=cards)
        for player in b.players:
            player.elixir = 10
        b.deploy_card(0, "Firecracker", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        b.deploy_card(1, "Goblins", Position(4.5, 18.5))
        r = clasher_core.BattleState(snapshot(b, config(cards)))
        for _ in range(45):
            b.step()
            r.step()
            self.assert_same(b, r)
        self.assertIsNone(b.entities[7]._last_combat_target_id)
        e = next(e for e in json.loads(r.snapshot())["entities"] if e["id"] == 7)
        self.assertIsNone(e["last_target"])

    def test_balloon_death_bomb_birth_countdown_and_live_import(self):
        cards = ("Balloon", "Archers", "Musketeer", "Knight")
        cfg = config(cards)
        b = initial(560408, cards=cards)
        for player in b.players:
            player.elixir = 10
        self.assertTrue(b.deploy_card(0, "Balloon", Position(4.5, 13.5)))
        self.assertTrue(b.deploy_card(1, "Musketeer", Position(4.5, 18.5)))
        self.assertTrue(b.deploy_card(1, "Archers", Position(4.5, 18.5)))
        r = clasher_core.BattleState(snapshot(b, cfg))
        imports = 0
        for _ in range(700):
            b.step()
            r.step()
            self.assert_same(b, r)
            if imports < 5 and any(
                type(e).__name__ == "TimedExplosive" for e in b.entities.values()
            ):
                imports += 1
                imported = clasher_core.BattleState(snapshot(b, cfg))
                copy = b.clone()
                for _ in range(80):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertGreater(imports, 0)

    def test_firecracker_recoil_child_rays_and_hit_ledgers_on_import(self):
        cards = ("Firecracker", "Goblins", "Knight", "Archers")
        cfg = config(cards)
        for seat in (0, 1):
            b = initial(560409, cards=cards)
            for player in b.players:
                player.elixir = 10
            own_y, enemy_y = (13.5, 18.5) if seat == 0 else (18.5, 13.5)
            self.assertTrue(b.deploy_card(seat, "Firecracker", Position(4.5, own_y)))
            self.assertTrue(b.deploy_card(1 - seat, "Knight", Position(4.5, enemy_y)))
            self.assertTrue(b.deploy_card(1 - seat, "Goblins", Position(4.5, enemy_y)))
            r = clasher_core.BattleState(snapshot(b, cfg))
            imports = 0
            for _ in range(400):
                b.step()
                r.step()
                self.assert_same(b, r)
                if imports < 5 and any(
                    getattr(e, "pierces", False) for e in b.entities.values()
                ):
                    imports += 1
                    imported = clasher_core.BattleState(snapshot(b, cfg))
                    copy = b.clone()
                    for _ in range(40):
                        copy.step()
                        imported.step()
                        self.assert_same(copy, imported)
            self.assertGreater(imports, 0)

    def test_princess_nonhoming_shot_keeps_endpoint_and_no_reservation(self):
        from stage2 import focused_case

        result = focused_case("Princess", 0, config((*CARDS, "Princess")), ticks=148)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_special_weapon_finishes_passive_load_on_arrival_from_movement(self):
        from stage2 import focused_case

        result = focused_case("Princess", 1, config((*CARDS, "Princess")), ticks=1220)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_started_projectile_cycle_uses_keep_reach_after_movement(self):
        from stage2 import focused_case

        result = focused_case("Princess", 2, config((*CARDS, "Princess")), ticks=1186)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_override_finish_card_reacquires_immediately_after_target_removal(self):
        from stage2 import focused_case

        result = focused_case("Valkyrie", 0, config((*CARDS, "Valkyrie")), ticks=721)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_special_troop_target_removal_does_not_grant_idle_preload(self):
        from stage2 import focused_case

        result = focused_case("Valkyrie", 0, config((*CARDS, "Valkyrie")), ticks=1252)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_five_and_six_body_formations_do_not_mirror_on_right_lane(self):
        for card in ("Bats", "MinionHorde"):
            cards = (card,) + CARDS
            cfg = config(cards)
            for seat in (0, 1):
                b = initial(cards=cards)
                r = clasher_core.BattleState(snapshot(b, cfg))
                y = 10.5 if seat == 0 else 21.5
                self.assertTrue(b.deploy_card(seat, card, Position(13.5, y)))
                self.assertTrue(r.apply_action(seat, card, 13.5, y))
                self.assert_same(b, r)

    def test_air_formation_single_node_routes_and_live_import(self):
        cards = ("Minions",) + CARDS
        cfg = config(cards)
        b = initial(560406, cards=cards)
        r = clasher_core.BattleState(snapshot(b, cfg))
        for seat in (0, 1):
            x, y = (4.5, 13.5) if seat == 0 else (13.5, 18.5)
            self.assertTrue(b.deploy_card(seat, "Minions", Position(x, y)))
            self.assertTrue(r.apply_action(seat, "Minions", x, y))
            self.assert_same(b, r)
        for _ in range(700):
            b.step()
            r.step()
            self.assert_same(b, r)
            if b.tick in (20, 21, 50, 100, 200):
                imported = clasher_core.BattleState(snapshot(b, cfg))
                copy = b.clone()
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)

    def test_projectile_splash_and_import_against_clustered_swarm(self):
        for card in ("BabyDragon", "Wizard"):
            cards = (card, "Goblins", "Skeletons", "Giant")
            cfg = config(cards)
            b = initial(560407, cards=cards)
            for player in b.players:
                player.elixir = 10
            self.assertTrue(b.deploy_card(0, card, Position(4.5, 13.5)))
            self.assertTrue(b.deploy_card(1, "Goblins", Position(4.5, 18.5)))
            self.assertTrue(b.deploy_card(1, "Skeletons", Position(4.5, 18.5)))
            r = clasher_core.BattleState(snapshot(b, cfg))
            imported_ticks = 0
            for _ in range(350):
                b.step()
                r.step()
                self.assert_same(b, r)
                if imported_ticks < 5 and any(
                    type(e).__name__ == "Projectile" and e.splash_radius > 0
                    for e in b.entities.values()
                ):
                    imported_ticks += 1
                    imported = clasher_core.BattleState(snapshot(b, cfg))
                    copy = b.clone()
                    for _ in range(40):
                        copy.step()
                        imported.step()
                        self.assert_same(copy, imported)
            self.assertGreater(imported_ticks, 0)


if __name__ == "__main__":
    unittest.main()
