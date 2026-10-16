"""Champion reductions are provisional until the Python repair is finalized."""

import json
import unittest
import clasher_core
import test_stage4
from champion_snapshot import champion
from differential import Position, config, initial, snapshot


class ChampionRegressions(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def assert_champions(self, b, r):
        self.assert_same(b, r)
        native = json.loads(r.snapshot())
        indexed = {e["id"]: e for e in native["entities"]}
        for e in b.entities.values():
            state = champion(e)
            if state is None:
                self.assertIsNone(
                    indexed[e.id]["champion"], f"nonchampion {b.tick}/{e.id}"
                )
            else:
                self.assertEqual(
                    state, indexed[e.id]["champion"], f"ability at {b.tick}/{e.id}"
                )
                self.assertEqual(e.movement_mode_multiplier, indexed[e.id]["move_mode"])
                self.assertEqual(e.attack_mode_multiplier, indexed[e.id]["attack_mode"])
                self.assertEqual(
                    getattr(e, "_stealth_until", 0), indexed[e.id]["stealth_until"]
                )
        owners = sorted(
            (p, key, id) for (p, key), id in b._champion_ability_owner_ids.items()
        )
        self.assertEqual(owners, sorted(tuple(v) for v in native["champion_owners"]))

    def test_log_knockback_breaks_mighty_beam_target_and_bank(self):
        cards = ("MightyMiner", "Knight", "Log", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        miner, knight = b.entities[7], b.entities[8]
        miner.hitpoints = knight.hitpoints = 100000
        for _ in range(140):
            b.step()
        ramp = next(m for m in miner.mechanics if type(m).__name__ == "DamageRamp")
        self.assertGreater(ramp._current_target_ms, 0)
        b.players[1].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.deploy_card(1, "Log", Position(4.5, 18.5)))
        self.assertTrue(r.apply_action(1, "Log", 4.5, 18.5))
        first_push = None
        for t in range(80):
            b.step()
            r.step()
            self.assert_same(b, r)
            if miner._knockback_target is not None and first_push is None:
                first_push = t
                self.assertIsNone(miner.target_id)
                self.assertEqual(ramp._current_target_ms, 0)
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(80):
                    copy.step()
                    imported.step()
                    self.assert_same(copy, imported)
        self.assertIsNotNone(first_push)

    def test_knockback_target_observation_does_not_start_an_attack(self):
        cards = ("Ghost", "FireSpirits", "MightyMiner", "Knight")
        cfg = config(cards)
        b = initial(cards=cards)
        for name, seat, y in (("Ghost", 1, 14.5), ("FireSpirits", 0, 13)):
            b._spawn_unit_at_position(
                Position(4.5, y),
                seat,
                b.card_loader.get_card(name),
                deploy_delay_override=0,
                snap_to_valid=False,
            )
        ghost = b.entities[7]
        ghost._stealth_until = 0
        next(
            m
            for m in ghost.mechanics
            if type(m).__name__ == "InvisibilityWhenNotAttacking"
        ).time_since_attack_ms = 0
        self.assertTrue(
            ghost.begin_knockback(Position(4.5, 16.3), 1800, source_kind="MightyMiner")
        )
        r = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(30):
            b.step()
            r.step()
            self.assert_same(b, r)
            native = next(
                (e for e in json.loads(r.snapshot())["entities"] if e["id"] == 7), None
            )
            if native is not None and ghost._knockback_target is not None:
                self.assertEqual(
                    native["started"],
                    bool(
                        getattr(ghost, "_has_attacked_once", False)
                        or ghost._attack_windup_active
                    ),
                )

    def test_queued_tornado_vector_survives_mighty_tunnel_entry_and_import(self):
        cards = ("MightyMiner", "Tornado", "Knight", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 10.5))
        for _ in range(20):
            b.step()
        b.players[0].elixir = 10
        b.entities[7].apply_stun(3)
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        queued = False
        for t in range(90):
            if t == 5:
                self.assertTrue(b.deploy_card(1, "Tornado", Position(5.5, 10.5)))
                self.assertTrue(r.apply_action(1, "Tornado", 5.5, 10.5))
            b.step()
            r.step()
            self.assert_champions(b, r)
            miner = b.entities[7]
            queued |= (
                getattr(miner, "_underground_deployment", False)
                and miner._movement_vector_count > 0
            )
            if t in (8, 9, 10, 25, 43):
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(60):
                    copy.step()
                    imported.step()
                    self.assert_champions(copy, imported)
        self.assertTrue(queued)

    def test_mighty_switch_bomb_tunnel_cooldown_and_import(self):
        cards = ("MightyMiner", "Knight", "Archers", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.deploy_card(
                    seat, "MightyMiner", Position(4.5, 13.5 if seat == 0 else 18.5)
                )
                b.deploy_card(
                    1 - seat, "Knight", Position(4.5, 18.5 if seat == 0 else 13.5)
                )
                miner, knight = b.entities[7], b.entities[8]
                miner.hitpoints = knight.hitpoints = 100000
                for _ in range(100):
                    b.step()
                miner.apply_stun(1.2)
                b.players[seat].elixir = 10
                r = clasher_core.BattleState(snapshot(b, cfg))
                self.assertTrue(b.activate_champion_ability(seat))
                self.assertTrue(r.activate_champion_ability(seat))
                saw_bomb = saw_tunnel = saw_push = False
                accepted = []
                for t in range(330):
                    self.assertEqual(
                        b.can_activate_champion_ability(seat),
                        r.can_activate_champion_ability(seat),
                    )
                    if t in (269, 270, 271):
                        pa = b.activate_champion_ability(seat)
                        self.assertEqual(pa, r.activate_champion_ability(seat))
                        if pa:
                            accepted.append(t)
                    b.step()
                    r.step()
                    self.assert_champions(b, r)
                    saw_bomb |= any(
                        type(e).__name__ == "TimedExplosive"
                        for e in b.entities.values()
                    )
                    saw_tunnel |= getattr(miner, "_underground_deployment", False)
                    saw_push |= getattr(knight, "_knockback_target", None) is not None
                    if t in (0, 8, 9, 15, 28, 45, 269, 270, 279):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(70):
                            copy.step()
                            imported.step()
                            self.assert_champions(copy, imported)
                self.assertEqual(accepted, [270])
                self.assertTrue(saw_bomb and saw_tunnel and saw_push)

    def test_mighty_bomb_excludes_effect_container_and_pushes_survivors(self):
        from clasher.entities import TimedExplosive

        cards = ("MightyMiner", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 10.5))
        b.deploy_card(1, "Knight", Position(4.5, 21.5))
        for _ in range(20):
            b.step()
        miner, knight = b.entities[7], b.entities[8]
        knight.position = Position(miner.position.x + 1.0, miner.position.y)
        knight.hitpoints = 100000
        container = TimedExplosive(
            id=b.next_entity_id,
            position=Position(miner.position.x, miner.position.y),
            player_id=1,
            card_stats=knight.card_stats,
            hitpoints=1,
            max_hitpoints=1,
            damage=0,
            range=0,
            sight_range=0,
            explosion_timer=999,
        )
        b.entities[container.id] = container
        b.next_entity_id += 1
        b.players[0].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        saw_push = False
        for _ in range(80):
            b.step()
            r.step()
            self.assert_champions(b, r)
            saw_push |= knight._knockback_target is not None
        self.assertIn(container.id, b.entities)
        self.assertEqual(container.hitpoints, 1)
        self.assertTrue(saw_push)

    def test_mighty_death_cancels_pending_bomb(self):
        cards = ("MightyMiner", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 10.5))
        for _ in range(20):
            b.step()
        b.entities[7].hitpoints = 1
        b.players[0].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        pos = b.entities[7].position
        self.assertTrue(b.deploy_card(1, "Zap", pos))
        self.assertTrue(r.apply_action(1, "Zap", pos.x, pos.y))
        for _ in range(50):
            b.step()
            r.step()
            self.assert_champions(b, r)
            self.assertFalse(
                any(type(e).__name__ == "TimedExplosive" for e in b.entities.values())
            )
        self.assertNotIn(7, b.entities)

    def test_live_ice_spirit_freeze_preserves_mighty_miner_beam_bank(self):
        cards = ("MightyMiner", "Knight", "IceSpirit", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        b.entities[7].hitpoints = b.entities[8].hitpoints = 100000
        r = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(100):
            b.step()
            r.step()
            self.assert_same(b, r)
        self.assertTrue(b.deploy_card(1, "IceSpirit", Position(4.5, 18.5)))
        self.assertTrue(r.apply_action(1, "IceSpirit", 4.5, 18.5))
        frozen = False
        for _ in range(150):
            b.step()
            r.step()
            self.assert_same(b, r)
            miner = b.entities[7]
            if miner._freeze_target_pause_remaining > 0:
                frozen = True
                ramp = next(
                    m for m in miner.mechanics if type(m).__name__ == "DamageRamp"
                )
                native = next(
                    e for e in json.loads(r.snapshot())["entities"] if e["id"] == 7
                )
                self.assertEqual(ramp._current_target_ms, native["ramp_time"])
                self.assertEqual(ramp._current_target_id, native["ramp_target"])
        self.assertTrue(frozen)

    def test_ice_spirit_freeze_pauses_special_weapon_target_observation(self):
        cards = ("MightyMiner", "Knight", "IceSpirit", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 13.5))
        b.deploy_card(1, "Knight", Position(4.5, 18.5))
        for _ in range(40):
            b.step()
        miner = b.entities[7]
        miner.apply_stun(0.5, source_kind="IceSpirit", interrupt_combat=False)
        r = clasher_core.BattleState(snapshot(b, cfg))
        for _ in range(20):
            b.step()
            r.step()
            self.assert_same(b, r)

    def test_mighty_miner_reduced_approach_range_before_beam_connection(self):
        from stage2 import focused_case
        from differential import CARDS

        result = focused_case(
            "MightyMiner", 0, config((*CARDS, "MightyMiner")), ticks=107
        )
        self.assertTrue(result["ok"], f"first mismatch at {result.get('tick')}")

    def test_later_queen_cloak_invalidates_earlier_committed_movement(self):
        cards = ("MightyMiner", "ArcherQueen", "Knight", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "MightyMiner", Position(4.5, 13.5))
        b.deploy_card(1, "ArcherQueen", Position(4.5, 18.5))
        for _ in range(20):
            b.step()
        b.players[1].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(1))
        self.assertTrue(r.activate_champion_ability(1))
        stopped = False
        for _ in range(40):
            miner, queen = b.entities[7], b.entities[8]
            before = (miner.position.x, miner.position.y)
            old_cloak = queen._stealth_until
            b.step()
            r.step()
            self.assert_champions(b, r)
            if not old_cloak and queen._stealth_until:
                stopped = True
                self.assertEqual((miner.position.x, miner.position.y), before)
        self.assertTrue(stopped)

    def test_queen_cast_cloak_cooldown_and_live_import(self):
        cards = ("ArcherQueen", "Knight", "Archers", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.deploy_card(
                    seat, "ArcherQueen", Position(4.5, 10.5 if seat == 0 else 21.5)
                )
                b.entities[7].hitpoints = 100000
                r = clasher_core.BattleState(snapshot(b, cfg))
                accepted = []
                cloaked = False
                for t in range(500):
                    self.assertEqual(
                        b.can_activate_champion_ability(seat),
                        r.can_activate_champion_ability(seat),
                    )
                    if t in (0, 19, 20, 21, 24, 38, 94, 433, 434, 435):
                        pa = b.activate_champion_ability(seat)
                        ra = r.activate_champion_ability(seat)
                        self.assertEqual(pa, ra)
                        if pa:
                            accepted.append(t)
                    b.step()
                    r.step()
                    self.assert_champions(b, r)
                    cloaked |= b.entities[7]._stealth_until > 0
                    if t in (20, 23, 37, 38, 93, 433, 434):
                        copy = b.clone()
                        imported = clasher_core.BattleState(snapshot(b, cfg))
                        for _ in range(90):
                            copy.step()
                            imported.step()
                            self.assert_champions(copy, imported)
                self.assertEqual(accepted, [20, 434])
                self.assertTrue(cloaked)

    def test_queen_frozen_activation_defers_combat_owned_cloak(self):
        cards = ("ArcherQueen", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "ArcherQueen", Position(4.5, 10.5))
        for _ in range(20):
            b.step()
        queen = b.entities[7]
        queen.apply_stun(1.2)
        b.players[0].elixir = 5
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        first_cloak = None
        for t in range(140):
            b.step()
            r.step()
            self.assert_champions(b, r)
            if queen._stealth_until and first_cloak is None:
                first_cloak = t + 1
            if t in (0, 10, 23, 24, 70):
                copy = b.clone()
                imported = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(80):
                    copy.step()
                    imported.step()
                    self.assert_champions(copy, imported)
        self.assertEqual(first_cloak, 25)
        self.assertEqual(queen._stealth_until, 0)

    def test_queen_newest_copy_owns_button_and_death_resets_older_cooldown(self):
        cards = ("ArcherQueen", "Knight", "Archers", "Zap")
        cfg = config(cards)
        b = initial(cards=cards)
        b.deploy_card(0, "ArcherQueen", Position(4.5, 10.5))
        for _ in range(20):
            b.step()
        old = b.entities[7]
        old.hitpoints = 100000
        b.players[0].elixir = 10
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        for _ in range(5):
            b.step()
            r.step()
            self.assert_champions(b, r)
        new_id = b.next_entity_id
        self.assertTrue(b.deploy_card(0, "ArcherQueen", Position(13.5, 10.5)))
        self.assertTrue(r.apply_action(0, "ArcherQueen", 13.5, 10.5))
        self.assertFalse(b.can_activate_champion_ability(0))
        self.assertFalse(r.can_activate_champion_ability(0))
        for _ in range(20):
            b.step()
            r.step()
            self.assert_champions(b, r)
        self.assertTrue(b.activate_champion_ability(0))
        self.assertTrue(r.activate_champion_ability(0))
        new = b.entities[new_id]
        new.hitpoints = 1
        r = clasher_core.BattleState(snapshot(b, cfg))
        self.assertTrue(
            b.deploy_card(1, "Zap", Position(new.position.x, new.position.y))
        )
        self.assertTrue(r.apply_action(1, "Zap", new.position.x, new.position.y))
        b.step()
        r.step()
        self.assert_champions(b, r)
        self.assertNotIn(new_id, b.entities)
        self.assertEqual(champion(old)["ability"]["last_use"], -(10**12))
        self.assertTrue(champion(old)["ability"]["active"])
        for _ in range(60):
            b.step()
            r.step()
            self.assert_champions(b, r)
        self.assertTrue(b.can_activate_champion_ability(0))
        self.assertTrue(r.can_activate_champion_ability(0))


if __name__ == "__main__":
    unittest.main()
