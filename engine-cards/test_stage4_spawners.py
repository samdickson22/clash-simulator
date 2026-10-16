"""Furnace and Goblin Hut production differentials."""

import unittest
import clasher_core
import test_stage4
from differential import CARDS, Position, config, initial, snapshot


class SpawnerRegressions(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def test_self_projectile_splash_bypasses_character_birth_immunity(self):
        for card in ("FireSpirits", "IceSpirit", "Heal"):
            with self.subTest(card=card):
                cards = (card, "GoblinHut", "Knight", "Zap")
                cfg = config(cards)
                b = initial(cards=cards)
                for name, seat, y in (
                    (card, 0, 12.5),
                    ("Knight", 1, 14),
                    ("GoblinHut", 1, 15),
                ):
                    b._spawn_unit_at_position(
                        Position(4.5, y),
                        seat,
                        b.card_loader.get_card(name),
                        deploy_delay_override=0,
                        snap_to_valid=False,
                    )
                spirit, knight, hut = b.entities[7], b.entities[8], b.entities[9]
                knight.apply_stun(10)
                for _ in range(20):
                    b.step()
                    if getattr(spirit, "_self_projectile_launched", False):
                        break
                self.assertTrue(getattr(spirit, "_self_projectile_launched", False))
                self.assertEqual(spirit.entity_kind, 2)
                hut.take_damage(hut.hitpoints)
                children = [
                    e for e in b.entities.values() if e.id >= 10 and e.entity_kind == 0
                ]
                self.assertTrue(children)
                hp = sum(e.hitpoints for e in children)
                r = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(20):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                self.assertLess(sum(e.hitpoints for e in children), hp)

    def test_furnace_walks_first_wave_cadence_deployment_and_import(self):
        cards = ("FirespiritHut",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                x, y = (4.5, 4.5) if seat == 0 else (13.5, 27.5)
                b.deploy_card(seat, "FirespiritHut", Position(x, y))
                furnace = b.entities[7]
                start_y = furnace.position.y
                r = clasher_core.BattleState(snapshot(b, cfg))
                seen = set()
                births = []
                for t in range(300):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    for e in b.entities.values():
                        if (
                            getattr(e.card_stats, "name", None) == "FireSpirits"
                            and e.id not in seen
                        ):
                            seen.add(e.id)
                            births.append(b.tick)
                            self.assertAlmostEqual(e.deploy_delay_remaining, 0.45)
                            self.assertTrue(
                                any(
                                    type(m).__name__ == "KamikazeSplash"
                                    for m in e.mechanics
                                )
                            )
                    if t in (1, 19, 59, 79, 159, 179):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(80):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertEqual(births[:3], [80, 180, 280])
                self.assertGreater(
                    (furnace.position.y - start_y) * (1 if seat == 0 else -1), 0
                )

    def test_hut_sleep_wake_reset_radial_direction_and_import(self):
        cards = ("GoblinHut", "Knight", "Archers", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.deploy_card(
                    seat, "GoblinHut", Position(9.5, 10.5 if seat == 0 else 21.5)
                )
                hut = b.entities[7]
                r = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(100):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                self.assertFalse(
                    any(
                        getattr(e.card_stats, "name", None) == "SpearGoblin"
                        for e in b.entities.values()
                    )
                )
                b.deploy_card(
                    1 - seat, "Knight", Position(4.5, 18.5 if seat == 0 else 13.5)
                )
                knight = b.entities[8]
                knight.hitpoints = 100000
                knight.apply_stun(20)
                near = Position(
                    hut.position.x, hut.position.y + (5 if seat == 0 else -5)
                )
                knight.position = near
                seen = set()
                for cycle in range(2):
                    r = clasher_core.BattleState(snapshot(b, cfg))
                    birth = []
                    for t in range(20):
                        b.step()
                        r.step()
                        self.assert_same(b, r)
                        new = [
                            e
                            for e in b.entities.values()
                            if type(e).__name__ == "Troop"
                            and getattr(e.card_stats, "name", None) == "SpearGoblin"
                            and e.id not in seen
                        ]
                        for e in new:
                            seen.add(e.id)
                            birth.append(t + 1)
                            self.assertAlmostEqual(
                                e.deploy_delay_remaining,
                                0.45,
                                msg=f"cycle={cycle} t={t} tick={b.tick} id={e.id} hut_alive={hut.is_alive}",
                            )
                            self.assertLess(
                                abs(e.position.distance_to(hut.position) - 1.2), 0.003
                            )
                            self.assertGreater(
                                (e.position.y - hut.position.y)
                                * (1 if seat == 0 else -1),
                                0,
                            )
                        if t in (0, 10, 18):
                            copy = b.clone()
                            imported = clasher_core.BattleState(snapshot(b, cfg))
                            for _ in range(50):
                                copy.step()
                                imported.step()
                                self.assert_same(copy, imported)
                    self.assertEqual(birth, [20])
                    if cycle == 0:
                        knight.position = Position(13.5, 25.5 if seat == 0 else 6.5)
                        r = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(80):
                            b.step()
                            r.step()
                            self.assert_same(b, r)
                        state = hut.mechanics[-1]
                        self.assertEqual(state.time_since_spawn_ms, 0)
                        self.assertEqual(state.spawns_created, 0)
                        knight.position = Position(near.x, near.y)

    def test_hut_immediate_death_child_inherits_freeze(self):
        cards = ("GoblinHut",) + CARDS
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "GoblinHut", Position(9.5, 10.5))
        for _ in range(20):
            b.step()
        hut = b.entities[7]
        hut.inherit_freeze_until(b.time + 2, b.time)
        hut.hitpoints = 1
        hut.lifetime_decay_work = 99
        r = clasher_core.BattleState(snapshot(b, cfg))
        b.step()
        r.step()
        self.assert_same(b, r)
        children = [
            e
            for e in b.entities.values()
            if getattr(e.card_stats, "name", None) == "SpearGoblin"
        ]
        self.assertEqual(len(children), 1)
        self.assertGreater(children[0].stun_timer, 1)
        self.assertEqual(children[0].freeze_expiry_time, hut.freeze_expiry_time)
        copy = b.clone()
        imported = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)
            copy.step()
            imported.step()
            self.assert_same(copy, imported)


if __name__ == "__main__":
    unittest.main()
