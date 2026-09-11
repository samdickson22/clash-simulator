"""Join registered death appearances to the scalar reference actor projection."""

from clasher.entities import (
    AreaEffect,
    BuffAreaEffect,
    DeathAreaEffectContainer,
    SpawnProjectile,
    TimedExplosive,
    Troop,
)
from scripts.hog26_scalar_actor_projection import (
    build_scalar_reference_actors,
    scalar_body_token,
)
from scripts.hog26_scalar_public_effect_adapter import ScalarEffectAppearance


class ScalarDeathActorAdapter:
    """Exact receipt-based visibility and appearance join; never a type-wide filter.

    Timed bomb bodies retain their serialized building_body identity while
    occupying scalar noncombat effect kind 3. No timer or future explosion
    representation is introduced. Excluding a registered internal scheduler
    does not certify coverage of Lumberjack's possible bottle animation.
    """

    def __init__(self, battle, builder, recorder, *, visible_to):
        if recorder.battle is not battle:
            raise ValueError("death recorder belongs to another battle")
        self.battle = battle
        self.builder = builder
        self.recorder = recorder
        self.current_visible_to = visible_to

    def _registrations(self):
        internal = {}
        for entity in self.recorder.registered_internal_containers:
            if type(entity) is not DeathAreaEffectContainer or id(entity) in internal:
                raise ValueError("invalid exact internal container registration")
            if entity.is_alive and self.battle.entities.get(entity.id) is not entity:
                raise ValueError("live internal container is outside registered battle")
            internal[id(entity)] = entity
        # Royal Delivery is a stationary scheduler, not a visible projectile.
        # Its separately named exact receipts cannot hide arbitrary SpawnProjectiles.
        for entity in getattr(self.recorder, "registered_royal_delivery_schedulers", ()):
            if type(entity) is not SpawnProjectile or id(entity) in internal:
                raise ValueError("invalid exact RoyalDelivery scheduler registration")
            if entity.is_alive and self.battle.entities.get(entity.id) is not entity:
                raise ValueError("live RoyalDelivery scheduler is outside registered battle")
            internal[id(entity)] = entity
        for receipt in getattr(self.recorder, "royal_delivery_recruits", ()):
            entity = receipt.entity
            if type(entity) is not Troop:
                raise ValueError("RoyalDelivery recruit class changed")
            if not entity.is_alive:
                continue
            if self.battle.entities.get(entity.id) is not entity:
                raise ValueError("live RoyalDelivery recruit is outside registered battle")
            if (scalar_body_token(entity, self.builder) != receipt.token
                    or self.builder.token_names[receipt.token] != "troop_body:DeliveryRecruit"):
                raise ValueError("RoyalDelivery recruit lacks current body identity")
        deaths = {}
        for receipt in self.recorder.receipts:
            entity = receipt.entity
            if id(entity) in deaths or id(entity) in internal:
                raise ValueError("duplicate death appearance registration")
            if entity.is_alive and self.battle.entities.get(entity.id) is not entity:
                raise ValueError("live death appearance is outside registered battle")
            if type(entity) is not receipt.rule.entity_type:
                raise ValueError("death appearance entity class changed")
            deaths[id(entity)] = receipt
        return internal, deaths

    def build(self, *, appearances=()):
        internal, deaths = self._registrations()
        bindings = list(appearances)
        for receipt in deaths.values():
            entity, rule = receipt.entity, receipt.rule
            if not entity.is_alive:
                continue
            observed = any(receipt.witnessed_seats[seat]
                           and self.current_visible_to(entity, seat) for seat in (0, 1))
            if not observed:
                continue
            if rule.token <= 1 or rule.token >= len(self.builder.token_names):
                raise ValueError("visible death appearance lacks actor vocabulary identity")
            identity = self.builder.token_names[rule.token]
            if type(entity) is TimedExplosive:
                expected = {"building_body:BalloonBomb", "building_body:BombTowerBomb",
                            "building_body:SkeletonContainerNew"}
                category = "death_body"
            elif type(entity) is AreaEffect:
                expected, category = {"area_effect:FreezeIceGolemite"}, "area"
            elif type(entity) is BuffAreaEffect:
                expected, category = {"area_effect:BarbarianRage"}, "area"
            else:
                raise ValueError("death entity class has no actor mapping")
            if identity not in expected or rule.category != category:
                raise ValueError("death token does not identify the registered current appearance")
            # Existing scalar effects encode entity_kind3 at feature7. This
            # keeps timed bombs out of troop/building combat counts; token
            # namespace still identifies their current body, not an explosion.
            bindings.append(ScalarEffectAppearance(entity, rule.token, type(entity), 2))

        def visible(entity, seat):
            if id(entity) in internal:
                return False
            receipt = deaths.get(id(entity))
            if receipt is not None and not receipt.witnessed_seats[seat]:
                return False
            return self.current_visible_to(entity, seat)

        return build_scalar_reference_actors(
            self.battle, self.builder, appearances=tuple(bindings), visible_to=visible,
        )
