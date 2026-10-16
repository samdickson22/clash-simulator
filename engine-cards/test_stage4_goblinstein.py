"""Goblinstein pair, projectile, tether, and callback cancellation differentials."""

import unittest

import clasher_core
import test_stage4_champions
from champion_snapshot import champion
from differential import Position, config, initial, snapshot


class GoblinsteinRegressions(unittest.TestCase):
    assert_same = test_stage4_champions.ChampionRegressions.assert_same
    assert_champions = test_stage4_champions.ChampionRegressions.assert_champions

    def test_pair_binding_after_statless_spell_and_newer_copy(self):
        cards = ("Goblinstein", "Poison", "Knight", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.deploy_card(1 - seat, "Poison", Position(9.5, 16.5))
                b.players[seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                doctors = []
                for x in (4.5, 13.5):
                    self.assertTrue(
                        b.deploy_card(
                            seat,
                            "Goblinstein",
                            Position(x, 14.5 if seat == 0 else 17.5),
                        )
                    )
                    self.assertTrue(
                        r.apply_action(
                            seat, "Goblinstein", x, 14.5 if seat == 0 else 17.5
                        )
                    )
                    doctor = max(
                        (e for e in b.entities.values() if champion(e) is not None),
                        key=lambda e: e.id,
                    )
                    doctors.append(doctor)
                    self.assert_champions(b, r)
                    for _ in range(25):
                        b.step()
                        r.step()
                        self.assert_champions(b, r)
                self.assertNotEqual(
                    champion(doctors[0])["effect"]["monster"],
                    champion(doctors[1])["effect"]["monster"],
                )
                self.assertEqual(
                    b.can_activate_champion_ability(seat),
                    r.can_activate_champion_ability(seat),
                )
                for _ in range(180):
                    b.step()
                    r.step()
                    self.assert_champions(b, r)

    def test_frozen_tether_eight_pulses_cooldown_and_import(self):
        cards = ("Goblinstein", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "Goblinstein", Position(9, 10.5))
        for _ in range(25):
            b.step()
        monster, doctor = b.entities[7], b.entities[8]
        doctor.position = Position(9, 11.5)
        monster.position = Position(9, 18.5)
        b._spawn_unit_at_position(
            Position(9, 14.5),
            1,
            b.card_loader.get_card("Knight"),
            deploy_delay_override=0,
            snap_to_valid=False,
        )
        knight = b.entities[max(b.entities)]
        for e in (doctor, monster, knight):
            e.apply_stun(30)
        hp = knight.hitpoints
        b.players[0].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        accepted = []
        for t in range(450):
            self.assertEqual(
                b.can_activate_champion_ability(0), r.can_activate_champion_ability(0)
            )
            if t in (420, 421, 422):
                pa = b.activate_champion_ability(0)
                self.assertEqual(pa, r.activate_champion_ability(0))
                if pa:
                    accepted.append(t)
            b.step()
            r.step()
            self.assert_champions(b, r)
            if t == 80:
                self.assertEqual(hp - knight.hitpoints, 8 * 94)
            if t in (0, 9, 18, 40, 79, 80, 420, 421):
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_champions(copy, imported)
        self.assertEqual(accepted, [421])

    def test_tether_pulse_golem_death_kills_doctor_and_cancels_timer(self):
        cards = ("Goblinstein", "Golem", "Knight", "Zap")
        cfg = config(cards)
        for late in (0, 1000):
            with self.subTest(late=late):
                b = initial(cards=cards)
                b.deploy_card(0, "Goblinstein", Position(7.5, 10.5))
                for _ in range(25):
                    b.step()
                monster, doctor = b.entities[7], b.entities[8]
                doctor.position = Position(7.5, 10.5)
                monster.position = Position(7.5, 15.5)
                b._spawn_unit_at_position(
                    Position(7.5, 11.5),
                    1,
                    b.card_loader.get_card("Golem"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                golem = b.entities[max(b.entities)]
                b._spawn_unit_at_position(
                    Position(7.5, 14),
                    1,
                    b.card_loader.get_card("Knight"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                knight = b.entities[max(b.entities)]
                hp = knight.hitpoints
                doctor.hitpoints = golem.hitpoints = 1
                for e in (doctor, monster, golem, knight):
                    e.apply_stun(3)
                b.players[0].elixir = 10
                self.assertTrue(b.activate_champion_ability(0))
                tether = next(
                    m
                    for m in doctor.mechanics
                    if type(m).__name__ == "GoblinsteinTether"
                )
                tether.next_hit_ms -= late
                r = clasher_core.BattleState(snapshot(b, cfg))
                b.step()
                r.step()
                self.assert_champions(b, r)
                self.assertFalse(doctor.is_alive or golem.is_alive)
                self.assertIsNone(tether.next_hit_ms)
                self.assertEqual(hp - knight.hitpoints, 94)
                for _ in range(80):
                    b.step()
                    r.step()
                    self.assert_champions(b, r)

    def test_tether_crown_damage_and_air_recipient_both_seats(self):
        cards = ("Goblinstein", "Bats", "Knight", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.deploy_card(
                    seat, "Goblinstein", Position(7.5, 10.5 if seat == 0 else 21.5)
                )
                for _ in range(25):
                    b.step()
                monster, doctor = b.entities[7], b.entities[8]
                doctor.position = Position(3.5, 21.5 if seat == 0 else 10.5)
                monster.position = Position(3.5, 27.5 if seat == 0 else 4.5)
                b._spawn_unit_at_position(
                    Position(3.5, 23.5 if seat == 0 else 8.5),
                    1 - seat,
                    b.card_loader.get_card("Bats"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                bats = [
                    e
                    for e in b.entities.values()
                    if e.entity_kind == 0 and e.player_id == 1 - seat and e.is_air_unit
                ]
                self.assertTrue(bats)
                crown = next(
                    e
                    for e in b.entities.values()
                    if e.player_id == 1 - seat
                    and getattr(e.card_stats, "name", None) == "Tower"
                    and e.position.x < 9
                )
                hp = crown.hitpoints
                for e in b.entities.values():
                    e.apply_stun(30)
                b.players[seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.activate_champion_ability(seat))
                self.assertTrue(r.activate_champion_ability(seat))
                for _ in range(81):
                    b.step()
                    r.step()
                    self.assert_champions(b, r)
                self.assertEqual(hp - crown.hitpoints, 8 * 23)
                self.assertTrue(all(not e.is_alive for e in bats))

    def test_monster_death_retains_anchor_for_active_tether(self):
        cards = ("Goblinstein", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "Goblinstein", Position(7.5, 10.5))
        for _ in range(25):
            b.step()
        monster, doctor = b.entities[7], b.entities[8]
        monster.hitpoints = 1
        b.players[0].elixir = 10
        self.assertTrue(b.activate_champion_ability(0))
        position = Position(monster.position.x, monster.position.y)
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.deploy_card(1, "Zap", position))
        self.assertTrue(r.apply_action(1, "Zap", position.x, position.y))
        for t in range(100):
            b.step()
            r.step()
            self.assert_champions(b, r)
            self.assertEqual(
                champion(doctor)["effect"]["anchor"],
                [monster.position.x, monster.position.y],
            )
            if t == 5:
                r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertNotIn(monster.id, b.entities)


if __name__ == "__main__":
    unittest.main()
