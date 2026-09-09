"""Diagnostic scalar Arrows appearance adapter; not a full visibility registry."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import torch

from clasher.dynamic_spells import create_spell_from_json
from clasher.entities import Projectile, RollingProjectile
from clasher.kinematics import tiles_to_logic_units
from clasher.spells import ProjectileSpell
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
class ScalarEffectAppearance:
    entity: Projectile
    token: int


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
    Unknown currently visible effects fail closed; this supports Arrows only.
    """
    bindings = {}
    for binding in appearances:
        key = id(binding.entity)
        if key in bindings or binding.token <= 1:
            raise ValueError("invalid or duplicate scalar appearance binding")
        bindings[key] = binding
    positions, owners, tokens, visibility = [], [], [], []
    seen = set()
    for entity in effects:
        if id(entity) in seen:
            raise ValueError("duplicate scalar effect")
        seen.add(id(entity))
        if not entity.is_alive:
            continue
        if isinstance(entity, Projectile) and entity.launch_delay > 0:
            continue
        if (isinstance(entity, RollingProjectile)
                and entity.time_alive + 1e-9 < entity.spawn_delay):
            continue
        seats = [bool(visible_to(entity, seat)) for seat in (0, 1)]
        if not any(seats):
            continue
        binding = bindings.get(id(entity))
        if binding is None or type(entity) is not Projectile:
            raise ValueError("visible scalar effect has no audited appearance")
        positions.append([tiles_to_logic_units(entity.position.x),
                          tiles_to_logic_units(entity.position.y)])
        owners.append(entity.player_id)
        tokens.append(binding.token)
        visibility.append(seats)
    count = len(tokens)
    positions_t = torch.tensor(positions, dtype=torch.int64).reshape(1, count, 2)
    owners_t = torch.tensor(owners, dtype=torch.int64).reshape(1, count)
    visible = torch.tensor(visibility, dtype=torch.bool).reshape(count, 2).T[None]
    features, mask = project_visible_effects(
        positions_t, owners_t, torch.ones((1, count), dtype=torch.int64), visible,
    )
    token_t = torch.tensor(tokens, dtype=torch.int64)[None, None].expand(1, 2, count)
    return torch.where(mask, token_t, 0), features, mask
