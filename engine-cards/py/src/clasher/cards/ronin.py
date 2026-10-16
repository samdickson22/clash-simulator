from dataclasses import dataclass

from ..mechanics.mechanic_base import BaseMechanic


@dataclass
class RoninCounter(BaseMechanic):
    """Batch C1: Ronin's passive counter, ported from RoyaleSim (MIT) card.rs `ParryDef` and state.rs
    `note_parry`/`parry_pick`/`parry_pass` (base card, no ability).

    A ready Ronin (also while deploying) that takes a normal direct hit from a ground troop without an
    attack projectile takes 0 instead; the counter then needs ``cooldown_ms``. Its attack progress restarts
    (load, phase and target kept); the attacker gets a ``stop_ms`` buff (movement 0, hit speed 5 %, spawn 0)
    and, ``reflect_delay_ticks`` later, ``damage_scalar`` % of the countered amount (not level scaled, not
    countered again). Flying attackers, buildings, projectiles, spells and dash blows are not countered.
    """

    cooldown_ms: int = 3500
    damage_scalar: int = 200
    stop_ms: int = 500
    reflect_delay_ticks: int = 6

    def on_attach(self, entity) -> None:
        raw = getattr(getattr(entity, "card_stats", None), "_raw_entry", {}) or {}
        data = raw.get("summonCharacterData", {}) or {}
        self.cooldown_ms = int(data.get("counterCooldown", self.cooldown_ms))
        self.damage_scalar = int(data.get("counterDamageScalar", self.damage_scalar))
        self.stop_ms = int(data.get("counterStopTime", self.stop_ms))
        self.reflect_delay_ticks = int(data.get("counterReflectDelay", self.reflect_delay_ticks * 50)) // 50
        entity._ronin_ready_tick = 0
        entity._ronin_pending = []

    def try_counter(self, ronin, attacker, amount: float, battle) -> bool:
        if not ronin.is_alive or battle.tick < ronin._ronin_ready_tick:
            return False
        ronin._ronin_ready_tick = battle.tick + self.cooldown_ms // 50
        from ..ordinary_combat_clock import stop_hit

        stop_hit(ronin)
        ronin._ronin_pending.append(
            (battle.tick + self.reflect_delay_ticks, attacker.id, float(amount) * self.damage_scalar / 100.0)
        )
        attacker.apply_slow(
            self.stop_ms / 1000.0,
            0.0,
            attack_speed_multiplier=0.05,
            spawn_speed_multiplier=0.0,
            source_kind=getattr(ronin.card_stats, "name", None),
        )
        return True

    @staticmethod
    def deliver(ronin, battle) -> None:
        tick = battle.tick
        due = [p for p in ronin._ronin_pending if p[0] <= tick]
        if not due:
            return
        ronin._ronin_pending = [p for p in ronin._ronin_pending if p[0] > tick]
        for _, attacker_id, amount in due:
            attacker = battle.entities.get(attacker_id)
            if attacker is not None and attacker.is_alive:
                attacker.take_damage(amount, source_kind=getattr(ronin.card_stats, "name", None))
