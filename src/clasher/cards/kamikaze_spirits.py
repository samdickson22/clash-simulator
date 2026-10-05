"""Kamikaze spirits whose impact is plain splash (Fire Spirit) or splash plus heal (Heal Spirit).

Both reuse the Ice Spirit self-projectile lifecycle (launch on attack start, homing
flight at the projectile speed, impact at the committed point). Native data
(decoded-logic-1e505767/characters): FireSpirits Kamikaze=true, FireSpiritsProjectile
Damage 81, Radius 2300, Speed 400; HealSpirit Kamikaze=true, HealSpiritProjectile
Damage 43, Radius 1500, Speed 400, SpawnAreaEffectObject HealSpirit (Radius 2500,
OnlyOwnTroops, IgnoreBuildings, BuffTime 1000) with HealSpiritBuff HealPerSecond 157 at
HitFrequency 250.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..arena import Position
from ..stat_scaling import scale_stat
from .ice_spirit import IceSpiritFreeze

if TYPE_CHECKING:
    from ..entities import Entity


@dataclass
class KamikazeSplash(IceSpiritFreeze):
    """Ice Spirit lifecycle without the freeze: one splash at impact."""

    def _freeze(self, entity: 'Entity', origin: Position) -> None:
        battle_state = getattr(entity, "battle_state", None)
        if battle_state is None:
            return
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        affects_hidden = bool(projectile.get("affectsHidden", False))
        source_kind = getattr(entity.card_stats, "name", None)
        targets = [
            other
            for other in list(battle_state.entities.values())
            if other.player_id != entity.player_id
            and other.is_alive
            and getattr(other, "entity_kind", 4) not in {2, 3}
            and entity.can_affect_target_plane(other)
            and other.intersects_native_area(origin, self.freeze_radius)
            and other.can_receive_area_damage(
                source_kind, affects_hidden=affects_hidden, source_entity=entity,
            )
        ]
        for other in targets:
            other.take_damage(entity.damage, source_kind=source_kind, affects_hidden=affects_hidden)
        self._after_impact(entity, origin)

    def _after_impact(self, entity: 'Entity', origin: Position) -> None:
        return


@dataclass
class HealSpiritBurst(KamikazeSplash):
    heal_radius: float = 2.5
    heal_per_second: float = 157.0
    heal_interval: float = 0.25
    heal_duration: float = 1.0

    def on_attach(self, entity: 'Entity') -> None:
        super().on_attach(entity)
        projectile = getattr(entity.card_stats, "projectile_data", {}) or {}
        area = projectile.get("spawnAreaEffectObjectData", {}) or {}
        buff = area.get("buffData", {}) or {}
        self.heal_radius = float(area.get("radius", 2500) or 2500) / 1000.0
        self.heal_per_second = float(buff.get("healPerSecond", 157) or 157)
        self.heal_interval = float(buff.get("hitFrequency", 250) or 250) / 1000.0
        self.heal_duration = float(area.get("buffTime", area.get("lifeDuration", 1000)) or 1000) / 1000.0

    def _after_impact(self, entity: 'Entity', origin: Position) -> None:
        from ..scope_spells import HealPulse

        battle_state = entity.battle_state
        level = int(getattr(entity.card_stats, "level", 11) or 11)
        per_tick = float(int((scale_stat(self.heal_per_second, level) or 0) * self.heal_interval + 1e-9))
        pulse = HealPulse(
            id=battle_state.next_entity_id,
            position=Position(origin.x, origin.y),
            player_id=entity.player_id, card_stats=None, hitpoints=1, max_hitpoints=1,
            damage=0, range=self.heal_radius, sight_range=self.heal_radius,
            radius=self.heal_radius, duration=self.heal_duration,
            heal_per_tick=per_tick, heal_interval=self.heal_interval,
        )
        pulse.spell_name = "HealSpirit"
        pulse.battle_state = battle_state
        battle_state.entities[pulse.id] = pulse
        battle_state.next_entity_id += 1
