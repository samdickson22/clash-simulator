"""Repaired opponent-scope mechanics against the read-only Python engine."""

import unittest
import clasher_core
import test_stage4
from differential import Position, config, initial, snapshot


class ScopeRegressions(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def test_firecracker_child_rays_drop_source_and_hit_new_drill_children(self):
        cards = ("Firecracker", "GoblinDrill", "Knight", "Archers")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "Firecracker", Position(4.5, 13.5))
        b.deploy_card(1, "GoblinDrill", Position(4.5, 18.5))
        drill = b.entities[8]
        r = clasher_core.BattleState(snapshot(b, cfg))
        witnessed = False
        for _ in range(240):
            carriers = [
                e
                for e in b.entities.values()
                if type(e).__name__ == "Projectile"
                and e.player_id == 0
                and not e.pierces
                and getattr(e.primary_target, "id", None) == drill.id
                and e._reaches_target_this_update(0.05)
            ]
            if carriers:
                drill.hitpoints = 1
                before_id = b.next_entity_id
                r = clasher_core.BattleState(snapshot(b, cfg))
                b.step()
                r.step()
                self.assert_same(b, r)
                children = [
                    e
                    for e in b.entities.values()
                    if type(e).__name__ == "Projectile"
                    and e.player_id == 0
                    and e.pierces
                ]
                self.assertTrue(children)
                self.assertTrue(all(e.source_entity is None for e in children))
                self.assertTrue(
                    any(id >= before_id for e in children for id in e.hit_entity_ids)
                )
                for _ in range(40):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                witnessed = True
                break
            b.step()
            r.step()
            self.assert_same(b, r)
        self.assertTrue(witnessed)

    def test_nonattacking_producers_do_not_target_contacting_ground_troops(self):
        for card in ("Elixir Collector", "GoblinDrill"):
            with self.subTest(card=card):
                cards = (card, "Skeletons", "Knight", "Archers")
                cfg = config(cards)
                b = initial(cards=cards)
                b.deploy_card(0, card, Position(9.5, 13.5))
                parent = b.entities[7]
                while parent.deploy_delay_remaining > 0:
                    b.step()
                self.assertFalse(parent._can_attack_ground())
                b.deploy_card(1, "Skeletons", Position(9.5, 18.5))
                enemy = next(
                    e
                    for e in b.entities.values()
                    if type(e).__name__ == "Troop" and e.player_id == 1
                )
                enemy.position = Position(parent.position.x + 0.25, parent.position.y)
                r = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(5):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    self.assertIsNone(parent.target_id)

    def test_drill_transport_emergence_production_death_and_import(self):
        cards = ("GoblinDrill", "Knight", "Vines", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                y = 18.5 if seat == 0 else 14.5
                enemy_y = 19.5 if seat == 0 else 12.5
                b.deploy_card(1 - seat, "Knight", Position(9.5, enemy_y))
                knight = b.entities[7]
                knight.apply_stun(20)
                hp = knight.hitpoints
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.deploy_card(seat, "GoblinDrill", Position(9.5, y)))
                self.assertTrue(r.apply_action(seat, "GoblinDrill", 9.5, y))
                drill = b.entities[8]
                self.assertTrue(drill._underground_deployment)
                spawner = next(
                    m for m in drill.mechanics if type(m).__name__ == "PeriodicSpawner"
                )
                emerged = False
                seen = set()
                waves = []
                death_children = 0
                for t in range(360):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if not emerged and drill.deploy_delay_remaining == 0:
                        emerged = True
                        self.assertEqual(
                            hp - knight.hitpoints,
                            cfg["spawn_areas"]["GoblinDrill"]["scope"]["damage"],
                        )
                    new = [
                        e
                        for e in b.entities.values()
                        if getattr(e.card_stats, "name", None) == "Goblin"
                        and e.id not in seen
                    ]
                    for e in new:
                        seen.add(e.id)
                    if new:
                        if drill.is_alive:
                            self.assertEqual(len(new), 1)
                            waves.append(b.tick)
                        else:
                            death_children += len(new)
                    if t in (1, 20, 60, 85, 110, 180, 260, 285):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(100):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertTrue(emerged)
                self.assertFalse(drill.is_alive)
                self.assertGreaterEqual(len(waves), 2)
                self.assertTrue(all(b - a == 60 for a, b in zip(waves, waves[1:])))
                self.assertEqual(death_children, 2)
                self.assertEqual(len(seen), spawner.spawns_created + 2)

    def test_drill_delayed_death_children_do_not_inherit_freeze(self):
        cards = ("GoblinDrill", "Vines", "Knight", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "GoblinDrill", Position(9.5, 18.5))
        drill = b.entities[7]
        while drill.deploy_delay_remaining > 0:
            b.step()
        b.deploy_card(1, "Vines", Position(drill.position.x, drill.position.y))
        for _ in range(20):
            b.step()
        self.assertGreater(drill.freeze_expiry_time, b.time)
        self.assertGreater(drill.stun_timer, 0)
        drill.hitpoints = 1
        r = clasher_core.BattleState(snapshot(b, cfg))
        b.step()
        r.step()
        self.assert_same(b, r)
        children = [
            e
            for e in b.entities.values()
            if getattr(e.card_stats, "name", None) == "Goblin"
        ]
        self.assertEqual(len(children), 2)
        self.assertTrue(
            all(
                e.deploy_delay_remaining > 0
                and e.stun_timer == 0
                and e.freeze_expiry_time == 0
                for e in children
            )
        )
        copy = b.clone()
        imported = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)
            copy.step()
            imported.step()
            self.assert_same(copy, imported)

    def test_collector_production_cap_spawn_slow_freeze_and_zap_import(self):
        cards = ("Elixir Collector", "Vines", "Zap", "Knight")
        cfg = config(cards)
        for mode, expected in (("plain", 1), ("zap", 1), ("freeze", 40), ("slow", 2)):
            with self.subTest(mode=mode):
                b = initial(cards=cards)
                b.players[0].elixir = 10
                b.deploy_card(0, "Elixir Collector", Position(4.5, 10.5))
                for _ in range(20):
                    b.step()
                collector = b.entities[7]
                mechanic = next(
                    m
                    for m in collector.mechanics
                    if type(m).__name__ == "ElixirProduction"
                )
                mechanic._elapsed_ms = 12950
                b.players[0].elixir = 5
                if mode == "zap":
                    collector.apply_stun(0.5)
                if mode == "freeze":
                    collector.inherit_freeze_until(b.time + 2, b.time)
                if mode == "slow":
                    collector.apply_slow(2, 0.7)
                r = clasher_core.BattleState(snapshot(b, cfg))
                gains = []
                for t in range(60):
                    before = b.players[0].elixir
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if b.players[0].elixir - before > 0.9:
                        gains.append(t + 1)
                    if t in (0, 20, 38, 40):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(60):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertEqual(gains, [expected])
                mechanic._elapsed_ms = 12950
                b.players[0].elixir = 9.99
                r = clasher_core.BattleState(snapshot(b, cfg))
                b.step()
                r.step()
                self.assert_same(b, r)
                self.assertEqual(b.players[0].elixir, 10)
                self.assertEqual(mechanic._elapsed_ms, 0)

    def test_collector_death_payout_during_deploy_and_lifetime_expiry(self):
        cards = ("Elixir Collector", "Zap", "Knight", "Archers")
        cfg = config(cards)
        for mode in ("combat", "lifetime"):
            with self.subTest(mode=mode):
                b = initial(cards=cards)
                b.deploy_card(0, "Elixir Collector", Position(4.5, 10.5))
                if mode == "lifetime":
                    for _ in range(20):
                        b.step()
                b.entities[7].hitpoints = 1
                if mode == "lifetime":
                    b.entities[7].lifetime_decay_work = 99
                b.players[0].elixir = 5
                r = clasher_core.BattleState(snapshot(b, cfg))
                if mode == "combat":
                    self.assertTrue(b.deploy_card(1, "Zap", Position(4.5, 10.5)))
                    self.assertTrue(r.apply_action(1, "Zap", 4.5, 10.5))
                b.step()
                r.step()
                self.assert_same(b, r)
                self.assertNotIn(7, b.entities)
                self.assertAlmostEqual(b.players[0].elixir, 6.0178)

    def test_heal_spirit_snapshot_recipients_departure_arrival_and_import(self):
        cards = ("Heal", "Knight", "Archers", "Giant")
        cfg = config(cards)
        b = initial(cards=cards)
        b.players[0].elixir = 10
        b.deploy_card(0, "Knight", Position(4.5, 13.5))
        knight = b.entities[7]
        knight.hitpoints = 100
        b.deploy_card(0, "Archers", Position(13.5, 8.5))
        archers = [
            e
            for e in b.entities.values()
            if getattr(e.card_stats, "name", None) == "Archer"
        ]
        self.assertEqual(len(archers), 2)
        for archer in archers:
            archer.hitpoints = 1
            archer.apply_stun(10)
        b.deploy_card(1, "Giant", Position(4.5, 18.5))
        for _ in range(60):
            b.step()
        b.deploy_card(0, "Heal", Position(4.5, 13.5))
        r = clasher_core.BattleState(snapshot(b, cfg))
        pulse_seen = False
        imports = 0
        heals = 0
        for t in range(220):
            b.step()
            r.step()
            self.assert_same(b, r)
            pulse = next(
                (e for e in b.entities.values() if type(e).__name__ == "HealPulse"),
                None,
            )
            if pulse and not pulse_seen:
                pulse_seen = True
                self.assertIn(knight, pulse.recipients)
                self.assertFalse(any(e in pulse.recipients for e in archers))
                self.assertEqual(pulse.ticks_done, 0)
                hp_before = knight.hitpoints
                heals = pulse.heal_per_tick * 4
                knight.position = Position(13.5, 13.5)
                for archer in archers:
                    archer.position = Position(pulse.position.x, pulse.position.y)
                r = clasher_core.BattleState(snapshot(b, cfg))
            if imports < 6 and (
                pulse is not None
                or any(
                    getattr(e, "_self_projectile_launched", False)
                    for e in b.entities.values()
                )
            ):
                imports += 1
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
            if pulse_seen and pulse is None:
                self.assertEqual(knight.hitpoints, hp_before + heals)
                self.assertTrue(all(e.hitpoints <= 1 for e in archers))
                break
        self.assertTrue(pulse_seen)
        self.assertGreater(imports, 0)

    def test_curse_late_death_references_conversions_river_snap_and_import(self):
        cards = ("GoblinCurse", "Fireball", "Knight", "Bats")
        cfg = config(cards)
        for seat in (0, 1):
            for card, count in (("Knight", 1), ("Bats", 5)):
                with self.subTest(seat=seat, card=card):
                    b = initial(cards=cards)
                    y = 18.5 if seat == 0 else 13.5
                    b.deploy_card(1 - seat, card, Position(4.5, y))
                    for _ in range(20):
                        b.step()
                    targets = [
                        e for e in b.entities.values() if type(e).__name__ == "Troop"
                    ]
                    x, y = (9.0, 16.0) if card == "Bats" else (4.5, y)
                    for e in targets:
                        e.hitpoints = 100
                        e.position = Position(x, y)
                        e.apply_stun(5)
                    b.players[seat].elixir = 10
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    self.assertTrue(b.deploy_card(seat, "GoblinCurse", Position(x, y)))
                    self.assertTrue(r.apply_action(seat, "GoblinCurse", x, y))
                    converted = set()
                    late_imports = 0
                    bank_conversions = 0
                    for t in range(150):
                        if t == 4:
                            self.assertTrue(
                                b.deploy_card(seat, "Fireball", Position(x, y))
                            )
                            self.assertTrue(r.apply_action(seat, "Fireball", x, y))
                        b.step()
                        r.step()
                        self.assert_same(b, r)
                        for e in b.entities.values():
                            if (
                                e.player_id == seat
                                and getattr(e.card_stats, "name", None) == "Goblin"
                            ):
                                if e.id not in converted and card == "Bats":
                                    bank_conversions += e.position.y == (
                                        14.5 if seat == 0 else 17.5
                                    )
                                converted.add(e.id)
                        late = any(
                            type(e).__name__ == "GoblinCurseArea"
                            and any(
                                not target.is_alive and target.id not in b.entities
                                for target, expiry in e.cursed.values()
                            )
                            for e in b.entities.values()
                        )
                        if late:
                            late_imports += 1
                            copy = b.clone()
                            imported = clasher_core.BattleState(snapshot(b, cfg))
                            for _ in range(60):
                                copy.step()
                                imported.step()
                                self.assert_same(copy, imported)
                    self.assertEqual(len(converted), count)
                    self.assertGreater(late_imports, 0)
                    if card == "Bats":
                        self.assertGreater(bank_conversions, 0)

    def test_void_target_count_tiers_delayed_departure_and_import(self):
        cards = ("DarkMagic", "Knight", "Minions", "Bats")
        cfg = config(cards)
        for card, tier, leave in (
            ("Knight", 0, False),
            ("Minions", 1, False),
            ("Bats", 2, False),
            ("Knight", 0, True),
        ):
            with self.subTest(card=card, leave=leave):
                b = initial(cards=cards)
                b.deploy_card(1, card, Position(4.5, 18.5))
                for _ in range(20):
                    b.step()
                targets = [
                    e for e in b.entities.values() if type(e).__name__ == "Troop"
                ]
                for e in targets:
                    e.hitpoints = 100000
                    e.apply_stun(10)
                r = clasher_core.BattleState(snapshot(b, cfg))
                b.deploy_card(0, "DarkMagic", Position(4.5, 18.5))
                r.apply_action(0, "DarkMagic", 4.5, 18.5)
                for t in range(90):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    if t == 29 and leave:
                        area = next(
                            e
                            for e in b.entities.values()
                            if type(e).__name__ == "VoidArea"
                        )
                        self.assertEqual(len(area.pending), 1)
                        targets[0].position = Position(13.5, 18.5)
                        r = clasher_core.BattleState(snapshot(b, cfg))
                    if t in (29, 30, 49, 69):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(80):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                expected = cfg["cards"]["DarkMagic"]["spell"]["tier_damage"][tier] * (
                    1 if leave else 3
                )
                self.assertTrue(all(100000 - e.hitpoints == expected for e in targets))
        b = initial(cards=cards)
        r = clasher_core.BattleState(snapshot(b, cfg))
        b.deploy_card(0, "DarkMagic", Position(3.5, 25.5))
        r.apply_action(0, "DarkMagic", 3.5, 25.5)
        for _ in range(90):
            b.step()
            r.step()
            self.assert_same(b, r)
        lost = sum(
            e.max_hitpoints - e.hitpoints
            for e in b.entities.values()
            if e.player_id == 1
        )
        self.assertEqual(
            lost, 3 * cfg["cards"]["DarkMagic"]["spell"]["tier_crown_damage"][0]
        )

    def test_vines_rank_grounding_freeze_death_children_and_import(self):
        cards = ("Vines", "Minions", "Golem", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                y = 18.5 if seat == 0 else 13.5
                b.players[1 - seat].elixir = 10
                b.deploy_card(1 - seat, "Minions", Position(4.5, y))
                b.players[1 - seat].elixir = 10
                b.deploy_card(1 - seat, "Golem", Position(4.5, y))
                b.players[seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.deploy_card(seat, "Vines", Position(4.5, y)))
                self.assertTrue(r.apply_action(seat, "Vines", 4.5, y))
                saw_ground = False
                saw_children = False
                for t in range(150):
                    if t == 22:
                        golem = b.entities[10]
                        self.assertGreater(golem.stun_timer, 0)
                        self.assertGreater(golem.freeze_expiry_time, b.time)
                        golem.hitpoints = 1
                        r = clasher_core.BattleState(snapshot(b, cfg))
                        pos = golem.position
                        self.assertTrue(
                            b.deploy_card(seat, "Zap", Position(pos.x, pos.y))
                        )
                        self.assertTrue(r.apply_action(seat, "Zap", pos.x, pos.y))
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    saw_ground |= any(
                        getattr(e, "_vines_grounded", False)
                        for e in b.entities.values()
                    )
                    if t == 22:
                        children = [
                            e
                            for e in b.entities.values()
                            if getattr(e.card_stats, "name", None) == "Golemite"
                        ]
                        self.assertEqual(len(children), 2)
                        self.assertTrue(
                            all(
                                e.stun_timer > 1
                                and any(
                                    v[1:] == (0.0, 0.0, 0.0) for v in e._slow_effects
                                )
                                for e in children
                            )
                        )
                        saw_children = True
                    if t in (17, 18, 20, 22, 35, 57):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(100):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertTrue(saw_ground and saw_children)
                self.assertFalse(
                    any(
                        getattr(e, "_vines_grounded", False)
                        for e in b.entities.values()
                    )
                )


if __name__ == "__main__":
    unittest.main()
