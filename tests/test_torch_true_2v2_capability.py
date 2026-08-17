from collections import deque

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.torch_sim.two_vs_two_capability import (
    TRUE_TWO_VS_TWO_BLOCKER,
    audit_enabled_true_two_vs_two_capability,
)


def test_true_two_vs_two_capability_matrix_is_exhaustive_and_unsupported() -> None:
    report = audit_enabled_true_two_vs_two_capability()
    summary = report.summary()

    assert summary["enabled_card_count"] == 66
    assert summary["matrix_row_count"] == 66
    assert summary["python_owner_ids"] == [0, 1]
    assert summary["action_owner_ids"] == [0, 1]
    assert summary["python_has_team_identity"] is False
    assert summary["tensor_player_axis"] == 2
    assert summary["true_two_vs_two_supported"] is False
    assert summary["python_oracle_supported_rows"] == 0
    assert summary["tensor_backend_supported_rows"] == 0
    assert summary["two_cards_per_owner_is_true_two_vs_two"] is False
    assert len(summary["matrix_sha256"]) == 64

    assert tuple(row.card_name for row in report.rows) == report.manifest.card_names
    for row in report.rows:
        assert not row.python_oracle_supported
        assert not row.tensor_backend_supported
        assert row.blocker == TRUE_TWO_VS_TWO_BLOCKER


def test_two_card_per_owner_fixture_remains_a_two_owner_battle() -> None:
    """Prevent the interaction matrix from being cited as true team 2v2."""

    report = audit_enabled_true_two_vs_two_capability()
    cards = report.manifest.card_names[:2]
    battle = BattleState()
    for player_id, y_positions in ((0, (12.0, 10.0)), (1, (20.0, 22.0))):
        for slot, (card_name, y_position) in enumerate(zip(cards, y_positions)):
            player = battle.players[player_id]
            player.elixir = player.max_elixir
            player.hand = [card_name, None, None, None]
            player.deck = [card_name]
            player.cycle_queue = deque()
            assert battle.deploy_card(
                player_id,
                card_name,
                Position((4.0, 14.0)[slot], y_position),
            )

    assert len(cards) == 2
    assert tuple(player.player_id for player in battle.players) == (0, 1)
    assert {entity.player_id for entity in battle.entities.values()} == {0, 1}
    assert not report.true_two_vs_two_supported
