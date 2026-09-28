"""Native reference frames projected without private actor information."""
import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from clasher.rl.action_space import DiscreteTileActionSpace
from clasher.rl.native_public_observation import (
    NativePublicObservationAdapter,
    NativePublicProjectionError,
    NativePublicScope,
)
from clasher.rl.public_action_mask import PublicActionMaskBuilder, PublicActionMaskInput
from clasher.rl.public_policy_contract import PublicPolicySequence
from clasher.rl.structured_obs import StructuredObservationBuilder

REFERENCE = json.loads((Path(__file__).parent / 'fixtures/native_public_frames_15_535_86.json').read_text())
CARDS = ('Knight', 'IceGolem', 'Archers', 'Musketeer', 'Cannon', 'Fireball', 'Log', 'Skeletons', 'HogRider', 'IceSpirit', 'Zap', 'Tesla', 'Mirror')


def adapter():
    b = StructuredObservationBuilder(card_vocab=list(CARDS), canonical_lane_globals=True)
    scope = NativePublicScope('15.535.86', hashlib.sha256(b.loader.data_file.read_bytes()).hexdigest())
    return b, NativePublicObservationAdapter(b, scope, card_names=CARDS)


@pytest.mark.parametrize('case', REFERENCE['cases'])
@pytest.mark.parametrize('perspective', [0, 1])
def test_native_public_position_hud_and_mask_roundtrip(case, perspective, tmp_path):
    builder, source = adapter()
    frame = case['snapshot']
    public = source.project(frame, perspective)
    actor = public.observation
    assert actor.terminal is False
    assert actor.entity_mask.sum() == 7
    knight = frame['objects'][-1]
    assert knight['cardId'] == 26000000
    row = actor.entity_features[(actor.entity_ids == builder.token_id('Knight')) & actor.entity_mask][0]
    expected = [knight['x'] / 18000, knight['y'] / 32000]
    if perspective:
        expected = [1 - x for x in expected]
    np.testing.assert_allclose(row[:2], expected)
    assert row[2] == (case['owner'] == perspective)
    assert row[9] == 1
    own = next(p for p in frame['players'] if p['owner'] == perspective)
    assert actor.global_features[5] == pytest.approx(own['elixirRaw'] / 100000)
    np.testing.assert_array_equal(actor.global_features[8:14], np.ones(6))
    assert not public.entity_feature_confidence[:, 10:].any()
    assert not public.global_feature_confidence[:5].any()
    masks = PublicActionMaskBuilder(builder)
    mask = masks.build(PublicActionMaskInput.from_confidence_observation(public))
    assert mask[:masks.no_op_action].any()
    space = DiscreteTileActionSpace()
    for action in np.flatnonzero(mask[:masks.no_op_action]):
        selected = space.decode_action(int(action), perspective)
        assert space.encode_action(int(action) // 576, int(selected.position.x), int(selected.position.y), perspective) == action
    sequence = PublicPolicySequence.from_observations(builder, [public])
    sequence.save(tmp_path / 'native.npz')
    restored = PublicPolicySequence.load(tmp_path / 'native.npz', token_names=builder.token_names)
    restored.validate_action_mask(mask[None])


@pytest.mark.parametrize('perspective', [0, 1])
def test_private_state_and_native_identifiers_do_not_change_actor(perspective):
    builder, source = adapter()
    frame = copy.deepcopy(REFERENCE['cases'][0]['snapshot'])
    baseline = PublicPolicySequence.from_observations(builder, [source.project(frame, perspective)])
    enemy = next(p for p in frame['players'] if p['owner'] != perspective)
    enemy.clear()
    enemy['owner'] = 1 - perspective
    enemy['elixirRaw'] = 123
    enemy['hand'] = [{'private': 'unread'}]
    for obj in frame['objects']:
        obj['nativeObjectId'] += 98765
        obj['targetX'], obj['targetY'] = -99999, 99999
        obj['phaseRuntime'] = {'hitTimeline': -1000}
    frame['objects'].reverse()
    after = PublicPolicySequence.from_observations(builder, [source.project(frame, perspective)])
    for key in baseline.arrays:
        np.testing.assert_array_equal(baseline.arrays[key], after.arrays[key])


@pytest.mark.parametrize('problem', ['truncation', 'count', 'effect', 'level', 'hand', 'form', 'duplicate', 'presentation'])
def test_incomplete_or_unsupported_native_frame_fails(problem):
    _, source = adapter()
    frame = copy.deepcopy(REFERENCE['cases'][0]['snapshot'])
    if problem == 'truncation': frame['truncated'] = True
    elif problem == 'count': frame['count'] += 1
    elif problem == 'effect': frame['objects'][-1]['hp'] = None
    elif problem == 'level': frame['objects'][-1]['maxHp'] += 1
    elif problem == 'hand': frame['players'][0]['hand'].pop()
    elif problem == 'form': frame['players'][0]['hand'][0]['commandCardId'] = 999
    elif problem == 'duplicate': frame['objects'][-1]['nativeObjectId'] = frame['objects'][0]['nativeObjectId']
    elif problem == 'presentation': frame['finalized'] = True
    with pytest.raises(NativePublicProjectionError): source.project(frame, 0)


def test_native_reference_deadline_precedes_result_presentation():
    builder, source = adapter()
    frame = copy.deepcopy(REFERENCE['cases'][0]['snapshot'])
    frame['tick'] = 6001
    assert frame['ended'] is False
    view = source.project(frame, 0)
    assert view.observation.terminal is True
    masks = PublicActionMaskBuilder(builder)
    assert np.flatnonzero(masks.build(PublicActionMaskInput.from_confidence_observation(view))).tolist() == [masks.no_op_action]


def test_ruleset_hash_is_bound():
    builder, _ = adapter()
    with pytest.raises(NativePublicProjectionError, match='digest'):
        NativePublicObservationAdapter(builder, NativePublicScope('15.535.86', '0' * 64), card_names=CARDS)


def test_mirror_dispatch_does_not_fabricate_own_history():
    builder, source = adapter()
    frame = copy.deepcopy(REFERENCE['cases'][0]['snapshot'])
    hand = frame['players'][0]['hand'][0]
    hand['cardId'] = 28000006
    hand['commandCardId'] = 26000000
    view = source.project(frame, 0)
    assert view.observation.hand_ids[hand['handIndex']] == builder.token_id('Mirror')
    assert view.observation.own_last_play is None
    masks = PublicActionMaskBuilder(builder)
    mask = masks.build(PublicActionMaskInput.from_confidence_observation(view))
    slot = hand['handIndex']
    assert not mask[slot * 576:(slot + 1) * 576].any()


FIREBALL = json.loads((Path(__file__).parent / 'fixtures/native_fireball_public_15_535_86.json').read_text())


def fireball_adapter():
    from clasher.rl.native_public_observation import NativeProjectileCatalog
    cards = (*CARDS, 'Giant', 'Prince', 'DarkPrince')
    builder = StructuredObservationBuilder(card_vocab=list(cards), canonical_lane_globals=True)
    catalog = NativeProjectileCatalog.from_csv(
        Path(__file__).parent / 'fixtures/native_projectiles_15_535_86.csv',
        expected_sha256=FIREBALL['catalog_sha256'],
    )
    tokens = ['<pad>', '<unknown>', *sorted(set(builder.token_names[2:]) | set(catalog.names))]
    builder = StructuredObservationBuilder(card_vocab=list(cards), token_names=tokens, canonical_lane_globals=True)
    scope = NativePublicScope('15.535.86', hashlib.sha256(builder.loader.data_file.read_bytes()).hexdigest())
    return builder, NativePublicObservationAdapter(builder, scope, card_names=cards, projectile_catalog=catalog)


@pytest.mark.parametrize('perspective', [0, 1])
def test_native_fireball_public_rows_have_identity_but_no_fabricated_health(perspective):
    builder, source = fireball_adapter()
    view = source.project(FIREBALL['ordinary'], perspective, rich_snapshot=FIREBALL['rich'])
    actor = view.observation
    selected = actor.entity_mask & (actor.entity_features[:, 6] == 1)
    assert selected.sum() == 2
    assert (actor.entity_ids[selected] == builder.token_id('FireballSpell', namespace='projectile')).all()
    assert not actor.entity_features[selected, 9:].any()
    assert not view.entity_feature_confidence[selected, 9:].any()
    positions = sorted(tuple(row[:2]) for row in actor.entity_features[selected])
    expected = []
    for obj in FIREBALL['ordinary']['objects']:
        if obj['hp'] is None:
            xy = [obj['x'] / 18000, obj['y'] / 32000]
            expected.append(tuple(1 - v for v in xy) if perspective else tuple(xy))
    np.testing.assert_allclose(positions, sorted(expected))


@pytest.mark.parametrize('problem', ['tick', 'epoch', 'count', 'position', 'identity', 'phase'])
def test_rich_projection_rejects_stale_or_ambiguous_join(problem):
    _, source = fireball_adapter()
    rich = copy.deepcopy(FIREBALL['rich'])
    if problem == 'tick': rich['tick'] += 1
    elif problem == 'epoch': rich['stateEpoch'] += 1
    elif problem == 'count': rich['objects'].pop()
    elif problem == 'position': rich['objects'][0]['x'] += 1
    elif problem == 'identity': rich['objects'][0]['projectile']['projectileDataGlobalId'] += 1
    elif problem == 'phase': rich['objects'][0]['projectile']['nativePhase'] = 'unknown'
    with pytest.raises(NativePublicProjectionError):
        source.project(FIREBALL['ordinary'], 0, rich_snapshot=rich)


def test_rich_target_and_runtime_fields_never_enter_actor():
    builder, source = fireball_adapter()
    baseline = PublicPolicySequence.from_observations(builder, [source.project(FIREBALL['ordinary'], 0, rich_snapshot=FIREBALL['rich'])])
    rich = copy.deepcopy(FIREBALL['rich'])
    for obj in rich['objects']:
        obj['phaseRuntime'] = {'secret': 'ignored'}
        obj['targetEntityKey'] = [999, 999, 999]
        if obj['projectile'] is not None:
            obj['projectile']['sourceEntityKey'] = [999, 999, 999]
            obj['projectile']['destinationX'] = -99999
            obj['projectile']['homingTargetEntityKey'] = [999, 999, 999]
    after = PublicPolicySequence.from_observations(builder, [source.project(FIREBALL['ordinary'], 0, rich_snapshot=rich)])
    for key in baseline.arrays:
        np.testing.assert_array_equal(baseline.arrays[key], after.arrays[key])


ATTACK_PROJECTILES = json.loads((Path(__file__).parent / 'fixtures/native_public_attack_projectiles_15_535_86.json').read_text())


@pytest.mark.parametrize('case', ATTACK_PROJECTILES['cases'])
@pytest.mark.parametrize('perspective', [0, 1])
def test_catalog_bound_attack_projectile_positions(case, perspective):
    builder, source = fireball_adapter()
    view = source.project(case['ordinary'], perspective, rich_snapshot=case['rich'])
    names = {10000002: 'ArcherArrow', 10000003: 'TowerPrincessProjectile', 10000006: 'TowerCannonball'}
    for identity in case['projectile_ids']:
        token = builder.token_id(names[identity], namespace='projectile')
        selected = view.observation.entity_mask & (view.observation.entity_ids == token)
        actual = sorted(tuple(row[:2]) for row in view.observation.entity_features[selected])
        expected = []
        for obj in case['rich']['objects']:
            if obj['dataGlobalId'] != identity:
                continue
            x, y = obj['x'] / 18000, obj['y'] / 32000
            expected.append((1 - x, 1 - y) if perspective else (x, y))
        assert len(actual) == len(expected) > 0
        np.testing.assert_allclose(actual, sorted(expected))
        assert not view.entity_feature_confidence[selected, 9:].any()


TESLA = json.loads((Path(__file__).parent / 'fixtures/native_public_tesla_15_535_86.json').read_text())


@pytest.mark.parametrize('perspective', [0, 1])
def test_tesla_trapdoor_and_health_bar_are_public_but_combat_hide_state_is_not(perspective):
    builder, source = fireball_adapter()
    frame = copy.deepcopy(TESLA['ordinary'])
    public = source.project(frame, perspective)
    actor = public.observation
    token = builder.token_id('Tesla', namespace='building_body')
    selected = actor.entity_mask & (actor.entity_ids == token)
    assert selected.sum() == 1
    entity = next(e for e in frame['objects'] if e['cardId'] == 27000006)
    x, y = entity['x'] / 18000, entity['y'] / 32000
    np.testing.assert_allclose(actor.entity_features[selected][0, :2], [1-x, 1-y] if perspective else [x, y])
    assert actor.entity_features[selected][0, 5] == 1
    assert actor.entity_features[selected][0, 9] == pytest.approx(entity['hp'] / entity['maxHp'])
    assert public.entity_feature_confidence[selected][0, 9] == 1
    assert not public.entity_feature_confidence[selected][0, 10:].any()
    entity['hidden'] = True
    entity['visibilityState'] = 'invisible'
    changed = source.project(frame, perspective)
    np.testing.assert_array_equal(changed.observation.entity_features, actor.entity_features)
    masks = PublicActionMaskBuilder(builder)
    masks.build(PublicActionMaskInput.from_confidence_observation(public))


RETRACTED_TESLAS = json.loads((Path(__file__).parent / 'fixtures/native_public_retracted_teslas_15_535_86.json').read_text())


@pytest.mark.parametrize('perspective', [0, 1])
def test_rendered_idle_teslas_keep_both_public_health_fractions(perspective):
    builder, source = fireball_adapter()
    view = source.project(RETRACTED_TESLAS['ordinary'], perspective)
    token = builder.token_id('Tesla', namespace='building_body')
    selected = view.observation.entity_mask & (view.observation.entity_ids == token)
    rows = view.observation.entity_features[selected]
    assert len(rows) == 2
    np.testing.assert_allclose(rows[:, 9], [1112 / 1182, 1112 / 1182])
    assert sorted(rows[:, 2].tolist()) == [0, 1]
    assert (view.entity_feature_confidence[selected, 9] == 1).all()
    assert not view.entity_feature_confidence[selected, 10:].any()


LOG_PHASES = json.loads((Path(__file__).parent / 'fixtures/native_public_log_phases_15_535_86.json').read_text())


@pytest.mark.parametrize('perspective', [0, 1])
@pytest.mark.parametrize('frame', LOG_PHASES['frames'])
def test_rendered_log_flight_rolling_and_removal(frame, perspective):
    builder, source = fireball_adapter()
    view = source.project(frame['ordinary'], perspective, rich_snapshot=frame['rich'])
    selected = view.observation.entity_mask & (view.observation.entity_features[:, 6] == 1)
    if frame['tick'] == 261:
        assert not selected.any()
        return
    name = 'LogProjectile' if frame['tick'] < 209 else 'LogProjectileRolling'
    assert selected.sum() == 2
    assert (view.observation.entity_ids[selected] == builder.token_id(name, namespace='projectile')).all()
    assert not view.entity_feature_confidence[selected, 9:].any()
    actual = sorted(tuple(row[:4]) for row in view.observation.entity_features[selected])
    expected = []
    for obj in frame['ordinary']['objects']:
        if obj['hp'] is not None:
            continue
        x, y = obj['x'] / 18000, obj['y'] / 32000
        if perspective:
            x, y = 1-x, 1-y
        expected.append((x, y, obj['owner'] == perspective, obj['owner'] != perspective))
    np.testing.assert_allclose(actual, sorted(expected))


ICE_GOLEM_DEATH = json.loads((Path(__file__).parent / 'fixtures/native_public_ice_golem_death_15_535_86.json').read_text())


@pytest.mark.parametrize('perspective', [0, 1])
@pytest.mark.parametrize('frame', ICE_GOLEM_DEATH['frames'])
def test_rendered_ice_golem_death_area_has_no_hp_or_private_timer(frame, perspective):
    builder, source = fireball_adapter()
    view = source.project(frame['ordinary'], perspective, rich_snapshot=frame['rich'])
    selected = view.observation.entity_mask & (view.observation.entity_features[:, 7] == 1)
    if frame['ordinary']['tick'] == 510:
        assert not selected.any()
        return
    assert selected.sum() == 2
    assert (view.observation.entity_ids[selected] == builder.token_id('FreezeIceGolemite', namespace='area_effect')).all()
    assert not view.observation.entity_features[selected, 9:].any()
    assert not view.entity_feature_confidence[selected, 9:].any()
    expected = []
    for obj in frame['rich']['objects']:
        if obj['dataGlobalId'] == 22000007:
            x, y = obj['x'] / 18000, obj['y'] / 32000
            expected.append((1-x, 1-y) if perspective else (x, y))
    actual = [tuple(row[:2]) for row in view.observation.entity_features[selected]]
    np.testing.assert_allclose(sorted(actual), sorted(expected))


def test_area_effect_identity_is_not_guessed_from_csv_ordinal():
    _, source = fireball_adapter()
    frame = copy.deepcopy(ICE_GOLEM_DEATH['frames'][0])
    for obj in frame['rich']['objects']:
        if obj['dataGlobalId'] == 22000007:
            obj['dataGlobalId'] = 22000006
    with pytest.raises(NativePublicProjectionError):
        source.project(frame['ordinary'], 0, rich_snapshot=frame['rich'])


REMAINING_PROJECTILES = json.loads((Path(__file__).parent / 'fixtures/native_public_remaining_projectiles_15_535_86.json').read_text())


@pytest.mark.parametrize('perspective', [0, 1])
@pytest.mark.parametrize('frame', REMAINING_PROJECTILES['frames'])
def test_rendered_musketeer_and_spirit_projectiles(frame, perspective):
    builder, source = fireball_adapter()
    view = source.project(frame['ordinary'], perspective, rich_snapshot=frame['rich'])
    selected = view.observation.entity_mask & (view.observation.entity_features[:, 6] == 1)
    assert selected.sum() == 2
    assert (view.observation.entity_ids[selected] == builder.token_id(frame['projectile_name'], namespace='projectile')).all()
    assert not view.observation.entity_features[selected, 9:].any()
    assert not view.entity_feature_confidence[selected, 9:].any()
