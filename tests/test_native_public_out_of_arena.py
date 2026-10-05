"""Bounded out-of-arena native positions (thrown Log) project clipped.

The thrown LogProjectile starts MinDistance=3000 behind a deploy-zone
placement, so owner 1 at y=31500 yields y=34500 and owner 0 at y=500 yields
y=-2500. Frames beyond the documented margin remain corrupt and must fail.
"""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from clasher.arena import Position
from clasher.battle import BattleState
from clasher.rl.native_public_observation import (
    NATIVE_OUT_OF_ARENA_MARGIN,
    NativeProjectileCatalog,
    NativePublicObservationAdapter,
    NativePublicProjectionError,
    NativePublicScope,
    native_out_of_arena_positions,
)
from clasher.rl.public_observation import reference_public_observation
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.public_reference_checks import (
    check_reference_entities,
    check_reference_packet,
    reference_token_maps,
)
from clasher.rl.structured_obs import StructuredObservationBuilder

FIXTURES = Path(__file__).parent / 'fixtures'
LOG_PHASES = json.loads((FIXTURES / 'native_public_log_phases_15_535_86.json').read_text())
FIREBALL = json.loads((FIXTURES / 'native_fireball_public_15_535_86.json').read_text())
CARDS = ('Knight', 'IceGolem', 'Archers', 'Musketeer', 'Cannon', 'Fireball', 'Log', 'Skeletons',
         'HogRider', 'IceSpirit', 'Zap', 'Tesla', 'Mirror', 'Giant', 'Prince', 'DarkPrince')
# Owner-0 and owner-1 in-flight LogProjectile IDs in the tick-202 frame.
LOG_IDS = {0: 4000000, 1: 4000001}


def components():
    catalog = NativeProjectileCatalog.from_csv(
        FIXTURES / 'native_projectiles_15_535_86.csv', expected_sha256=FIREBALL['catalog_sha256'],
    )
    base = StructuredObservationBuilder(card_vocab=list(CARDS), canonical_lane_globals=True)
    tokens = ['<pad>', '<unknown>', *sorted(set(base.token_names[2:]) | set(catalog.names))]
    builder = StructuredObservationBuilder(
        card_vocab=list(CARDS), token_names=tokens, canonical_lane_globals=True, public_entity_levels=True,
    )
    scope = NativePublicScope('15.535.86', hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest())
    adapter = NativePublicObservationAdapter(builder, scope, card_names=CARDS, projectile_catalog=catalog)
    return builder, adapter, reference_token_maps(builder, CARDS, catalog)


def log_frame(owner, x=None, y=None):
    frame = copy.deepcopy(LOG_PHASES['frames'][0])
    assert frame['tick'] == 202
    for snapshot in (frame['ordinary'], frame['rich']):
        obj = next(o for o in snapshot['objects'] if o['nativeObjectId'] == LOG_IDS[owner])
        if x is not None:
            obj['x'] = x
        if y is not None:
            obj['y'] = y
    return frame


def log_rows(builder, view):
    actor = view.observation
    token = builder.token_id('LogProjectile', namespace='projectile')
    selected = actor.entity_mask & (actor.entity_ids == token)
    return actor.entity_features[selected]


@pytest.mark.parametrize('owner,x,y,clipped', [
    (1, 12500, 32400, (12500, 32000)),  # job-00685: behind owner 1's back line
    (1, 12500, 34500, (12500, 32000)),  # worst case: Log at y=31500
    (1, 12500, 32000 + NATIVE_OUT_OF_ARENA_MARGIN, (12500, 32000)),
    (0, 5500, -400, (5500, 0)),  # symmetric owner-0 case
    (0, 5500, -2500, (5500, 0)),  # worst case: Log at y=500
    (0, 5500, -NATIVE_OUT_OF_ARENA_MARGIN, (5500, 0)),
    (0, -NATIVE_OUT_OF_ARENA_MARGIN, 9220, (0, 9220)),
    (1, 18000 + NATIVE_OUT_OF_ARENA_MARGIN, 22780, (18000, 22780)),
])
@pytest.mark.parametrize('perspective', [0, 1])
def test_bounded_out_of_arena_log_projects_clipped(owner, x, y, clipped, perspective, tmp_path):
    builder, adapter, (card_tokens, body_tokens, effect_tokens, tower_tokens) = components()
    frame = log_frame(owner, x, y)
    view = adapter.project(frame['ordinary'], perspective, rich_snapshot=frame['rich'])
    view.validate()
    cx, cy = clipped
    if perspective:
        cx, cy = 18000 - cx, 32000 - cy
    rows = log_rows(builder, view)
    assert len(rows) == 2
    match = [row for row in rows if bool(row[2]) == (owner == perspective)]
    assert len(match) == 1
    np.testing.assert_array_equal(match[0][:2], np.float32([cx / 18000, cy / 32000]))
    assert ((view.observation.entity_features[:, :2] >= 0) & (view.observation.entity_features[:, :2] <= 1)).all()
    # Raw coordinates stay available as diagnostics; only the feature is clipped.
    assert native_out_of_arena_positions(frame['ordinary']) == [{
        'nativeObjectId': LOG_IDS[owner], 'owner': owner, 'cardId': 28000011,
        'raw': [x, y], 'clipped': list(clipped),
    }]
    # Public packet round trip: reference checks agree and the packet survives
    # serialization unchanged.
    assert check_reference_packet(frame['ordinary'], view, perspective, card_tokens=card_tokens) == []
    assert check_reference_entities(
        frame['ordinary'], frame['rich'], view, perspective, body_tokens=body_tokens,
        effect_tokens=effect_tokens, tower_tokens=tower_tokens, levels={}, level_confidence={},
    ) == []
    sequence = PublicPolicySequence.from_observations(builder, [view])
    sequence.save(tmp_path / 'clipped.npz')
    restored = PublicPolicySequence.load(tmp_path / 'clipped.npz', token_names=builder.token_names)
    for name, array in sequence.arrays.items():
        np.testing.assert_array_equal(restored.arrays[name], array)


@pytest.mark.parametrize('owner,x,y', [
    (1, 12500, 40000),
    (1, 12500, 32001 + NATIVE_OUT_OF_ARENA_MARGIN),
    (0, 5500, -8000),
    (0, 5500, -1 - NATIVE_OUT_OF_ARENA_MARGIN),
    (0, -1 - NATIVE_OUT_OF_ARENA_MARGIN, 9220),
    (1, 18001 + NATIVE_OUT_OF_ARENA_MARGIN, 22780),
])
@pytest.mark.parametrize('perspective', [0, 1])
def test_positions_beyond_margin_remain_corrupt(owner, x, y, perspective):
    _, adapter, _ = components()
    frame = log_frame(owner, x, y)
    with pytest.raises(NativePublicProjectionError, match='out-of-arena body'):
        adapter.project(frame['ordinary'], perspective, rich_snapshot=frame['rich'])


def test_non_integer_positions_remain_invalid():
    _, adapter, _ = components()
    for value in (32400.0, True, None):
        frame = log_frame(1)
        for snapshot in (frame['ordinary'], frame['rich']):
            next(o for o in snapshot['objects'] if o['nativeObjectId'] == LOG_IDS[1])['y'] = value
        with pytest.raises(NativePublicProjectionError, match='invalid y'):
            adapter.project(frame['ordinary'], 0, rich_snapshot=frame['rich'])


@pytest.mark.parametrize('raw', [(12500, 32400), (12500, 34500), (5500, -2500), (-400, 9000), (18300, 9000)])
@pytest.mark.parametrize('perspective', [0, 1])
def test_scalar_and_native_packets_encode_out_of_arena_positions_alike(raw, perspective):
    """The scalar builder clips after canonical rotation; native clips before.

    Both reduce to the same float32 feature for any in-margin position.
    """
    builder, adapter, _ = components()
    owner = 1 if raw[1] > 16000 else 0
    frame = log_frame(owner, *raw)
    native = [row for row in log_rows(builder, adapter.project(
        frame['ordinary'], perspective, rich_snapshot=frame['rich'])) if bool(row[2]) == (owner == perspective)]
    battle = BattleState()
    battle.players[owner].hand = ['Knight']
    before = set(battle.entities)
    assert battle.deploy_card(owner, 'Knight', Position(9.5, 20.5 if owner else 10.5))
    (knight_id,) = set(battle.entities) - before
    battle.entities[knight_id].position = Position(raw[0] / 1000, raw[1] / 1000)
    scalar = reference_public_observation(builder.build_actor(battle, perspective))
    token = builder.token_id('Knight', namespace='troop_body')
    rows = scalar.observation.entity_features[scalar.observation.entity_mask & (scalar.observation.entity_ids == token)]
    assert len(native) == 1 and len(rows) == 1
    np.testing.assert_array_equal(rows[0][:2], native[0][:2])
