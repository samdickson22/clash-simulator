"""Dense action, elixir, and card-cycle state for the practical tensor Gym.

The fast Gym models the stable eight-card rotation as four visible hand slots
and a four-entry ring queue.  The queue head is the player's visible Next
card.  An accepted deployment replaces the selected hand slot with Next,
puts the played card at the vacated queue position, and advances the head.
There is no random shuffle or Python-side command collection in this path.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from clasher.kinematics import LOGIC_UNITS_PER_TILE
from clasher.rl.common import BOARD_HEIGHT, BOARD_WIDTH, NUM_HAND_SLOTS, NUM_TILES

from .actions import ABILITY_ACTION, NO_OP_ACTION, NUM_ACTIONS
from .simple_catalog import FastCardCatalog
from .simple_engine import FastDeploymentRequest

FAST_CYCLE_SIZE = 4
FAST_MAX_ELIXIR = 10.0
FAST_BASE_ELIXIR_SECONDS = 2.8


@dataclass
class FastActionState:
    """Mutable private action state with shape ``[batch, two players, ...]``."""

    hand_ids: torch.Tensor
    cycle_ids: torch.Tensor
    cycle_head: torch.Tensor
    elixir: torch.Tensor
    max_elixir: torch.Tensor
    player_alive: torch.Tensor
    tower_alive: torch.Tensor

    @property
    def device(self) -> torch.device:
        return self.hand_ids.device

    @property
    def batch_size(self) -> int:
        return int(self.hand_ids.shape[0])

    @property
    def own_next(self) -> torch.Tensor:
        """Return each actor's visible Next identity as ``[batch, 2]``."""

        return self.cycle_ids.gather(2, self.cycle_head.unsqueeze(-1)).squeeze(-1)

    @classmethod
    def from_decks(
        cls,
        deck_ids: torch.Tensor,
        *,
        starting_elixir: float = 6.0,
        max_elixir: float = FAST_MAX_ELIXIR,
    ) -> FastActionState:
        """Create deterministic hands from ordered ``[batch, 2, 8]`` decks."""

        if deck_ids.ndim != 3 or deck_ids.shape[1:] != (2, 8):
            raise ValueError("deck_ids must have shape [batch, 2, 8]")
        if deck_ids.dtype != torch.int64:
            deck_ids = deck_ids.to(torch.int64)
        batch = deck_ids.shape[0]
        device = deck_ids.device
        player_shape = (batch, 2)
        return cls(
            hand_ids=deck_ids[:, :, :NUM_HAND_SLOTS].clone(),
            cycle_ids=deck_ids[:, :, NUM_HAND_SLOTS:].clone(),
            cycle_head=torch.zeros(player_shape, dtype=torch.int64, device=device),
            elixir=torch.full(
                player_shape,
                float(starting_elixir),
                dtype=torch.float32,
                device=device,
            ),
            max_elixir=torch.full(
                player_shape,
                float(max_elixir),
                dtype=torch.float32,
                device=device,
            ),
            player_alive=torch.ones(player_shape, dtype=torch.bool, device=device),
            tower_alive=torch.ones((*player_shape, 3), dtype=torch.bool, device=device),
        )

    def clone(self) -> FastActionState:
        return type(self)(
            hand_ids=self.hand_ids.clone(),
            cycle_ids=self.cycle_ids.clone(),
            cycle_head=self.cycle_head.clone(),
            elixir=self.elixir.clone(),
            max_elixir=self.max_elixir.clone(),
            player_alive=self.player_alive.clone(),
            tower_alive=self.tower_alive.clone(),
        )

    def validate(self) -> None:
        player_shape = (self.batch_size, 2)
        expected = {
            "hand_ids": (*player_shape, NUM_HAND_SLOTS),
            "cycle_ids": (*player_shape, FAST_CYCLE_SIZE),
            "cycle_head": player_shape,
            "elixir": player_shape,
            "max_elixir": player_shape,
            "player_alive": player_shape,
            "tower_alive": (*player_shape, 3),
        }
        for name, shape in expected.items():
            value = getattr(self, name)
            if value.shape != shape:
                raise ValueError(f"{name} must have shape {list(shape)}")
            if value.device != self.device:
                raise ValueError(f"{name} is on a different device")


@dataclass(frozen=True)
class FastActionSelection:
    action_ids: torch.Tensor
    valid_input: torch.Tensor
    is_no_op: torch.Tensor
    slot: torch.Tensor
    tile: torch.Tensor
    world_x_units: torch.Tensor
    world_y_units: torch.Tensor


@dataclass(frozen=True)
class FastActionIngressResult:
    """Accepted actions and player-ordered fixed-shape deployment requests."""

    accepted: torch.Tensor
    deployment_accepted: torch.Tensor
    entity_deployment: torch.Tensor
    spell_cast: torch.Tensor
    selected_card_ids: torch.Tensor
    selection: FastActionSelection
    requests: tuple[FastDeploymentRequest, FastDeploymentRequest]


class FastActionKernel:
    """Label-independent action mask and deterministic action ingress."""

    def __init__(
        self,
        catalog: FastCardCatalog,
        *,
        canonical_perspective: bool = True,
    ) -> None:
        self.catalog = catalog
        self.device = catalog.device
        canonical_x = torch.arange(NUM_TILES, device=self.device) % BOARD_WIDTH
        canonical_y = torch.arange(NUM_TILES, device=self.device) // BOARD_WIDTH
        player = torch.arange(2, device=self.device)[:, None]
        if canonical_perspective:
            flip = player == 1
            world_x = torch.where(flip, BOARD_WIDTH - 1 - canonical_x, canonical_x)
            world_y = torch.where(flip, BOARD_HEIGHT - 1 - canonical_y, canonical_y)
        else:
            world_x = canonical_x.expand(2, -1)
            world_y = canonical_y.expand(2, -1)
        self.world_x = world_x.to(torch.int64)
        self.world_y = world_y.to(torch.int64)
        self.world_x_units = self.world_x * LOGIC_UNITS_PER_TILE + 500
        self.world_y_units = self.world_y * LOGIC_UNITS_PER_TILE + 500

        blocked = torch.zeros(
            (BOARD_HEIGHT, BOARD_WIDTH), dtype=torch.bool, device=self.device
        )
        blocked_xy = (
            (0, 14),
            (0, 17),
            (17, 14),
            (17, 17),
            *((x, 0) for x in (*range(6), *range(12, 18))),
            *((x, 31) for x in (*range(6), *range(12, 18))),
        )
        for x, y in blocked_xy:
            blocked[y, x] = True
        self.non_blocked = ~blocked[self.world_y, self.world_x]
        self._players = torch.arange(2, dtype=torch.int64, device=self.device)
        self._tower_centers = torch.tensor(
            (
                (3_500, 6_500, 1_500),
                (14_500, 6_500, 1_500),
                (9_000, 2_500, 2_000),
                (3_500, 25_500, 1_500),
                (14_500, 25_500, 1_500),
                (9_000, 29_500, 2_000),
            ),
            dtype=torch.int64,
            device=self.device,
        )

    def _validate_state(self, state: FastActionState) -> None:
        state.validate()
        if state.device != self.device:
            raise ValueError("catalog and action state must use the same device")

    def decode(self, action_ids: torch.Tensor) -> FastActionSelection:
        """Decode ``[batch, 2]`` canonical actions without host synchronization."""

        action_ids = action_ids.to(device=self.device, dtype=torch.int64)
        if action_ids.ndim != 2 or action_ids.shape[1] != 2:
            raise ValueError("action_ids must have shape [batch, 2]")
        valid = (action_ids >= 0) & (action_ids < NUM_ACTIONS)
        placement = valid & (action_ids < NO_OP_ACTION)
        safe_action = torch.where(placement, action_ids, torch.zeros_like(action_ids))
        slot = safe_action // NUM_TILES
        tile = safe_action % NUM_TILES
        player = self._players.view(1, 2).expand_as(action_ids)
        x = self.world_x_units[player, tile]
        y = self.world_y_units[player, tile]
        minus_one = torch.full_like(slot, -1)
        return FastActionSelection(
            action_ids=action_ids,
            valid_input=valid,
            is_no_op=(action_ids == NO_OP_ACTION) | ~valid,
            slot=torch.where(placement, slot, minus_one),
            tile=torch.where(placement, tile, minus_one),
            world_x_units=torch.where(placement, x, torch.zeros_like(x)),
            world_y_units=torch.where(placement, y, torch.zeros_like(y)),
        )

    def _deploy_zone(self, state: FastActionState) -> torch.Tensor:
        x = self.world_x.view(1, 2, NUM_TILES)
        y = self.world_y.view(1, 2, NUM_TILES)
        player = self._players.view(1, 2, 1)
        blue = ((y >= 1) & (y < 15)) | ((x >= 6) & (x < 12) & (y >= 0) & (y < 6))
        red = ((y >= 17) & (y < 31)) | ((x >= 6) & (x < 12) & (y >= 26) & (y < 32))
        base = torch.where(player == 0, blue, red)
        enemy = 1 - player.expand(state.batch_size, 2, 1)
        enemy_towers = state.tower_alive.gather(1, enemy.expand(-1, -1, 3))
        left_dead = ~enemy_towers[:, :, 0:1]
        right_dead = ~enemy_towers[:, :, 1:2]
        extra_blue = (left_dead & (x < 9) & (y >= 17) & (y < 21)) | (
            right_dead & (x >= 9) & (y >= 17) & (y < 21)
        )
        extra_red = (left_dead & (x < 9) & (y >= 11) & (y < 15)) | (
            right_dead & (x >= 9) & (y >= 11) & (y < 15)
        )
        return base | torch.where(player == 0, extra_blue, extra_red)

    def _tower_blocked(self, state: FastActionState) -> torch.Tensor:
        centers = self._tower_centers
        x = self.world_x_units.view(1, 2, NUM_TILES, 1)
        y = self.world_y_units.view(1, 2, NUM_TILES, 1)
        covered = (
            torch.abs(x - centers[:, 0].view(1, 1, 1, 6))
            <= centers[:, 2].view(1, 1, 1, 6)
        ) & (
            torch.abs(y - centers[:, 1].view(1, 1, 1, 6))
            <= centers[:, 2].view(1, 1, 1, 6)
        )
        alive = state.tower_alive.reshape(state.batch_size, 1, 1, 6)
        return (covered & alive).any(dim=-1)

    def legal_action_mask(self, state: FastActionState) -> torch.Tensor:
        """Return an exact mask for the ordinary fast-engine action contract.

        The result depends only on pre-action public mechanics state and the
        actor's private hand/elixir.  It never reads chosen/expert labels.
        Unsupported spell/ability identities fail closed; no-op remains legal.
        """

        self._validate_state(state)
        card_ids = state.hand_ids
        known = (card_ids > 0) & (card_ids < self.catalog.size)
        safe_card = card_ids.clamp(0, self.catalog.size - 1)
        entity_card = self.catalog.kind[safe_card] >= 0
        spell_card = ~entity_card & (
            (self.catalog.effect_kind[safe_card] >= 0)
            | self.catalog.rolling_enabled[safe_card]
        )
        supported = (
            known
            & (entity_card | spell_card)
            & self.catalog.training_supported[safe_card]
        )
        affordable = state.elixir[..., None] >= self.catalog.elixir_cost[safe_card]
        playable = supported & affordable & state.player_alive[..., None]

        zone = self._deploy_zone(state).unsqueeze(2)
        non_blocked = self.non_blocked.view(1, 2, 1, NUM_TILES)
        tower_free = ~self._tower_blocked(state).unsqueeze(2)
        enemy_side = self.catalog.can_deploy_on_enemy_side[safe_card][..., None]
        entity_candidates = (
            non_blocked
            & tower_free
            & torch.where(enemy_side, torch.ones_like(zone), zone)
        )
        margin = self.catalog.deploy_w_tile_margin[safe_card].to(torch.int64)[..., None]
        x = self.world_x.view(1, 2, 1, NUM_TILES)
        entity_candidates &= (x >= margin) & (x < BOARD_WIDTH - margin)
        # Spells target absolute arena coordinates rather than occupying a
        # deployment tile, so river/tower/entity placement blockers do not
        # apply. Unsupported spell shapes already fail closed above.
        candidates = torch.where(
            spell_card[..., None],
            torch.ones_like(entity_candidates),
            entity_candidates,
        )

        mask = torch.zeros(
            (state.batch_size, 2, NUM_ACTIONS),
            dtype=torch.bool,
            device=self.device,
        )
        mask[:, :, :NO_OP_ACTION] = (candidates & playable[..., None]).reshape(
            state.batch_size, 2, NO_OP_ACTION
        )
        mask[:, :, NO_OP_ACTION] = True
        # Champion abilities are mechanic-owned and intentionally fail closed.
        mask[:, :, ABILITY_ACTION] = False
        return mask

    def ingress(
        self,
        state: FastActionState,
        action_ids: torch.Tensor,
        *,
        legal_mask: torch.Tensor | None = None,
    ) -> FastActionIngressResult:
        """Spend, rotate, and emit player-0 then player-1 deployment requests."""

        self._validate_state(state)
        selection = self.decode(action_ids)
        if action_ids.shape[0] != state.batch_size:
            raise ValueError("action_ids batch does not match action state")
        if legal_mask is None:
            legal_mask = self.legal_action_mask(state)
        if legal_mask.shape != (state.batch_size, 2, NUM_ACTIONS):
            raise ValueError("legal_mask must have shape [batch, 2, NUM_ACTIONS]")
        safe_action = selection.action_ids.clamp(0, NUM_ACTIONS - 1)
        selected_legal = legal_mask.gather(2, safe_action.unsqueeze(-1)).squeeze(-1)
        accepted = selection.valid_input & selected_legal
        deployment = accepted & (selection.action_ids < NO_OP_ACTION)

        safe_slot = selection.slot.clamp(0, NUM_HAND_SLOTS - 1)
        card_ids = state.hand_ids.gather(2, safe_slot.unsqueeze(-1)).squeeze(-1)
        selected_card = card_ids.clamp(0, self.catalog.size - 1)
        entity_deployment = deployment & (self.catalog.kind[selected_card] >= 0)
        spell_cast = deployment & ~entity_deployment
        next_ids = state.own_next
        replacement = torch.where(deployment, next_ids, card_ids)
        state.hand_ids.scatter_(2, safe_slot.unsqueeze(-1), replacement.unsqueeze(-1))

        head = state.cycle_head
        current_queue = state.cycle_ids.gather(2, head.unsqueeze(-1)).squeeze(-1)
        queue_value = torch.where(deployment, card_ids, current_queue)
        state.cycle_ids.scatter_(2, head.unsqueeze(-1), queue_value.unsqueeze(-1))
        state.cycle_head.copy_(
            torch.where(deployment, (head + 1) % FAST_CYCLE_SIZE, head)
        )
        cost = self.catalog.elixir_cost[card_ids.clamp(0, self.catalog.size - 1)]
        state.elixir.sub_(torch.where(deployment, cost, torch.zeros_like(cost)))

        requests: list[FastDeploymentRequest] = []
        for player_id in (0, 1):
            player_card = selected_card[:, player_id]
            requests.append(
                FastDeploymentRequest(
                    valid=entity_deployment[:, player_id],
                    owner=torch.full(
                        (state.batch_size,),
                        player_id,
                        dtype=torch.int64,
                        device=self.device,
                    ),
                    card_id=card_ids[:, player_id],
                    kind=self.catalog.kind[player_card],
                    x_units=selection.world_x_units[:, player_id].to(torch.int32),
                    y_units=selection.world_y_units[:, player_id].to(torch.int32),
                    hp=self.catalog.hitpoints[player_card],
                    deploy_ticks=self.catalog.deploy_ticks[player_card],
                    summon_count=self.catalog.summon_count[player_card],
                    summon_radius_units=self.catalog.summon_radius_units[player_card],
                )
            )
        return FastActionIngressResult(
            accepted=accepted,
            deployment_accepted=deployment,
            entity_deployment=entity_deployment,
            spell_cast=spell_cast,
            selected_card_ids=card_ids,
            selection=selection,
            requests=(requests[0], requests[1]),
        )

    def regenerate_elixir_(
        self,
        state: FastActionState,
        *,
        ticks: int = 1,
        tick_seconds: float = 0.05,
        multiplier: float | torch.Tensor = 1.0,
        live: torch.Tensor | None = None,
    ) -> None:
        """Regenerate fractional elixir, supporting 1x/2x/3x match phases."""

        self._validate_state(state)
        if ticks < 0:
            raise ValueError("ticks must be non-negative")
        factor = torch.as_tensor(
            multiplier, dtype=state.elixir.dtype, device=self.device
        )
        delta = float(ticks) * float(tick_seconds) * factor / FAST_BASE_ELIXIR_SECONDS
        next_elixir = torch.minimum(state.max_elixir, state.elixir + delta)
        if live is None:
            live = state.player_alive
        if live.shape != (state.batch_size, 2):
            raise ValueError("live must have shape [batch, 2]")
        state.elixir.copy_(torch.where(live, next_elixir, state.elixir))


__all__ = [
    "FAST_BASE_ELIXIR_SECONDS",
    "FAST_CYCLE_SIZE",
    "FAST_MAX_ELIXIR",
    "FastActionIngressResult",
    "FastActionKernel",
    "FastActionSelection",
    "FastActionState",
]
