"""Live imports of character-owned death areas retain their native route."""

import unittest
import clasher_core
import test_stage4
from differential import Position, config, initial, snapshot


class CharacterAreaImports(unittest.TestCase):
    assert_same = test_stage4.Stage4Regressions.assert_same

    def test_character_death_area_label_is_not_a_playable_spell_key(self):
        cards = ("IceGolem", "Knight", "Archers", "Zap")
        cfg = config(cards)
        for seat in (0, 1):
            with self.subTest(seat=seat):
                b = initial(cards=cards)
                y = 13.5 if seat == 0 else 18.5
                b._spawn_unit_at_position(
                    Position(4.5, y),
                    seat,
                    b.card_loader.get_card("IceGolem"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                b._spawn_unit_at_position(
                    Position(4.5, y + (1 if seat == 0 else -1)),
                    1 - seat,
                    b.card_loader.get_card("Knight"),
                    deploy_delay_override=0,
                    snap_to_valid=False,
                )
                parent = b.entities[7]
                parent.take_damage(parent.hitpoints)
                areas = [
                    e for e in b.entities.values() if type(e).__name__ == "AreaEffect"
                ]
                self.assertEqual(len(areas), 1)
                self.assertEqual(areas[0].spell_name, "FreezeIceGolemite")
                native = clasher_core.BattleState(snapshot(b, cfg))
                for _ in range(100):
                    b.step()
                    native.step()
                    self.assert_same(b, native)


if __name__ == "__main__":
    unittest.main()
