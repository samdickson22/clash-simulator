"""Fresh and visible-body C56 native script controls."""

import unittest
import clasher_core
from c56_controller import CARDS, resources, verify
from differential import Position, config, initial, snapshot


class ControllerRegressions(unittest.TestCase):
    def test_all_fresh_hands_and_both_seats(self):
        builder, _, scripts, bots = resources()
        cfg = config(CARDS)
        for start in range(0, len(CARDS), 4):
            cards = CARDS[start : start + 4]
            b = initial(cards=cards)
            for player in b.players:
                player.elixir = 10
            native = clasher_core.BattleState(snapshot(b, cfg))
            for seat in (0, 1):
                self.assertTrue(
                    (result := verify(b, native, builder, scripts, bots, seat))["ok"],
                    result,
                )

    def test_visible_payloads_and_masked_abilities(self):
        builder, _, scripts, bots = resources()
        cfg = config(CARDS)
        for name in CARDS:
            with self.subTest(card=name):
                cards = (name, "Knight", "Zap", "ArcherQueen")
                b = initial(cards=cards)
                b.players[0].elixir = 10
                self.assertTrue(b.deploy_card(0, name, Position(4.5, 10.5)))
                for _ in range(60):
                    b.step()
                native = clasher_core.BattleState(snapshot(b, cfg))
                for seat in (0, 1):
                    self.assertTrue(
                        (result := verify(b, native, builder, scripts, bots, seat))[
                            "ok"
                        ],
                        result,
                    )


if __name__ == "__main__":
    unittest.main()
