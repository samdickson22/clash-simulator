"""Numeric checks of reference labels after public actor serialization.

These tolerances describe integer native labels and float32 encoding, not a
camera detector. No simulator trajectory accuracy or gate admission is implied.
"""

from collections import Counter

import numpy as np


def check_reference_packet(snapshot, packet, perspective, *, card_tokens):
    """Return explicit failures; require exact integer round trips and coverage.

    Positions use native thousandths of a tile, health uses the source fraction,
    and own elixir uses hundred-thousandths of capacity. Unavailable channels
    must have zero values and confidence. Native IDs never join actor rows.
    """
    errors = []
    actor = packet.observation
    active = actor.entity_mask
    features = actor.entity_features[active]
    confidence = packet.entity_feature_confidence[active]
    if not np.isfinite(features).all():
        return ["nonfinite entity feature"]
    if (
        not np.isin(features[:, 2:9], (0, 1)).all()
        or not np.all(features[:, 2:4].sum(axis=1) == 1)
        or not np.all(features[:, 4:9].sum(axis=1) == 1)
    ):
        errors.append("invalid ownership or entity-kind encoding")
    if actor.board_rotated is not bool(perspective):
        errors.append("wrong board rotation")
    if not np.all(packet.entity_id_confidence[active] == 1):
        errors.append("reference identity confidence is incomplete")
    if not np.all(confidence[:, :9] == 1):
        errors.append("reference geometry confidence is incomplete")
    if np.any(actor.entity_features[:, 10:]) or np.any(
        packet.entity_feature_confidence[:, 10:]
    ):
        errors.append("unobserved entity state was exposed")
    if np.any(actor.opponent_history_ids) or np.any(actor.opponent_seen_card_ids):
        errors.append("unobserved opponent history was exposed")
    if np.any(packet.opponent_history_confidence) or np.any(
        packet.opponent_seen_card_confidence
    ):
        errors.append("unobserved opponent history has confidence")
    observed_globals = {5, 8, 9, 10, 11, 12, 13}
    for i, (value, certainty) in enumerate(
        zip(actor.global_features, packet.global_feature_confidence)
    ):
        if i not in observed_globals and (value != 0 or certainty != 0):
            errors.append(f"unobserved global channel {i}")
        if i in observed_globals and certainty != 1:
            errors.append(f"missing reference global confidence {i}")
    own = next(p for p in snapshot["players"] if p["owner"] == perspective)
    if (
        not np.isfinite(actor.global_features[5])
        or round(float(actor.global_features[5]) * 100000) != own["elixirRaw"]
    ):
        errors.append("own elixir integer round trip failed")

    hand = sorted(own["hand"], key=lambda c: c["handIndex"]) + [own["nextCard"]]
    expected_hand = [card_tokens[c["cardId"]] for c in hand]
    if actor.hand_ids.tolist() != expected_hand:
        errors.append("own hand or visible next card differs from reference")
    if not np.all(packet.hand_id_confidence == 1):
        errors.append("own hand confidence missing")

    # Match multisets, not row order or native IDs. HP fractions are rounded to
    # their float32 reference encoding before comparison, with no gameplay error
    # tolerance added. This catches lost/duplicated/swapped-health bodies.
    expected, actual = Counter(), Counter()
    for obj in snapshot["objects"]:
        if obj.get("hp") is None or obj["hp"] == 0:
            continue
        x, y = obj["x"], obj["y"]
        if perspective:
            x, y = 18000 - x, 32000 - y
        expected[
            (
                x,
                y,
                obj["owner"] == perspective,
                float(np.float32(obj["hp"] / obj["maxHp"])),
            )
        ] += 1
    for row, certainty in zip(features, confidence):
        if row[4] + row[5] == 0:
            if row[9] != 0 or certainty[9] != 0:
                errors.append("effect claims body HP")
            continue
        if certainty[9] != 1:
            errors.append("body HP confidence missing")
        actual[
            (
                round(float(row[0]) * 18000),
                round(float(row[1]) * 32000),
                bool(row[2]),
                float(row[9]),
            )
        ] += 1
    if actual != expected:
        errors.append("body position/owner/HP multiset differs from reference")
    # Crown arrays preserve canonical left/right, including zero for removed
    # towers. Expected anchors are the six fixed level11 reference positions.
    towers = {
        (o["owner"], o["x"], o["y"]): o
        for o in snapshot["objects"]
        if o["cardId"] == -1 and o.get("hp") is not None
    }
    for owner in (0, 1):
        for x, y, column in (
            (3500, 6500 if owner == 0 else 25500, 0),
            (14500, 6500 if owner == 0 else 25500, 1),
            (9000, 3000 if owner == 0 else 29000, 2),
        ):
            obj = towers.get((owner, x, y))
            hp = 0.0 if obj is None else float(np.float32(obj["hp"] / obj["maxHp"]))
            col = (1 - column if perspective and column != 2 else column) + (
                8 if owner == perspective else 11
            )
            if actor.global_features[col] != hp:
                errors.append(f"Crown HP mismatch at channel {col}")
    return errors


def check_reference_entities(
    snapshot,
    rich,
    packet,
    perspective,
    *,
    body_tokens,
    effect_tokens,
    tower_tokens,
    levels,
    level_confidence,
):
    """Match every declared live reference object, including transient effects.

    Token maps are supplied from the pinned card/catalog declarations, separately
    from adapter output. This checks correspondence, not rendered detectability.
    """
    actor = packet.observation
    if actor.entity_levels is None or actor.entity_level_confidence is None:
        return ["level-aware reference packet required"]
    rich_by_id = {o["nativeObjectId"]: o for o in rich["objects"]}
    expected = Counter()
    for obj in snapshot["objects"]:
        identity = obj["nativeObjectId"]
        if obj.get("hp") == 0:
            continue
        if obj.get("hp") is None:
            detail = rich_by_id[identity]
            kind, token = effect_tokens[detail["dataGlobalId"]]
        elif obj["cardId"] == -1:
            kind, token = 1, tower_tokens["KingTower" if obj["x"] == 9000 else "Tower"]
        else:
            kind, token = body_tokens[obj["cardId"]]
        x, y = obj["x"], obj["y"]
        if perspective:
            x, y = 18000 - x, 32000 - y
        hp = (
            0.0
            if obj.get("hp") is None
            else float(np.float32(obj["hp"] / obj["maxHp"]))
        )
        level = levels.get(identity, 0)
        certainty = float(np.float32(level_confidence.get(identity, 0.0)))
        expected[
            (token, kind, x, y, obj["owner"] == perspective, hp, level, certainty)
        ] += 1
    actual = Counter()
    for index in np.flatnonzero(actor.entity_mask):
        row = actor.entity_features[index]
        if not np.isfinite(row).all():
            return ["nonfinite entity feature"]
        actual[
            (
                int(actor.entity_ids[index]),
                int(np.argmax(row[4:9])),
                round(float(row[0]) * 18000),
                round(float(row[1]) * 32000),
                bool(row[2]),
                float(row[9]),
                int(actor.entity_levels[index]),
                float(actor.entity_level_confidence[index]),
            )
        ] += 1
    if actual != expected:
        return [
            "entity identity/kind/position/HP/level multiset differs from reference"
        ]
    return []


def reference_token_maps(builder, names, catalog):
    """Resolve the declared label vocabulary without inspecting adapter output."""
    cards, bodies = {}, {}
    for name in names:
        card = builder.loader.get_card(name)
        identity = card._raw_entry["id"]
        cards[identity] = builder.token_id(name, namespace="card_action")
        if card._raw_entry.get("summonCharacterData"):
            building = card.card_type.lower() == "building"
            bodies[identity] = (
                int(building),
                builder.token_id(
                    card.name, namespace="building_body" if building else "troop_body"
                ),
            )
    effects = {
        10000000 + i: (2, builder.token_id(n, namespace="projectile"))
        for i, n in enumerate(catalog.names)
    }
    effects[22000007] = (
        3,
        builder.token_id("FreezeIceGolemite", namespace="area_effect"),
    )
    towers = {n: builder.token_id(n, namespace="tower") for n in ("Tower", "KingTower")}
    return cards, bodies, effects, towers
