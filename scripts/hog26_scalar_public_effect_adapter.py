"""Diagnostic scalar spell appearance adapter; not a full visibility registry."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import torch

from clasher.dynamic_spells import create_spell_from_json, load_dynamic_spells
from clasher.entities import (
    AreaEffect,
    Graveyard,
    Projectile,
    RollingProjectile,
    SpawnProjectile,
)
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import (
    AreaEffectSpell,
    DirectDamageSpell,
    GraveyardSpell,
    ProjectileSpell,
    RollingProjectileSpell,
    SpawnProjectileSpell,
    TornadoSpell,
)
from scripts.hog26_public_effect_probe import project_visible_effects


@dataclass(frozen=True)
class ScalarArrowsAppearance:
    """Setup-only serialized identity, with no combat payload."""

    token: int

    @classmethod
    def compile(cls, loader, vocabulary):
        raw = loader.get_card("Arrows")._raw_entry
        spell = create_spell_from_json(raw, loader.load_card_definitions())
        identity = raw.get("projectileData", {}).get("name")
        token = vocabulary.resolve(identity, "projectile") if identity else 0
        if (type(spell) is not ProjectileSpell or spell.multiple_projectiles != 10
                or spell.damage_waves != 3 or token <= 1):
            raise ValueError("Arrows has no audited serialized projectile appearance")
        return cls(token)

    def bind_cast(self, created_entities: Iterable[Projectile]):
        """Bind the exact newly-created entity receipt at a known Arrows cast.

        Caller owns cast provenance. Runtime source/spell names are never used
        to infer identity. This registration is not an actor-visible event.
        """
        entities = tuple(created_entities)
        if (len(entities) != 30 or len({id(e) for e in entities}) != 30
                or any(type(e) is not Projectile for e in entities)):
            raise ValueError("Arrows cast receipt must contain 30 distinct projectiles")
        return tuple(ScalarEffectAppearance(e, self.token) for e in entities)


@dataclass(frozen=True)
class ScalarSpellAppearance:
    """A bounded factory-checked appearance rule, separate from combat data."""

    token: int
    entity_type: type | None
    appearance_kind: int

    @classmethod
    def compile(cls, card_name, loader, vocabulary):
        if card_name not in {"Fireball", "GiantSnowball", "Rocket", "Log", "BarbLog",
                             "GoblinBarrel", "Poison", "BarbarianBarrel", "Earthquake", "Freeze",
                             "Tornado", "Graveyard", "Zap"}:
            raise ValueError("spell family has no audited scalar appearance rule")
        raw = loader.get_card(card_name)._raw_entry
        spell = create_spell_from_json(raw, loader.load_card_definitions())
        if card_name == "Graveyard":
            spell = load_dynamic_spells(loader.data_file)[raw["name"]]
        if card_name == "Zap":
            if type(spell) is not DirectDamageSpell:
                raise ValueError("Zap no longer uses audited zero-entity direct damage")
            # Serialized area data describe damage, not a persistent scalar sprite.
            return cls(0, None, 0)
        projectile = raw.get("projectileData", {})
        namespace, kind = "projectile", 1
        if card_name in {"Log", "BarbLog", "BarbarianBarrel"}:
            factory, entity_type = RollingProjectileSpell, RollingProjectile
            identity = projectile.get("spawnProjectileData", {}).get("name")
        elif card_name == "GoblinBarrel":
            factory, entity_type = SpawnProjectileSpell, SpawnProjectile
            identity = projectile.get("name")
        elif card_name in {"Poison", "Earthquake", "Freeze", "Tornado", "Graveyard"}:
            factory, entity_type = {
                "Tornado": (TornadoSpell, AreaEffect),
                "Graveyard": (GraveyardSpell, Graveyard),
            }.get(card_name, (AreaEffectSpell, AreaEffect))
            identity = raw.get("areaEffectObjectData", {}).get("name")
            namespace, kind = "area_effect", 2
        else:
            factory, entity_type = ProjectileSpell, Projectile
            identity = projectile.get("name")
            if spell.multiple_projectiles != 1 or spell.damage_waves != 1:
                raise ValueError("single-projectile lifecycle changed")
        token = vocabulary.resolve(identity, namespace) if identity else 0
        if type(spell) is not factory or token <= 1:
            raise ValueError("spell has no audited serialized appearance")
        return cls(token, entity_type, kind)

    def bind_cast(self, created_entities):
        """Bind an exact known cast receipt; never inspect source labels."""
        entities = tuple(created_entities)
        if self.entity_type is None:
            if entities:
                raise ValueError("zero-entity spell cast created unresolved child objects")
            return ()
        if len(entities) != 1 or type(entities[0]) is not self.entity_type:
            raise ValueError("spell cast receipt differs from audited entity lifecycle")
        return (ScalarEffectAppearance(entities[0], self.token, self.entity_type,
                                       self.appearance_kind),)


@dataclass(frozen=True)
class ScalarEffectAppearance:
    entity: Projectile | RollingProjectile | AreaEffect | Graveyard
    token: int
    entity_type: type = Projectile
    appearance_kind: int = 1


def project_scalar_public_effects(
    effects: Iterable,
    appearances: Iterable[ScalarEffectAppearance],
    *,
    visible_to: Callable[[object, int], bool],
):
    """Return packed appearance tokens, six public features, and seat masks.

    Explicit visibility is necessary in addition to lifecycle eligibility.
    Hidden entries have no output slots. Targets, damage, source labels,
    lifetimes, hit ledgers, and future payloads never reach the projection API.
    Unknown currently visible effects fail closed; only compiled spell rules qualify.
    """
    bindings = {}
    for binding in appearances:
        key = id(binding.entity)
        if key in bindings or binding.token <= 1:
            raise ValueError("invalid or duplicate scalar appearance binding")
        bindings[key] = binding
    positions, owners, tokens, visibility, kinds = [], [], [], [], []
    seen = set()
    for entity in effects:
        if id(entity) in seen:
            raise ValueError("duplicate scalar effect")
        seen.add(id(entity))
        if not entity.is_alive:
            continue
        if isinstance(entity, Projectile) and entity.launch_delay > 0:
            continue
        if (isinstance(entity, SpawnProjectile)
                and entity.time_alive + 1e-9 < entity.activation_delay):
            continue
        if (isinstance(entity, RollingProjectile)
                and entity.time_alive + 1e-9 < entity.spawn_delay):
            continue
        seats = [bool(visible_to(entity, seat)) for seat in (0, 1)]
        if not any(seats):
            continue
        binding = bindings.get(id(entity))
        if (binding is None or type(entity) is not binding.entity_type
                or binding.appearance_kind not in (1, 2)):
            raise ValueError("visible scalar effect has no audited appearance")
        positions.append([tiles_to_logic_units(entity.position.x),
                          tiles_to_logic_units(entity.position.y)])
        owners.append(entity.player_id)
        tokens.append(binding.token)
        kinds.append(binding.appearance_kind)
        visibility.append(seats)
    count = len(tokens)
    positions_t = torch.tensor(positions, dtype=torch.int64).reshape(1, count, 2)
    owners_t = torch.tensor(owners, dtype=torch.int64).reshape(1, count)
    visible = torch.tensor(visibility, dtype=torch.bool).reshape(count, 2).T[None]
    features, mask = project_visible_effects(
        positions_t, owners_t, torch.tensor(kinds, dtype=torch.int64).reshape(1, count), visible,
    )
    token_t = torch.tensor(tokens, dtype=torch.int64)[None, None].expand(1, 2, count)
    return torch.where(mask, token_t, 0), features, mask
