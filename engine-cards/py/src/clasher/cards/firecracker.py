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

        # The recoil is a physical push: it stops the started hit on its first
        # movement frame while the weapon keeps loading (calibration batch 2,
        # cards). Native 15.535 rich snapshots of train Firecrackers show
        # attackTimelineMs 0 and loadRemainingMs 2350 - 50k for k = 1..9 ticks
        # after every launch; a hit restarting at k = 10 shows 550 (= the
        # ordinary clock's loaded work 500 + 50), so the next launch comes 59
        # ticks after the previous one (77/86 same-target pairs; ours 60), and
        # a Firecracker pushed out of reach walks straight back (31/34 aligned
        # shots with the target 7.5-9 tiles away; ours stood in the started-hit
        # leash, 6/34). A LoadFirstHit holder (Sparky, Batch C1) keeps its
        # immediate stop_hit below instead; the calibration did not measure it.
        load_first_hit = bool(getattr(entity.card_stats, "load_first_hit", False))
        armed = apply_radial_knockback(
            entity,
            battle_state,
            target_position,
            self.recoil_distance,
            source_kind=getattr(entity.card_stats, "name", None),
            ignores_mass=True,
            interrupts_combat=False,
            reset_hit_on_movement=not load_first_hit,
        )
        if armed and load_first_hit:
            # Batch C1, ported from RoyaleSim (MIT) state.rs `attack_recoil`: an armed recoil releases
            # a LoadFirstHit unit from its swing (progress 0); a refused one keeps the cycle.
            from ..ordinary_combat_clock import stop_hit

            stop_hit(entity)


FirecrackerRecoil = AttackRecoil
