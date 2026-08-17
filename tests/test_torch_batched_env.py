from __future__ import annotations

from collections import deque

import numpy as np
import torch

from clasher.battle import BattleState
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.selfplay_env import SelfPlayBattleEnv
from clasher.torch_sim.actions import NO_OP_ACTION, TensorActionState
from clasher.torch_sim.batched_env import BatchedSelfPlayActionIngress
from clasher.torch_sim.diagnostics import battle_snapshot, first_divergence


def _env(seed: int, *, canonical_perspective: bool = True) -> SelfPlayBattleEnv:
    env = SelfPlayBattleEnv(
        seed=seed,
        decision_interval_ticks=0,
        max_ticks=64,
        canonical_perspective=canonical_perspective,
    )
    env.reset(seed=seed)
    assert env.battle is not None
    for player in env.battle.players:
        player.elixir = 10.0
    return env


def _oracle_masks(envs: list[SelfPlayBattleEnv]) -> np.ndarray:
    return np.stack(
        [
            np.stack(
                [
                    env.action_space.legal_action_mask(
                        env.battle,
                        player_id,
                        fast_path=False,
                    )
                    for player_id in (0, 1)
                ]
            )
            for env in envs
        ]
    )


def _first_deployments(masks: torch.Tensor) -> torch.Tensor:
    actions = torch.full(masks.shape[:2], NO_OP_ACTION, dtype=torch.int64)
    for batch_index in range(masks.shape[0]):
        for player_id in (0, 1):
            legal = torch.nonzero(
                masks[batch_index, player_id, :NO_OP_ACTION],
                as_tuple=False,
            )
            if legal.numel():
                actions[batch_index, player_id] = legal[0, 0]
    return actions


def _oracle_ingress(
    env: SelfPlayBattleEnv,
    actions: torch.Tensor,
) -> tuple[list[int], list[bool]]:
    assert env.battle is not None
    order = [0, 1]
    env.rng.shuffle(order)
    success = [False, False]
    for player_id in order:
        success[player_id] = env.action_space.apply_action(
            env.battle,
            player_id,
            int(actions[player_id]),
        )
    return order, success


def _assert_battle_equal(expected: BattleState, actual: BattleState) -> None:
    mismatch = first_divergence(
        battle_snapshot(expected),
        battle_snapshot(actual),
    )
    assert mismatch is None, str(mismatch)


def test_twelve_environment_masks_match_exact_oracle() -> None:
    envs = [_env(50_100 + index) for index in range(12)]
    ingress = BatchedSelfPlayActionIngress(envs)

    result = ingress.action_masks()

    assert result.values.shape == (12, 2, NO_OP_ACTION + 2)
    assert result.values.dtype is torch.bool
    assert result.tensor_supported.all()
    assert not result.fallback_rows.any()
    np.testing.assert_array_equal(result.values.cpu().numpy(), _oracle_masks(envs))


def test_twelve_environment_ingress_matches_rng_order_and_oracle_state() -> None:
    actual = [_env(60_200 + index) for index in range(12)]
    expected = [_env(60_200 + index) for index in range(12)]
    ingress = BatchedSelfPlayActionIngress(actual)
    masks = ingress.action_masks()
    actions = _first_deployments(masks.values.cpu())
    plan = ingress.plan(actions, masks=masks)

    expected_orders: list[list[int]] = []
    expected_success: list[list[bool]] = []
    for env, row_actions in zip(expected, actions):
        order, success = _oracle_ingress(env, row_actions)
        expected_orders.append(order)
        expected_success.append(success)

    result = ingress.ingress(actions, masks=masks)

    assert result.player_order.cpu().tolist() == expected_orders
    assert result.action_success.cpu().tolist() == expected_success
    assert not result.downstream_rejected.any()
    assert plan.tensor.commands.sequence.tolist() == list(
        range(plan.tensor.commands.sequence.numel())
    )
    assert plan.tensor.commands.battle_index.tolist() == sorted(
        plan.tensor.commands.battle_index.tolist()
    )

    actual_battles: list[BattleState] = []
    for expected_env, actual_env in zip(expected, actual):
        assert expected_env.battle is not None
        assert actual_env.battle is not None
        _assert_battle_equal(expected_env.battle, actual_env.battle)
        assert expected_env.rng.getstate() == actual_env.rng.getstate()
        actual_battles.append(actual_env.battle)

    projected = TensorActionState.from_battles(actual_battles, ingress.catalog)
    assert torch.equal(projected.hand_ids, plan.tensor.hand_ids)
    assert torch.equal(projected.cycle_length, plan.tensor.cycle_length)
    assert torch.equal(projected.elixir, plan.tensor.elixir)
    for batch_index in range(12):
        for player_id in (0, 1):
            length = int(plan.tensor.cycle_length[batch_index, player_id])
            assert torch.equal(
                projected.cycle_ids[batch_index, player_id, :length],
                plan.tensor.cycle_ids[batch_index, player_id, :length],
            )


def test_mixed_perspective_rows_fall_back_without_poisoning_tensor_rows() -> None:
    actual = [_env(70_301), _env(70_302, canonical_perspective=False)]
    expected = [_env(70_301), _env(70_302, canonical_perspective=False)]
    ingress = BatchedSelfPlayActionIngress(actual, canonical_perspective=True)

    masks = ingress.action_masks()
    np.testing.assert_array_equal(masks.values.cpu().numpy(), _oracle_masks(actual))
    assert masks.tensor_supported.tolist() == [[True, True], [False, False]]
    assert masks.fallback_rows.tolist() == [[False, False], [True, True]]

    actions = _first_deployments(masks.values.cpu())
    expected_orders = []
    expected_success = []
    for env, row_actions in zip(expected, actions):
        order, success = _oracle_ingress(env, row_actions)
        expected_orders.append(order)
        expected_success.append(success)
    result = ingress.ingress(actions, masks=masks)

    assert result.player_order.cpu().tolist() == expected_orders
    assert result.action_success.cpu().tolist() == expected_success
    assert set(result.plan.tensor.commands.battle_index.tolist()) <= {0}
    for expected_env, actual_env in zip(expected, actual):
        assert expected_env.battle is not None
        assert actual_env.battle is not None
        _assert_battle_equal(expected_env.battle, actual_env.battle)


def test_unknown_player_row_uses_oracle_mask_and_rejects_fail_closed() -> None:
    battles = [BattleState(), BattleState()]
    for battle in battles:
        for player in battle.players:
            player.elixir = 10.0
            player.hand = ["Knight", "Fireball", "Cannon", "Zap"]
            player.deck = list(player.hand)
            player.cycle_queue = deque()
    battles[1].players[1].hand[0] = "UnknownSerializedCard"
    action_space = DiscreteTileActionSpace(canonical_perspective=True)
    enabled = ["Knight", "Fireball", "Cannon", "Zap"]
    ingress = BatchedSelfPlayActionIngress(battles, card_names=enabled)

    masks = ingress.action_masks()

    assert masks.tensor_supported.tolist() == [[True, True], [True, False]]
    expected = action_space.legal_action_mask(battles[1], 1, fast_path=False)
    np.testing.assert_array_equal(masks.values[1, 1].cpu().numpy(), expected)
    illegal_unknown_slot = action_space.encode_action(0, 9, 20, 1)
    result = ingress.ingress(
        [[NO_OP_ACTION, NO_OP_ACTION], [NO_OP_ACTION, illegal_unknown_slot]],
        masks=masks,
        player_order=[[0, 1], [0, 1]],
    )
    assert not result.action_success[1, 1]
    assert not result.plan.tensor.commands.battle_index.numel()
    assert battles[1].players[1].hand[0] == "UnknownSerializedCard"
    assert battles[1].players[1].elixir == 10.0


def test_planning_is_read_only_and_ingress_does_not_touch_reward_or_observation() -> (
    None
):
    envs = [_env(80_401), _env(80_402)]
    ingress = BatchedSelfPlayActionIngress(envs)
    before_snapshots = [battle_snapshot(env.battle) for env in envs]
    before_rewards = [env._prev_objective_p0 for env in envs]
    before_ticks = [env.battle.tick for env in envs if env.battle is not None]
    assert all(env._structured_obs_builder is None for env in envs)

    masks = ingress.action_masks()
    plan = ingress.plan(
        torch.full((2, 2), NO_OP_ACTION, dtype=torch.int64),
        masks=masks,
    )

    assert plan.tensor.accepted.all()
    for before, env in zip(before_snapshots, envs):
        assert first_divergence(before, battle_snapshot(env.battle)) is None

    result = ingress.ingress(plan.action_ids, masks=masks)
    assert result.action_success.all()
    assert [env._prev_objective_p0 for env in envs] == before_rewards
    assert [env.battle.tick for env in envs if env.battle is not None] == before_ticks
    assert all(env._structured_obs_builder is None for env in envs)
