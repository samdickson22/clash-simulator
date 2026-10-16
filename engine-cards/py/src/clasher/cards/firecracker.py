from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..mechanics.mechanic_base import BaseMechanic
from ..kinematics import tiles_to_logic_units

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class AttackRecoil(BaseMechanic):
    """Move an attacker backward by its serialized attack pushback."""
    recoil_distance: float = 1.0

    def on_attach(self, entity: 'Entity') -> None:
        configured_recoil = getattr(entity.card_stats, "attack_pushback", None)
        if configured_recoil:
            self.recoil_distance = float(configured_recoil)

    def on_attack_committed(self, entity: 'Entity', target: 'Entity') -> None:
        if target is None:
            return
        target_position = target.position
        dx_units = tiles_to_logic_units(entity.position.x - target_position.x)
        dy_units = tiles_to_logic_units(entity.position.y - target_position.y)
        if dx_units == 0 and dy_units == 0:
            return
        battle_state = getattr(entity, "battle_state", None)
        if battle_state is None:
            return
        from ..mechanics.shared.knockback import apply_radial_knockback

        apply_radial_knockback(
            entity,
            battle_state,
            target_position,
            self.recoil_distance,
            source_kind=getattr(entity.card_stats, "name", None),
            ignores_mass=True,
            interrupts_combat=False,
        )


FirecrackerRecoil = AttackRecoil
