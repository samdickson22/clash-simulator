"""B3 melee, swarm, kamikaze and visibility differential reductions."""

import unittest
import clasher_core
import test_stage4
from differential import CARDS, Position, config, initial, snapshot


class B3Regressions(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def test_wallbreakers_commit_explosion_and_self_death(self):
        cards = ("Wallbreakers", "Cannon", "Knight", "Archers")
        cfg = config(cards)
        b = initial(560419, cards=cards)
        b.deploy_card(0, "Wallbreakers", Position(4.5, 13.5))
        b.deploy_card(1, "Cannon", Position(4.5, 18.5))
        r = clasher_core.BattleState(snapshot(b, cfg))
        wall_ids = {
            e.id
            for e in b.entities.values()
            if e.player_id == 0 and type(e).__name__ == "Troop"
        }
        witnessed = False
        for _ in range(200):
            b.step()
            r.step()
            self.assert_same(b, r)
            shots = [
                e
                for e in b.entities.values()
                if type(e).__name__ == "Projectile" and e.player_id == 0
            ]
            if shots:
                witnessed = True
                self.assertTrue(any(id not in b.entities for id in wall_ids))
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(30):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertTrue(witnessed)

    def test_golem_death_spawn_knockback_and_live_travel(self):
        cards = ("Golem", "Zap", "Knight", "Musketeer")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(560418, cards=cards)
                b.players[seat].elixir = 10
                y = 13.5 if seat == 0 else 18.5
                self.assertTrue(b.deploy_card(seat, "Golem", Position(4.5, y)))
                self.assertTrue(
                    b.deploy_card(1 - seat, "Knight", Position(4.5, 32 - y))
                )
                for _ in range(60):
                    b.step()
                golem = next(
                    e
                    for e in b.entities.values()
                    if getattr(e.card_stats, "name", "") == "Golem"
                )
                golem.hitpoints = 1
                b.players[1 - seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                x, y = golem.position.x, golem.position.y
                self.assertTrue(b.deploy_card(1 - seat, "Zap", Position(x, y)))
                self.assertTrue(r.apply_action(1 - seat, "Zap", x, y))
                imports = 0
                for _ in range(100):
                    b.step()
                    r.step()
                    self.assert_same(b, r)
                    children = [
                        e
                        for e in b.entities.values()
                        if getattr(e.card_stats, "name", "") == "Golemite"
                    ]
                    if any(e._death_spawn_travel_ticks_remaining > 0 for e in children):
                        imports += 1
                        self.assertEqual(len(children), 2)
                        self.assertTrue(all(e.stun_timer > 0 for e in children))
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(40):
                            copy.step()
                            imported.step()
                            self.assert_same(copy, imported)
                self.assertGreater(imports, 0)

    def test_royal_hogs_deployment_width_margin(self):
        cards = ("RoyalHogs",) + CARDS
        cfg = config(cards)
        for seat in (0, 1):
            for x in (0.5, 1.5, 2.5, 15.5, 16.5, 17.5):
                b = initial(cards=cards)
                r = clasher_core.BattleState(snapshot(b, cfg))
                y = 10.5 if seat == 0 else 21.5
                accepted = b.deploy_card(seat, "RoyalHogs", Position(x, y))
                self.assertEqual(accepted, r.apply_action(seat, "RoyalHogs", x, y))
                self.assertEqual(accepted, 2 <= x < 16)
                self.assert_same(b, r)

    def test_fire_spirit_flight_import_and_splash_without_freeze(self):
        cards = ("FireSpirits", "Goblins", "Knight", "Archers")
        cfg = config(cards)
        b = initial(560416, cards=cards)
        b.deploy_card(0, "FireSpirits", Position(4.5, 13.5))
        b.deploy_card(1, "Goblins", Position(4.5, 18.5))
        r = clasher_core.BattleState(snapshot(b, cfg))
        imports = 0
        for _ in range(220):
            b.step()
            r.step()
            self.assert_same(b, r)
            self.assertFalse(any(e.stun_timer > 0 for e in b.entities.values()))
            if any(
                getattr(e, "_self_projectile_launched", False)
                for e in b.entities.values()
            ):
                imports += 1
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(40):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertGreater(imports, 0)

    def test_ghost_reveals_on_attack_and_refades_while_hovering(self):
        cards = ("Ghost", "Knight", "Archers", "Giant")
        cfg = config(cards)
        b = initial(560417, cards=cards)
        b.deploy_card(0, "Ghost", Position(9.5, 13.5))
        b.deploy_card(1, "Knight", Position(9.5, 18.5))
        b.entities[8].hitpoints = 1
        r = clasher_core.BattleState(snapshot(b, cfg))
        seen = set()
        for _ in range(400):
            b.step()
            r.step()
            self.assert_same(b, r)
            ghost = b.entities.get(7)
            if ghost:
                seen.add(bool(ghost._stealth_until))
            if b.tick in (20, 60, 100, 160):
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertEqual(seen, {False, True})


if __name__ == "__main__":
    unittest.main()
