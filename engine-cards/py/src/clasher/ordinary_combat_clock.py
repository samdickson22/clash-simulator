"""Adapters between ordinary native clocks and the legacy cooldown projection."""

from .attack_clock import OrdinaryAttackClock
from .cards.ice_spirit import IceSpiritFreeze
from .mechanics.mechanic_base import BaseMechanic


def supported(entity) -> bool:
    stats = entity.card_stats
    if stats is None or entity.entity_kind not in (0, 1):
        return False
    if getattr(stats, "name", None) in {"Tower", "KingTower"}:
        return False
    hit = int(getattr(stats, "hit_speed", 0) or 0)
    load = int(getattr(stats, "load_time", 0) or 0)
    if not 0 <= load <= hit or hit <= 0:
        return False
    if (
        getattr(stats, "load_first_hit", False)
        or getattr(stats, "attack_sequence", None)
        or getattr(stats, "override_attack_finish_time", False)
    ):
        return False
    if getattr(stats, "first_hit_time", None) != hit - load:
        return False
    # Ice Spirit uses the ordinary clock until its launch hook replaces the
    # character with a projectile. Other custom handlers await native coverage.
    return all(
        getattr(type(mechanic), method, None) is getattr(BaseMechanic, method)
        for mechanic in entity.mechanics
        if not isinstance(mechanic, IceSpiritFreeze)
        for method in ("on_attack_start", "on_attack_committed")
    )


def seed_remaining(entity, clock, remaining: float) -> None:
    """Map an explicit setup/interruption write, not an ordinary hit commit."""
    remaining_ms = max(0, round(remaining * 1000))
    first = clock.hit_interval_ms - clock.load_time_ms
    clock.stop_hit()
    entity._ordinary_force_due = remaining_ms == 0
    if 0 < remaining_ms < first:
        clock.hit_timeline_ms = clock.hit_interval_ms - remaining_ms
        clock.load_remaining_ms = 0
    else:
        clock.load_remaining_ms = min(clock.load_time_ms, max(0, remaining_ms - first))
    clock.finish_elapsed_ms = entity._attack_finish_elapsed_ms
    entity._ordinary_clock_projection = remaining


def get_clock(entity):
    if not supported(entity):
        entity._ordinary_clock = None
        return None
    interval = entity.get_base_attack_interval_seconds()
    if entity.attack_cooldown > interval + 1e-8:
        # Explicit synthetic setup deadlines can exceed a native hit cycle.
        # Keep their existing countdown rather than silently truncating them.
        entity._ordinary_clock = None
        return None
    clock = entity._ordinary_clock
    if clock is None:
        clock = OrdinaryAttackClock(int(entity.card_stats.hit_speed), int(entity.card_stats.load_time or 0))
        entity._ordinary_clock = clock
        seed_remaining(entity, clock, entity.attack_cooldown)
    elif abs(entity.attack_cooldown - entity._ordinary_clock_projection) > 1e-8:
        seed_remaining(entity, clock, entity.attack_cooldown)
    return clock


def publish(entity, clock, *, due: bool = False) -> None:
    if due or entity._ordinary_force_due:
        remaining = 0
    elif clock.finish_elapsed_ms or not clock.hit_timeline_ms:
        remaining = clock.load_remaining_ms + clock.hit_interval_ms - clock.load_time_ms
    else:
        remaining = clock.hit_interval_ms - clock.hit_timeline_ms % clock.hit_interval_ms
    entity.attack_cooldown = remaining / 1000
    entity._ordinary_clock_projection = entity.attack_cooldown
    entity._ordinary_clock_due = due


def advance(entity, dt: float, *, engaged: bool) -> bool:
    clock = get_clock(entity)
    if clock is None:
        return False
    pushing = entity._knockback_target is not None and not entity._knockback_interrupts_combat
    active = engaged and not pushing
    elapsed_ms = max(0, round(dt * 1000))
    load_work = 0 if entity._attack_preload_blocked and not clock.hit_timeline_ms else elapsed_ms
    if entity._ordinary_force_due and active and not entity.is_stunned():
        entity._ordinary_force_due = False
        clock.hit_timeline_ms = clock.hit_interval_ms
        clock.load_remaining_ms = clock.load_time_ms
        hits = 1
    else:
        hits = clock.advance(
            elapsed_ms, max(0, round(dt * 1000 * entity.get_attack_rate_multiplier())),
            engaged=active, frozen=entity.is_stunned(), load_work_ms=load_work,
        )
    publish(entity, clock, due=bool(hits))
    return True


def stop_hit(entity) -> None:
    clock = get_clock(entity)
    if clock is not None:
        clock.stop_hit()
        entity._ordinary_force_due = False
        publish(entity, clock)
