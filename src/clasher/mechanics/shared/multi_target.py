from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanic_base import BaseMechanic

if TYPE_CHECKING:
    from ...entities import Entity


@dataclass
class MultipleTargetAttack(BaseMechanic):
    """Resolve serialized simultaneous direct-attack recipients.

    Characters with ``multipleTargets`` commit their primary recipient plus
    the nearest distinct recipients in their own attack range. When
    ``allTargetsHit`` is set, any otherwise-unused hits are committed to the
    primary target instead.
    """

    target_count: int = 2
    all_targets_hit: bool = False
    damage_scale: float = 1.0
    _secondary_target_ids: tuple[int, ...] = ()

    def on_attach(self, entity: "Entity") -> None:
        raw = getattr(entity.card_stats, "_raw_entry", {}) or {}
        character_data = raw.get("summonCharacterData", {}) or {}
        self.target_count = max(
            1,
            int(character_data.get("multipleTargets", self.target_count)),
        )
        self.all_targets_hit = bool(
            character_data.get("allTargetsHit", self.all_targets_hit)
        )

    def on_attack_start(self, entity: "Entity", target: "Entity") -> None:
        """Snapshot every simultaneous recipient before the first hit."""
        candidates = self._ordered_secondary_targets(entity, target)
        secondary = candidates[: max(0, self.target_count - 1)]
        if self.all_targets_hit and len(secondary) < self.target_count - 1:
            secondary.extend(
                [target] * (self.target_count - 1 - len(secondary))
            )
        self._secondary_target_ids = tuple(item.id for item in secondary)

    def resolve_secondary_attack_hits(
        self,
        entity: "Entity",
        primary_target: "Entity",
        damage: float,
        battle_state,
    ) -> None:
        """Resolve secondary recipients with the committed primary damage."""
        if battle_state is None:
            self._secondary_target_ids = ()
            return

        for target_id in self._secondary_target_ids:
            secondary = battle_state.entities.get(target_id)
            if secondary is None:
                continue
            target_damage = float(damage) * self.damage_scale
            for mechanic in entity.mechanics:
                modifier = getattr(mechanic, "modify_outgoing_damage", None)
                if callable(modifier):
                    target_damage = float(
                        modifier(entity, secondary, target_damage)
                    )
            secondary.take_damage(target_damage)
            for mechanic in entity.mechanics:
                if mechanic is self:
                    continue
                on_secondary_hit = getattr(
                    mechanic,
                    "on_secondary_attack_hit",
                    None,
                )
                if callable(on_secondary_hit):
                    on_secondary_hit(entity, secondary)
        self._secondary_target_ids = ()

    def _ordered_secondary_targets(
        self,
        entity: "Entity",
        primary_target: "Entity",
    ) -> list["Entity"]:
        candidates: list[tuple[Entity, float]] = []
        for other in entity.battle_state.entities.values():
            if (
                other is primary_target
                or other.player_id == entity.player_id
                or not other.is_alive
                or getattr(other, "entity_kind", 4) in {2, 3}
                or not entity.can_attack_target(other)
            ):
                continue
            candidates.append(
                (other, entity.native_target_distance_to(other))
            )

        ordered: list[Entity] = []
        while candidates:
            selected = entity._select_nearest_target(candidates)
            if selected is None:
                break
            ordered.append(selected)
            candidates = [
                item for item in candidates if item[0] is not selected
            ]
        return ordered
