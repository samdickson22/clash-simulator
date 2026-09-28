"""Production boundary for batched self-play action ingress.

The battle simulator is still the authority for materialising deployments and
champion abilities.  This adapter moves the production-shaped, simultaneous
pre-action work -- projection, masks, decoding, card-cycle transitions, and
command construction -- into the tensor action kernels.  Supported rows use
the tensor decode when commands are committed.  Rows the tensor schema cannot
represent are evaluated and committed through the Python oracle instead.

Reward calculation, observations, and tick advancement deliberately remain
outside this module so a rollout worker can adopt batched action ingress
without changing their ordering or RNG contracts.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeAlias

import torch

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.kinematics import logic_units_to_tiles
from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.deck_pool import load_deck_pool, unique_cards_from_decks
from clasher.rl.selfplay_env import SelfPlayBattleEnv

from .actions import (
    NO_OP_ACTION,
    NUM_ACTIONS,
    TensorActionCatalog,
    TensorActionKernel,
    TensorActionState,
    TensorIngressResult,
)
from .catalog import TensorCardCatalog

BattleRow: TypeAlias = SelfPlayBattleEnv | BattleState


@dataclass(frozen=True)
class BatchedActionMasks:
    """Exact masks plus the tensor/oracle ownership of each player row."""

    values: torch.Tensor
    tensor_supported: torch.Tensor
    fallback_rows: torch.Tensor
    state: TensorActionState


@dataclass(frozen=True)
class BatchedActionPlan:
    """One simultaneous pre-action snapshot for an entire battle batch."""

    action_ids: torch.Tensor
    masks: BatchedActionMasks
    tensor: TensorIngressResult


@dataclass(frozen=True)
class BatchedActionIngressResult:
    """Committed oracle outcomes and the tensor plan that produced them."""

    action_success: torch.Tensor
    player_order: torch.Tensor
    plan: BatchedActionPlan
    downstream_rejected: torch.Tensor

    @property
    def tensor_supported(self) -> torch.Tensor:
        return self.plan.masks.tensor_supported

    @property
    def fallback_rows(self) -> torch.Tensor:
        return self.plan.masks.fallback_rows


def _default_card_names(rows: Sequence[BattleRow]) -> tuple[str, ...]:
    names: set[str] = set()
    for row in rows:
        if isinstance(row, SelfPlayBattleEnv):
            names.update(unique_cards_from_decks(row.decks))
        battle = row.battle if isinstance(row, SelfPlayBattleEnv) else row
        if battle is None:
            continue
        for player in battle.players:
            names.update(card for card in player.deck if card is not None)
            names.update(card for card in player.hand if card is not None)
            names.update(card for card in player.cycle_queue if card is not None)
    if not names:
        names.update(unique_cards_from_decks(load_deck_pool()))
    return tuple(sorted(names))


class BatchedSelfPlayActionIngress:
    """Batch exact self-play masks and action ingress over Python battles.

    ``SelfPlayBattleEnv`` rows preserve the environment's player-order RNG:
    exactly one ``shuffle([0, 1])`` is consumed for every ingress call.  Bare
    ``BattleState`` rows have no action-order RNG owner, so their default order
    is stable ``(0, 1)``; callers can provide explicit per-battle permutations.

    The class is an integration boundary rather than a replacement environment.
    A rollout worker may obtain masks, call :meth:`ingress`, and then continue
    its existing tick, observation, and reward pipeline unchanged.
    """

    def __init__(
        self,
        rows: Sequence[BattleRow],
        *,
        card_names: Iterable[str] | None = None,
        device: str | torch.device = "cpu",
        canonical_perspective: bool = True,
    ) -> None:
        if not rows:
            raise ValueError("rows must contain at least one battle or environment")
        self.rows = tuple(rows)
        self.device = torch.device(device)
        self.canonical_perspective = bool(canonical_perspective)
        battles = self._battles()
        names = (
            tuple(card_names) if card_names is not None else _default_card_names(rows)
        )
        cards = TensorCardCatalog.compile(
            battles[0].card_loader,
            names,
            device=self.device,
        )
        self.catalog = TensorActionCatalog.compile(cards)
        self.kernel = TensorActionKernel(
            self.catalog,
            canonical_perspective=self.canonical_perspective,
        )
        self._fallback_action_spaces = tuple(
            row.action_space
            if isinstance(row, SelfPlayBattleEnv)
            else DiscreteTileActionSpace(
                canonical_perspective=self.canonical_perspective
            )
            for row in self.rows
        )

    @property
    def batch_size(self) -> int:
        return len(self.rows)

    def _battles(self) -> tuple[BattleState, ...]:
        battles: list[BattleState] = []
        for batch_index, row in enumerate(self.rows):
            battle = row.battle if isinstance(row, SelfPlayBattleEnv) else row
            if battle is None:
                raise RuntimeError(
                    f"SelfPlayBattleEnv row {batch_index} must be reset before batching"
                )
            battles.append(battle)
        return tuple(battles)

    def _project(self) -> TensorActionState:
        state = TensorActionState.from_battles(self._battles(), self.catalog)
        # A single kernel has one perspective. Mixed-perspective worker rows
        # remain valid, but must use their own scalar oracle action space.
        for batch_index, action_space in enumerate(self._fallback_action_spaces):
            if action_space.canonical_perspective != self.canonical_perspective:
                state.supported[batch_index] = False
        return state

    def action_masks(self) -> BatchedActionMasks:
        """Return exact simultaneous masks for both players in every battle."""

        battles = self._battles()
        state = self._project()
        supported = state.supported.clone()
        values = self.kernel.legal_action_mask(state)
        fallback = ~supported
        for batch_index, player_id in (
            torch.nonzero(fallback, as_tuple=False).cpu().tolist()
        ):
            oracle_mask = self._fallback_action_spaces[batch_index].legal_action_mask(
                battles[batch_index],
                player_id,
                fast_path=False,
            )
            values[batch_index, player_id] = torch.as_tensor(
                oracle_mask,
                dtype=torch.bool,
                device=self.device,
            )
        return BatchedActionMasks(
            values=values,
            tensor_supported=supported,
            fallback_rows=fallback,
            state=state,
        )

    def plan(
        self,
        action_ids: torch.Tensor | Sequence[Sequence[int]],
        *,
        masks: BatchedActionMasks | None = None,
    ) -> BatchedActionPlan:
        """Tensorize one simultaneous action snapshot without mutating battles."""

        actions = torch.as_tensor(action_ids, dtype=torch.int64, device=self.device)
        if actions.shape != (self.batch_size, 2):
            raise ValueError(
                f"action_ids must have shape [{self.batch_size}, 2], "
                f"got {list(actions.shape)}"
            )
        exact_masks = self.action_masks() if masks is None else masks
        if exact_masks.values.shape != (self.batch_size, 2, NUM_ACTIONS):
            raise ValueError("masks belong to a different battle batch")

        # Tensor ingress is fail-closed for unsupported rows. Their exact mask
        # is returned to the caller, but no tensor command or speculative card
        # transition is emitted for an oracle-owned row.
        tensor_actions = torch.where(
            exact_masks.tensor_supported,
            actions,
            torch.full_like(actions, NO_OP_ACTION),
        )
        tensor_mask = self.kernel.legal_action_mask(exact_masks.state)
        tensor_result = self.kernel.ingress(
            exact_masks.state,
            tensor_actions,
            legal_mask=tensor_mask,
        )
        return BatchedActionPlan(
            action_ids=actions,
            masks=exact_masks,
            tensor=tensor_result,
        )

    def _player_orders(
        self,
        player_order: torch.Tensor | Sequence[Sequence[int]] | None,
    ) -> torch.Tensor:
        if player_order is not None:
            orders = torch.as_tensor(
                player_order,
                dtype=torch.int64,
                device=self.device,
            )
            if orders.shape != (self.batch_size, 2):
                raise ValueError(f"player_order must have shape [{self.batch_size}, 2]")
            if not torch.all(
                torch.sort(orders, dim=1).values
                == torch.tensor([0, 1], dtype=torch.int64, device=self.device)
            ):
                raise ValueError(
                    "each player_order row must be a permutation of (0, 1)"
                )
            return orders

        result: list[list[int]] = []
        for row in self.rows:
            order = [0, 1]
            if isinstance(row, SelfPlayBattleEnv):
                row.rng.shuffle(order)
            result.append(order)
        return torch.tensor(result, dtype=torch.int64, device=self.device)

    def _apply_tensor_decoded(
        self,
        battle: BattleState,
        batch_index: int,
        player_id: int,
        plan: BatchedActionPlan,
    ) -> bool:
        selection = plan.tensor.selection
        if not bool(selection.valid_input[batch_index, player_id]):
            return False
        if bool(selection.is_no_op[batch_index, player_id]):
            return True
        if bool(selection.is_ability[batch_index, player_id]):
            return battle.activate_champion_ability(player_id)

        slot = int(selection.slot[batch_index, player_id])
        hand = battle.players[player_id].hand
        if slot < 0 or slot >= len(hand):
            return False
        card_name = hand[slot]
        if card_name is None:
            return False
        position = Position(
            logic_units_to_tiles(int(selection.world_x_units[batch_index, player_id])),
            logic_units_to_tiles(int(selection.world_y_units[batch_index, player_id])),
        )
        return battle.deploy_card(player_id, card_name, position)

    def ingress(
        self,
        action_ids: torch.Tensor | Sequence[Sequence[int]],
        *,
        masks: BatchedActionMasks | None = None,
        player_order: torch.Tensor | Sequence[Sequence[int]] | None = None,
    ) -> BatchedActionIngressResult:
        """Plan simultaneously, then commit commands in exact oracle order."""

        battles = self._battles()
        plan = self.plan(action_ids, masks=masks)
        orders = self._player_orders(player_order)
        success = torch.zeros(
            (self.batch_size, 2), dtype=torch.bool, device=self.device
        )
        for batch_index, battle in enumerate(battles):
            for player_id in orders[batch_index].cpu().tolist():
                if bool(plan.masks.tensor_supported[batch_index, player_id]):
                    accepted = self._apply_tensor_decoded(
                        battle,
                        batch_index,
                        player_id,
                        plan,
                    )
                else:
                    accepted = self._fallback_action_spaces[batch_index].apply_action(
                        battle,
                        player_id,
                        int(plan.action_ids[batch_index, player_id]),
                    )
                success[batch_index, player_id] = accepted

        tensor_preaccepted = plan.tensor.accepted & plan.masks.tensor_supported
        downstream_rejected = tensor_preaccepted & ~success
        return BatchedActionIngressResult(
            action_success=success,
            player_order=orders,
            plan=plan,
            downstream_rejected=downstream_rejected,
        )


__all__ = [
    "BatchedActionIngressResult",
    "BatchedActionMasks",
    "BatchedActionPlan",
    "BatchedSelfPlayActionIngress",
]
