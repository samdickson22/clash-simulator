"""Explicit scalar reference actor projection; collection is not authorized yet.

Bodies expose current public position/HP and declared static card statistics.
Effect identities and visibility come from separately bound appearance receipts.
Private target, clock, damage, lifetime, and RNG fields are not actor features.
"""

import math

import numpy as np

from clasher.entities import Building, Troop
from clasher.rl.structured_obs import ActorObservation, EntityCapacityError
from scripts.hog26_scalar_public_effect_adapter import project_scalar_public_effects


def build_scalar_reference_actors(battle, builder, *, appearances, visible_to):
    """Return two fixed-capacity actor views; reject unresolved visible effects.

    Caller must supply an audited current-visibility predicate. This is a new
    observation contract, not byte parity with the former native projection.
    Own hand/HUD access reuses the reviewed actor-only builder helpers; neither
    critic construction nor simulator legality is called.
    """
    bodies = [e for e in battle.entities.values() if isinstance(e, (Troop, Building))]
    effects = [e for e in battle.entities.values() if not isinstance(e, (Troop, Building))]
    effect_ids, effect_features, effect_mask = project_scalar_public_effects(
        effects, appearances, visible_to=visible_to,
    )
    actors = []
    unknown = builder.token_id(None)
    for seat in (0, 1):
        rows = []
        for entity in bodies:
            if not entity.is_alive or not visible_to(entity, seat):
                continue
            stats = entity.card_stats
            name = getattr(stats, "name", "")
            namespace = "tower" if name in {"Tower", "KingTower"} else (
                "building_body" if isinstance(entity, Building) else "troop_body")
            if namespace != "tower":
                # Summoning cards can have a different public body identity
                # (Skeletons summons Skeleton). Use serialized body metadata.
                name = (getattr(stats, "summon_character_data", None) or {}).get("name") or name
            token = builder.token_id(name, namespace=namespace)
            if token <= 0 or token == unknown:
                raise ValueError(f"visible body has no typed appearance: {name}")
            row = np.zeros(32, dtype=np.float32)
            x, y = builder._canonical_position(entity.position.x, entity.position.y, seat)
            row[:4] = [np.clip(x / 18, 0, 1), np.clip(y / 32, 0, 1),
                       entity.player_id == seat, entity.player_id != seat]
            row[5 if isinstance(entity, Building) else 4] = 1
            row[9] = np.clip(entity.hitpoints / max(1, entity.max_hitpoints), 0, 1)
            row[10] = builder._shield_fraction(entity)
            # Static visible-body metadata only; never entity.damage or its
            # temporary speed/range modifiers and internal facing target.
            speed = float(getattr(stats, "speed", 0) or 0)
            row[23] = np.clip(math.log1p(abs(speed)) / math.log1p(1000), 0, 1)
            row[24] = np.clip(float(getattr(stats, "range", 0) or 0) / 12, 0, 1)
            row[25] = np.clip(float(getattr(stats, "sight_range", 0) or 0) / 12, 0, 1)
            row[26] = np.clip(float(getattr(stats, "collision_radius", 0) or 0) / 3, 0, 1)
            row[30] = np.clip(math.log1p(max(0, float(getattr(stats, "damage", 0) or 0))) / 8, 0, 1)
            rows.append((token, row))
        for index in np.flatnonzero(effect_mask[0, seat].numpy()):
            row = np.zeros(32, dtype=np.float32)
            observed = effect_features[0, seat, index].numpy()
            row[:4], row[6:8] = observed[:4], observed[4:6]
            rows.append((int(effect_ids[0, seat, index]), row))
        if len(rows) > builder.max_entities:
            raise EntityCapacityError("visible scalar reference scene exceeds actor capacity")
        rows.sort(key=lambda item: (int(np.argmax(item[1][4:9])),
                                   item[1][3], item[0], float(item[1][1]), float(item[1][0])))
        ids = np.zeros(builder.max_entities, dtype=np.int64)
        features = np.zeros((builder.max_entities, 32), dtype=np.float32)
        mask = np.zeros(builder.max_entities, dtype=np.bool_)
        for index, (token, row) in enumerate(rows):
            ids[index], features[index], mask[index] = token, row, True
        history_ids, history_ages = builder._opponent_history(battle, seat)
        actors.append(ActorObservation(
            entity_ids=ids, entity_features=features, entity_mask=mask,
            hand_ids=builder._card_ids_for_player(battle, seat),
            global_features=builder._actor_globals(battle, seat),
            opponent_history_ids=history_ids, opponent_history_ages=history_ages,
            opponent_seen_card_ids=builder._opponent_seen_cards(battle, seat),
        ))
    return tuple(actors)
