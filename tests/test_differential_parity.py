import hashlib
import random

import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.differential import (
    BattleParityError,
    PythonBattleAdapter,
    canonical_battle_snapshot,
    first_snapshot_difference,
    python_lockstep,
    run_differential,
    snapshot_sha256,
)


def _duel(*, fast_path: bool) -> BattleState:
    battle = BattleState(rng=random.Random(734_221), fast_path=fast_path)
    battle.entities.clear()
    battle.next_entity_id = 1
    for player_id, card_name, position in (
        (0, "ElectroWizard", Position(8.0, 14.0)),
        (1, "Witch", Position(10.0, 18.0)),
    ):
        stats = battle.card_loader.get_card(card_name)
        assert stats is not None
        battle._spawn_unit_at_position(position, player_id, stats)
    for entity in list(battle.entities.values()):
        entity.deploy_delay_remaining = 0.0
        entity.placement_pending = False
        entity.on_spawn()
    if fast_path:
        battle._refresh_fast_path_caches()
    return battle


@pytest.mark.parametrize("fast_path", [False, True])
def test_python_lockstep_covers_full_mutable_state(fast_path):
    result = python_lockstep(
        _duel(fast_path=fast_path),
        ticks=8,
        scenario=f"electro-wizard-vs-witch-fast-{fast_path}",
    )

    assert result.ticks_compared == 8
    assert result.expected_sha256 == result.actual_sha256


def test_snapshot_digest_is_stable_across_exact_clones():
    battle = _duel(fast_path=True)

    expected = canonical_battle_snapshot(battle)
    actual = canonical_battle_snapshot(battle.clone())

    assert first_snapshot_difference(expected, actual) is None
    assert snapshot_sha256(expected) == snapshot_sha256(actual)


def test_first_mismatch_has_exact_path_and_atomic_reproducer(tmp_path):
    expected = _duel(fast_path=False)
    actual = expected.clone()
    actual.players[1].elixir += 0.125

    with pytest.raises(BattleParityError) as caught:
        run_differential(
            PythonBattleAdapter(expected),
            PythonBattleAdapter(actual),
            ticks=3,
            scenario="intentional player drift",
            dump_directory=tmp_path,
        )

    error = caught.value
    assert error.tick_offset == 0
    assert error.difference.path.endswith("players[1].$object.fields.elixir.$float")
    assert error.dump_path is not None
    assert error.dump_path.exists()
    assert not error.dump_path.with_suffix(error.dump_path.suffix + ".tmp").exists()


def test_observable_payload_participates_in_exact_comparison():
    battle = _duel(fast_path=False)
    expected = canonical_battle_snapshot(
        battle,
        observables={"mask": [True, False, True]},
    )
    actual = canonical_battle_snapshot(
        battle,
        observables={"mask": [True, True, True]},
    )

    difference = first_snapshot_difference(expected, actual)

    assert difference is not None
    assert difference.path.endswith("observables.$mapping[0][1][1]")


def test_snapshot_preserves_future_causal_entity_iteration_order():
    expected_battle = _duel(fast_path=False)
    actual_battle = expected_battle.clone()
    first_id = next(iter(actual_battle.entities))
    first = actual_battle.entities.pop(first_id)
    actual_battle.entities[first_id] = first

    expected = canonical_battle_snapshot(expected_battle)
    actual = canonical_battle_snapshot(actual_battle)
    difference = first_snapshot_difference(expected, actual)

    assert difference is not None
    assert difference.path.startswith("$.entities[0]") or difference.path.startswith(
        "$.entity_iteration_order"
    )
    assert expected["entity_iteration_order"] == list(expected_battle.entities)
    assert actual["entity_iteration_order"] == list(actual_battle.entities)


def test_snapshot_catalog_identity_is_portable_content_sha256():
    battle = _duel(fast_path=False)
    snapshot = canonical_battle_snapshot(battle)
    data_path = battle.card_loader.data_file

    assert snapshot["schema_version"] == 2
    assert snapshot["catalog"] == {
        "path_name": data_path.name,
        "size": data_path.stat().st_size,
        "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
    }
