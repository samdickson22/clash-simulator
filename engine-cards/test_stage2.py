"""Stage 2 root-cause regression trajectories against the Python reference."""

import unittest
from differential import CARDS, config
from stage2 import focused_case


class Stage2Parity(unittest.TestCase):
    def test_friendly_crown_removal_refreshes_retained_route_heading(self):
        result = focused_case("Skeletons", 3, config((*CARDS, "Skeletons")), ticks=700)
        self.assertTrue(
            result["ok"],
            f"first mismatch at {result.get('tick')}: {result.get('field_diff')}",
        )

    def test_completed_hit_then_movement_does_not_install_finish_on_removal(self):
        result = focused_case("Goblins", 3, config((*CARDS, "Goblins")), ticks=2050)
        self.assertTrue(
            result["ok"],
            f"first mismatch at {result.get('tick')}: {result.get('field_diff')}",
        )

    def test_ordinary_building_does_not_receive_crown_sight_bonus(self):
        result = focused_case("Cannon", 0, config((*CARDS, "Cannon")), ticks=142)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_troop_anchor_relocates_around_live_cannon(self):
        result = focused_case("Cannon", 0, config((*CARDS, "Cannon")), ticks=401)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_avoidance_normalizes_retained_heading_once(self):
        result = focused_case("Tesla", 0, config((*CARDS, "Tesla")), ticks=844)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_center_swarm_children_keep_their_own_lane(self):
        result = focused_case("HogRider", 6, config((*CARDS, "HogRider")), ticks=262)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_backward_walking_retains_distant_target_without_visible_alternative(self):
        result = focused_case("HogRider", 6, config((*CARDS, "HogRider")), ticks=1617)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_king_activation_does_not_bank_extra_interval_work(self):
        result = focused_case("IceGolem", 0, config((*CARDS, "IceGolem")), ticks=752)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_new_homing_shot_keeps_removed_targets_final_position(self):
        result = focused_case("IceGolem", 6, config((*CARDS, "IceGolem")), ticks=691)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_spirit_launch_releases_character_locks_at_cleanup(self):
        result = focused_case("IceSpirit", 0, config((*CARDS, "IceSpirit")), ticks=90)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_committed_hit_discards_payload_after_target_escapes(self):
        from stage2_matches import match, PILOT, resources

        result = match(1, config(PILOT), resources(), until=1459)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_frozen_walker_consumes_reached_route_node_without_travel(self):
        from stage2_matches import match, PILOT, resources

        result = match(3, config(PILOT), resources(), until=1798)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_overtime_hand_refill_uses_350ms(self):
        import json, clasher_core
        from differential import initial, snapshot, battle_digest

        b = initial()
        b.tick = 4799
        b.time = 239.95
        p = b.players[0]
        for slot in (0, 1):
            p.cycle_queue.append(p.hand[slot])
            p.hand[slot] = None
        r = clasher_core.BattleState(snapshot(b, config()))
        for _ in range(8):
            b.step()
            r.step()
            self.assertEqual(
                p.next_card_refill_cooldown_ms,
                json.loads(r.snapshot())["players"][0]["refill"],
            )
            self.assertEqual(battle_digest(b), r.digest())

    def test_stunned_deployment_decays_avoidance_without_scanning(self):
        from stage2_matches import match, PILOT, resources

        result = match(4, config(PILOT), resources(), until=112)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_deployment_expiry_enters_frozen_walking_state(self):
        from stage2_matches import match, PILOT, resources

        result = match(4, config(PILOT), resources(), until=128)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_deployment_body_pressure_clips_adjacent_river_cells(self):
        from stage2_matches import match, PILOT, resources

        result = match(4, config(PILOT), resources(), until=131)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_swarm_child_spawns_clamp_to_quarter_tile_boundary(self):
        from stage2_matches import match, PILOT, resources

        result = match(4, config(PILOT), resources(), until=286)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_moving_bodies_can_leave_quarter_tile_spawn_margin(self):
        import clasher_core
        from differential import initial, snapshot, battle_digest, Position

        cards = ("Skeletons", "Knight", "Archers", "Giant")
        b = initial(cards=cards)
        r = clasher_core.BattleState(snapshot(b, config(cards)))
        self.assertTrue(b.deploy_card(0, "Skeletons", Position(17.5, 7.5)))
        self.assertTrue(r.apply_action(0, "Skeletons", 17.5, 7.5))
        self.assertEqual(battle_digest(b), r.digest())
        b.step()
        r.step()
        self.assertGreater(max(e.position.x for e in b.entities.values()), 17.75)
        self.assertEqual(battle_digest(b), r.digest())

    def test_relocated_swarm_clips_to_column_forward_deploy_edge(self):
        from stage2_matches import match, PILOT, resources

        result = match(4, config(PILOT), resources(), until=2661)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_idle_cannon_clears_hit_timeline_but_preserves_load(self):
        from stage2_matches import match, PILOT, resources

        result = match(12, config(PILOT), resources(), until=4092)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_homing_impact_respects_tesla_hidden_state(self):
        from stage2_matches import match, PILOT, resources

        result = match(62, config(PILOT), resources(), until=2291)
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_live_import_preserves_post_spend_float_bits(self):
        import json, clasher_core
        from differential import initial, snapshot, battle_digest, Position

        b = initial()
        b.players[0].elixir = 3.01
        self.assertTrue(b.deploy_card(0, "Knight", Position(4.5, 10.5)))
        r = clasher_core.BattleState(snapshot(b, config()))
        self.assertEqual(
            b.players[0].elixir.hex(),
            json.loads(r.snapshot())["players"][0]["elixir"].hex(),
        )
        self.assertEqual(battle_digest(b), r.digest())

    def test_spirit_keeps_cached_endpoint_when_target_dies_on_launch_frame(self):
        import clasher_core
        from differential import initial, snapshot, battle_digest, Position

        cards = ("IceSpirit", "Giant", "Fireball", "Knight")
        b = initial(33, cards=cards)
        b.tick = 40
        b.time = 2.0
        for p in b.players:
            p.elixir = 10
        b.deploy_card(0, "IceSpirit", Position(4.5, 10.5))
        b.deploy_card(1, "Giant", Position(4.5, 21.5))
        s, g = b.entities[7], b.entities[8]
        s.position = Position(4.5, 13)
        g.position = Position(5, 14.5)
        for e in (s, g):
            e.deploy_delay_remaining = 0
            e.spawn_stagger_remaining = 0
            e._native_deployed_elapsed_ms = 1000
        s.attack_cooldown = 0
        g.hitpoints = 1
        b.resolve_card_play(0, "Fireball")[2].cast(b, 0, Position(5, 14.5))
        b.entities[9].position = Position(5, 14.49)
        r = clasher_core.BattleState(snapshot(b, config(cards)))
        for _ in range(6):
            b.step()
            r.step()
            self.assertEqual(battle_digest(b), r.digest())

    def test_frozen_stop_route_variants_and_live_import(self):
        import importlib.util
        import clasher_core
        from differential import ROOT, Position, snapshot, battle_digest
        from stage2_matches import PILOT
        from clasher.data import CardDataLoader

        spec = importlib.util.spec_from_file_location(
            "frozen_stop_reference", ROOT / "tests/test_native_frozen_stop_route.py"
        )
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        cfg = config(PILOT)
        for fast in (False, True):
            for name, case in reference.CASE["variants"].items():
                with self.subTest(fast=fast, variant=name):
                    b = reference._battle(CardDataLoader(), fast)
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    commands = {}
                    for c in case["commands"]:
                        commands.setdefault(c["tick"], []).append(c)
                    imported = None
                    for _ in range(max(row[0] for row in case["giant"])):
                        for c in commands.get(b.tick, []):
                            accepted = b.deploy_card(
                                c["owner"], c["card"], Position(*c["xy"])
                            )
                            self.assertEqual(
                                accepted,
                                r.apply_action(c["owner"], c["card"], *c["xy"]),
                            )
                            if imported is not None:
                                self.assertEqual(
                                    accepted,
                                    imported.apply_action(
                                        c["owner"], c["card"], *c["xy"]
                                    ),
                                )
                        b.step()
                        r.step()
                        self.assertEqual(battle_digest(b), r.digest(), (name, b.tick))
                        if imported is not None:
                            imported.step()
                            self.assertEqual(
                                battle_digest(b),
                                imported.digest(),
                                (name, b.tick, "imported"),
                            )
                        if imported is None and any(
                            (getattr(e, "_native_frozen_stop_route", None) or {}).get(
                                "resumable"
                            )
                            for e in b.entities.values()
                        ):
                            imported = clasher_core.BattleState(snapshot(b, cfg))
                            self.assertEqual(battle_digest(b), imported.digest())
                    if name == "control_no_goblins":
                        self.assertIsNotNone(imported)


if __name__ == "__main__":
    unittest.main()
