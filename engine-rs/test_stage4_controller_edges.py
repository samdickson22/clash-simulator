"""C56 projection integration reductions; no reference source edits."""

import json
import unittest
import clasher_core
from c56_controller import resources
from differential import Position, config, initial, snapshot, battle_digest
from clasher.rl.public_action_mask import PublicActionMaskInput


class ControllerEdges(unittest.TestCase):
    def test_air_placement_cannot_use_ground_relocation(self):
        builder, _, scripts, bots = resources()
        cards = ("Bats", "Knight", "InfernoTower", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                b.players[seat].elixir = 10
                b.deploy_card(
                    seat,
                    "InfernoTower",
                    Position(7.5, 10.5) if seat == 0 else Position(10.5, 21.5),
                )
                b.players[seat].elixir = 10
                native = clasher_core.BattleState(snapshot(b, cfg))
                packet = builder.build_public(b, seat)
                expected = bots["balanced"].mask_builder.build(
                    PublicActionMaskInput.from_confidence_observation(packet)
                )
                actual = scripts.public_mask(native, seat)
                tile = 10 * 18 + 7
                self.assertFalse(expected[tile])
                self.assertTrue(expected[576 + tile])
                self.assertEqual(actual[tile], expected[tile])
                self.assertEqual(actual[576 + tile], expected[576 + tile])

    def test_public_projection_refreshes_champion_ownership_before_death(self):
        builder, _, scripts, bots = resources()
        cards = ("ArcherQueen", "Knight", "Archers", "Zap")
        cfg = config(cards)
        for method in ("public_view", "public_mask", "select_action"):
            with self.subTest(method=method):
                b = initial(cards=cards)
                b.deploy_card(0, "ArcherQueen", Position(4.5, 10.5))
                for _ in range(20):
                    b.step()
                b.players[0].elixir = 10
                self.assertTrue(b.activate_champion_ability(0))
                for _ in range(5):
                    b.step()
                b.players[0].elixir = 10
                b.deploy_card(0, "ArcherQueen", Position(13.5, 10.5))
                new = b.entities[max(b.entities)]
                new.hitpoints = 1
                native = clasher_core.BattleState(snapshot(b, cfg))
                packet = builder.build_public(b, 0)
                if method == "select_action":
                    self.assertEqual(
                        bots["balanced"].select_action(packet),
                        scripts.select_action(native, 0, "balanced"),
                    )
                else:
                    getattr(scripts, method)(native, 0)
                # Check the observable cooldown consequence after the new copy
                # dies, beyond the board digest which excludes ownership maps.
                b.deploy_card(1, "Zap", new.position)
                native.apply_action(1, "Zap", new.position.x, new.position.y)
                for _ in range(110):
                    b.step()
                    native.step()
                    self.assertEqual(battle_digest(b), native.digest())
                self.assertTrue(b.can_activate_champion_ability(0))
                self.assertTrue(native.can_activate_champion_ability(0))
                owners = sorted(
                    (owner, key, id)
                    for (owner, key), id in b._champion_ability_owner_ids.items()
                )
                self.assertEqual(
                    owners,
                    sorted(
                        tuple(v)
                        for v in json.loads(native.snapshot())["champion_owners"]
                    ),
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
