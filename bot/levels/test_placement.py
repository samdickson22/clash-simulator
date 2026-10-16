"""Public-mask regressions and opt-in actual runtime/controller integration.

After the reviewed microprobe, set CLASHER_PLACEMENT_INTEGRATION=1 for the full
selection tests. Runtime is built once per pytest invocation. No tests run on05.
"""
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from . import placement, placement_probe
from .fixture_support import FrozenLevelConfigs, canonical, candidate_allowed, differences, normalized_spells, sha


@pytest.fixture(scope='module', autouse=True)
def bootstrap():
    """Initialize actual Runtime BEFORE any builder/spell objects in integration mode, once."""
    from bot.players.runtime import Runtime
    if os.environ.get('CLASHER_PLACEMENT_INTEGRATION') == '1':
        placement.proof()
        rt = Runtime()  # Includes the runtime's own override setup, before Resources or fixture builders.
        from .scope import install
        install(rt)
        frozen = FrozenLevelConfigs(rt, (4, 5, 6, 7, 9, 11))
        spells = normalized_spells(rt, frozen)
        rt._level_configs = frozen
        placement.install_runtime(rt)
        from .configs import LevelConfigs
        def refuse(*args, **kwargs):
            raise AssertionError('integration forbids all export/support-receipt builders; use the frozen cache')
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(LevelConfigs, 'build', refuse)
            patch.setattr(LevelConfigs, 'supported', refuse)
            print(json.dumps(dict(frozen_fixture_cache=frozen.manifest, normalized_spells=spells,
                                  supported=len(frozen.supported()), check11=frozen.check11()), sort_keys=True), flush=True)
            try:
                yield SimpleNamespace(rt=rt, cache=frozen)
            finally:
                frozen.verify()
        return
    # Optional lightweight mode creates no Runtime. Its builders are not physics/integration evidence.
    rt = Runtime.__new__(Runtime)
    rt.root = Path(os.environ['CLASHER_BOT_RUNTIME']).resolve()
    rt.native_dir = rt.root / 'native'
    rt._bootstrap_paths()
    yield SimpleNamespace(rt=None, cache=None)


@pytest.fixture(autouse=True)
def unchanged_fixture_cache(bootstrap):
    if bootstrap.cache is not None:
        bootstrap.cache.verify()
    try:
        yield
    finally:
        if bootstrap.cache is not None:
            bootstrap.cache.verify()


@pytest.fixture(scope='module')
def builder(bootstrap):
    if bootstrap.rt is not None:
        return bootstrap.rt.R.builder
    from clasher.rl.contract_v5 import ContractV5ObservationBuilder
    return ContractV5ObservationBuilder()


def request(builder, names, seat=0, down=(True, True), history=None):
    from clasher.rl.public_action_mask import PublicActionMaskInput
    glob = np.ones(32, dtype=np.float32)
    glob[4] = 0
    glob[11:13] = [not d for d in down]
    return PublicActionMaskInput(entity_ids=np.zeros(0, dtype=np.int64),
        entity_features=np.zeros((0, 32), dtype=np.float32), entity_mask=np.zeros(0, dtype=bool),
        hand_ids=np.asarray([builder.token_id(n, namespace='card_action') for n in names]),
        global_features=glob, entity_id_confidence=np.ones(0), hand_id_confidence=np.ones(4),
        global_feature_confidence=np.ones(32), own_last_play=history, terminal=False, board_rotated=bool(seat))


def expected_water():
    # Independent closed-bridge rectangle expectation from the pinned arena bounds.
    return np.array([y in (15, 16) and x not in (3, 14) for y in range(32) for x in range(18)])


def test_timed_wait_candidates_require_public_wait_and_reject_unknown_ids():
    from bot.search.players import TIMED_WAITS
    assert TIMED_WAITS == {2400: 10, 2401: 20, 2402: 40}  # Durations are simulation ticks.
    mask = np.zeros(2306, dtype=bool)
    mask[43] = mask[2304] = True
    assert all(candidate_allowed(a, mask) for a in (43, 2304, *TIMED_WAITS))
    assert candidate_allowed(np.int64(2400), mask)
    assert not candidate_allowed(42, mask)
    assert all(not candidate_allowed(a, mask) for a in (-1, 2306, 2399, 2403, 999999, 2400.0, True))
    mask[2304] = False
    assert all(not candidate_allowed(a, mask) for a in TIMED_WAITS)
    with pytest.raises(ValueError, match='2306-entry'):
        candidate_allowed(2400, np.ones(2403, dtype=bool))


def cache_case(tmp_path):
    """Isolated synthetic metadata, never a write to the pilot cache or a physics assertion."""
    from .configs import LevelConfigs
    cfg = dict(cards={
        'Fireball': dict(units=[[], []], spell=dict(crown_tower_damage=100.0)),
        'Musketeer': dict(units=[[dict(stats=dict(damage=113.0), anchor=(1.0, 2.0))], []])})
    rt = SimpleNamespace(R=SimpleNamespace(config=cfg), pins={})
    locator = LevelConfigs(rt, cache=tmp_path)
    locator.dir.mkdir(parents=True)
    for level in (4, 11):
        cards = copy.deepcopy(cfg['cards'])
        if level == 4:
            cards['Fireball']['spell']['crown_tower_damage'] = 50.0
        data = dict(level=level, cards={card: dict(card=value, tables={}) for card, value in cards.items()}, errors={})
        locator.path(level).write_text(json.dumps(data))
    reference = sha(json.dumps(cfg, sort_keys=True).encode())
    support = dict(cards=sorted(cfg['cards']), unsupported={}, comparison='native-json-v1', reference_sha256=reference)
    (locator.dir/'supported.json').write_text(json.dumps(support, indent=1))
    def pair(path):
        raw = path.read_bytes()
        return sha(raw), sha(canonical(json.loads(raw)))
    expected = dict(reference_sha256=reference, cards=2, supported=pair(locator.dir/'supported.json'),
                    levels={level: pair(locator.path(level)) for level in (4, 11)})
    return SimpleNamespace(rt=rt, locator=locator, expected=expected, cache=tmp_path)


def cache_bytes(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir()}


def test_existing_cache_is_read_only_and_future_reads_are_closed(tmp_path, monkeypatch):
    from .configs import LevelConfigs
    case = cache_case(tmp_path)
    before = cache_bytes(case.locator.dir)
    def forbidden(*args, **kwargs):
        raise AssertionError('fixture used a cache reader/writer outside its frozen contract')
    with monkeypatch.context() as patch:
        for method in ('build', 'supported', 'load'):
            patch.setattr(LevelConfigs, method, forbidden)
        for method in ('write_text', 'write_bytes', 'replace', 'mkdir'):
            patch.setattr(Path, method, forbidden)
        frozen = FrozenLevelConfigs(case.rt, (4, 11), cache=case.cache, expected=case.expected)
        assert frozen.supported() == {'Fireball', 'Musketeer'}
        assert frozen.check11() == (['Fireball', 'Musketeer'], {})
        assert frozen.entry('Fireball', 4)['card']['spell']['crown_tower_damage'] == 50.0
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'read_bytes', forbidden)
        assert frozen.load(4)['level'] == 4 and 'Fireball' in frozen.supported()
        with pytest.raises(ValueError, match='no future disk read/export'):
            frozen.load(8)
        with pytest.raises(ValueError, match='cannot build exports or write receipts'):
            frozen.build(4)
    frozen.verify()
    assert cache_bytes(case.locator.dir) == before


@pytest.mark.parametrize('fault', ['missing_support', 'bad_support', 'runtime_reference', 'L11_damage',
                                  'raw_whitespace', 'canonical_pin', 'unregistered_level'])
def test_cache_mismatch_fails_before_any_write_with_exact_diagnostics(tmp_path, monkeypatch, fault):
    case = cache_case(tmp_path)
    support = case.locator.dir/'supported.json'
    if fault == 'missing_support':
        support.unlink()
    elif fault == 'bad_support':
        data = json.loads(support.read_bytes())
        data['cards'].remove('Fireball')
        data['unsupported'] = {'Fireball': 'level-11 export differs from R.config'}
        support.write_text(json.dumps(data))
    elif fault == 'runtime_reference':
        case.rt.R.config['cards']['Fireball']['spell']['crown_tower_damage'] = 101.0
    elif fault == 'L11_damage':
        data = json.loads(case.locator.path(11).read_bytes())
        data['cards']['Fireball']['card']['spell']['crown_tower_damage'] = 99.0
        case.locator.path(11).write_text(json.dumps(data))
    elif fault == 'raw_whitespace':
        case.locator.path(4).write_text(json.dumps(json.loads(case.locator.path(4).read_bytes()), indent=2))
    elif fault == 'canonical_pin':
        case.expected['supported'] = (case.expected['supported'][0], '0'*64)
    before = cache_bytes(case.locator.dir)
    def forbidden(*args, **kwargs):
        raise AssertionError('mismatching fixture must never repair/regenerate a cache or receipt')
    with monkeypatch.context() as patch:
        for method in ('write_text', 'write_bytes', 'replace', 'mkdir'):
            patch.setattr(Path, method, forbidden)
        with pytest.raises(ValueError) as failure:
            FrozenLevelConfigs(case.rt, (3, 4, 11) if fault == 'unregistered_level' else (4, 11),
                               cache=case.cache, expected=case.expected)
    assert cache_bytes(case.locator.dir) == before
    if fault in ('runtime_reference', 'L11_damage'):
        details = json.loads(str(failure.value).split('read-only fixture cache validation failed: ', 1)[1])
        field = next(r for r in details['fields'] if r['path'] == 'cards.Fireball.spell.crown_tower_damage')
        assert (field['old'], field['new']) == ((100.0, 101.0) if fault == 'runtime_reference' else (99.0, 100.0))
        assert field['units'] == 'hitpoints per crown-tower hit; no conversion'


@pytest.mark.parametrize('fault', ['disk_whitespace', 'parsed_damage', 'runtime_damage', 'unexpected_receipt'])
def test_cache_post_use_immutability_fence(tmp_path, fault):
    case = cache_case(tmp_path)
    frozen = FrozenLevelConfigs(case.rt, (4, 11), cache=case.cache, expected=case.expected)
    if fault == 'disk_whitespace':
        path = case.locator.path(4)
        path.write_text(json.dumps(json.loads(path.read_bytes()), indent=2))
    elif fault == 'parsed_damage':
        frozen.load(4)['cards']['Fireball']['card']['spell']['crown_tower_damage'] += 1
    elif fault == 'runtime_damage':
        case.rt.R.config['cards']['Fireball']['spell']['crown_tower_damage'] += 1
    else:
        (case.locator.dir/'.supported.unexpected.tmp').write_text('preserve me')
    with pytest.raises(ValueError, match='changed'):
        frozen.verify()


def test_cache_field_diagnostics_normalize_only_json_tuple_representation():
    diff = differences(dict(anchor=(1.0, 2.0), damage=1), dict(anchor=[1.0, 2.0], damage=1.0))
    assert len(diff) == 1 and diff[0]['path'] == 'config.damage'
    assert (diff[0]['old_type'], diff[0]['new_type']) == ('int', 'float')


def test_static_geometry_closed_edges_both_bridges_and_rotations():
    water, _ = placement.static_rules()
    assert np.array_equal(water, expected_water()) and np.count_nonzero(water) == 32
    assert np.array_equal(water.reshape(32, 18), water.reshape(32, 18)[::-1, ::-1])
    assert not water.flags.writeable
    for xy in ((2, 15), (4, 15), (13, 16), (15, 16), (9, 16)):
        assert water[xy[1]*18+xy[0]]
    for xy in ((3, 15), (14, 15), (3, 16), (14, 16), (4, 14), (13, 14)):
        assert not water[xy[1]*18+xy[0]]


@pytest.mark.parametrize('card, kind', [('Knight', 'troop'), ('Minions', 'troop'), ('Cannon', 'ordinary'),
    ('Tesla', 'ordinary'), ('Miner', 'tunnel'), ('GoblinDrill', 'tunnel'), ('Log', 'rolling'),
    ('GoblinBarrel', 'water_spell'), ('Fireball', 'unrestricted'), ('ArcherQueen', 'troop')])
def test_static_public_card_classes(builder, card, kind):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    assert placement.PlacementMask(ContractV5ActionMaskBuilder(builder))._kind(card, None) == kind


def test_repaired_static_classes_match_all_preserved_native_rows():
    # Historical evidence only: this receipt failed BEFORE all taps, not a physics PASS.
    raw = Path('/mpac/sdicks02/jobs/clasher/bot-levels/dev/placement-micro-r17.json').read_bytes()
    assert placement.hashlib.sha256(raw).hexdigest() == 'd0609e3c1961d333c2bd356c2a30399e0106f9a08c04feb9a413bbeabe1385c4'
    old = json.loads(raw)
    assert old['passed'] is False and old['rows'] == old['river_matrix'] == []
    assert [(r['card'], r['kind'], r['placement']) for r in old['classifications'] if not r['passed']] == [
        ('Tornado', 'rolling', 2), ('MergeMaiden', 'unrestricted', 0)]
    _, cards = placement.static_rules()
    assert len(old['classifications']) == 145 and {r['card'] for r in old['classifications']} == set(cards)
    for row in old['classifications']:
        kind = placement.card_kind(cards[row['card']], cards)
        assert row['placement'] in placement_probe.KIND_CODES.get(kind, ()), row
    assert placement.card_kind(cards['Tornado'], cards) == 'unrestricted'
    assert placement.card_kind(cards['MergeMaiden'], cards) == 'troop'


def test_spell_territory_precedence_and_generic_variant_resolution():
    spell = dict(kind='spell', name='GenericSpell', spell=dict(spell_as_deploy=True, can_deploy_on_enemy_side=True))
    assert placement.card_kind(spell) == 'unrestricted'
    spell['spell']['can_deploy_on_enemy_side'] = False
    assert placement.card_kind(spell) == 'rolling'
    parent = dict(name='Variant', kind='spell', spell=dict(variant=dict(options=[{'card': 'FormA'}, {'card': 'FormB'}])))
    forms = dict(Variant=parent, FormA=dict(name='FormA', kind='troop'), FormB=dict(name='FormB', kind='troop'))
    assert placement.card_kind(parent, forms) == 'troop'
    assert placement.card_kind(parent) == 'unknown'
    assert placement.card_kind(parent, dict(forms, FormB={'name': 'FormB', 'kind': 'building'})) == 'unknown'
    assert placement.card_kind(parent, {'Variant': parent}) == 'unknown'
    cycle = dict(name='Loop', kind='spell', spell=dict(variant=dict(options=[{'card': 'Loop'}])))
    assert placement.card_kind(cycle, {'Loop': cycle}) == 'unknown'


@pytest.mark.parametrize('seat', [0, 1])
@pytest.mark.parametrize('down', placement_probe.PATTERNS)
@pytest.mark.parametrize('card', ['Cannon', 'Tesla'])
def test_actual_public_mask_intersection(builder, seat, down, card):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    source = request(builder, [card, 'Knight', 'Fireball', 'Archers'], seat, down)
    base = ContractV5ActionMaskBuilder(builder)
    before = base.build(source)
    wrapped = placement.PlacementMask(base)
    after = wrapped.build(source)
    assert np.array_equal(after[:15*18], before[:15*18])
    assert not after[15*18:576].any()
    expected = before.copy()
    expected[15*18:576] = False
    for slot in (1, 3):
        expected[slot*576:(slot+1)*576][expected_water()] = False
    assert np.array_equal(after, expected)
    assert not (after & ~before).any() and after[2304] == before[2304]
    assert np.array_equal(before, base.build(source))  # no mutation of existing mask/cache
    assert np.array_equal(after, wrapped.build(source))
    for x, y in placement_probe.FAILED:
        assert not after[y*18+x]
    if all(down):
        assert before[15*18:576].any() and wrapped.removed > 0


def test_special_building_and_mirror_public_history(builder):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    from clasher.rl.own_card_history import AcceptedOwnPlay
    base = ContractV5ActionMaskBuilder(builder)
    wrapped = placement.PlacementMask(base)
    source = request(builder, ['GoblinDrill', 'Mirror', 'Knight', 'Fireball'])
    assert wrapped._kind('GoblinDrill', None) == 'tunnel'
    for name in ('Cannon', 'Tesla', 'GoblinDrill', 'Miner', 'Knight', 'Minions', 'GoblinBarrel', 'Log', 'Fireball'):
        current = replace(source, own_last_play=AcceptedOwnPlay(name, int(builder.loader.get_card(name).mana_cost)))
        before, after = base.build(current), wrapped.build(current)
        drill = before[:576].copy()
        drill[expected_water()] = False
        assert np.array_equal(drill, after[:576])  # Drill retains enemy-side land, including pockets.
        if name in ('Cannon', 'Tesla'):
            assert np.array_equal(before[576:576+15*18], after[576:576+15*18])
            assert not after[576+15*18:1152].any()
        elif name == 'Fireball':
            assert np.array_equal(before[576:1152], after[576:1152])
        else:
            copied = before[576:1152].copy()
            copied[expected_water()] = False
            assert np.array_equal(copied, after[576:1152])
        assert not (after & ~before).any()


def test_unknown_identity_fail_closed_and_nonbuilding_confidence_unchanged(builder, monkeypatch):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    base = ContractV5ActionMaskBuilder(builder)
    original = np.ones(2306, dtype=bool)
    original[1::7] = False  # existing occupancy/affordability restrictions must remain
    monkeypatch.setattr(base, 'build', lambda source: original)
    source = request(builder, ['Knight', 'Fireball', 'Mirror', 'Cannon'])
    source = replace(source, hand_id_confidence=np.zeros(4))
    wrapped = placement.PlacementMask(base)
    got = wrapped.build(source)
    knight = original[:576].copy()
    knight[expected_water()] = False
    assert np.array_equal(got[:576], knight)  # Low confidence adds no further restriction.
    assert np.array_equal(got[576:1152], original[576:1152])  # Fireball remains unrestricted.
    assert not got[1152:1728].any()  # Mirror's unresolved own history
    unknown = replace(source, hand_ids=np.array([1, 0, 999999, source.hand_ids[3]]))
    assert not wrapped.build(unknown)[:1728].any()
    assert np.array_equal(got[2304:], original[2304:])
    assert not (got & ~original).any()
    with pytest.raises(TypeError, match='public mask input'):
        wrapped.build(object())
    with pytest.raises(TypeError, match='unsupported placement mask'):
        placement.PlacementMask(object())


def test_instance_installation_does_not_modify_other_runtime_or_classes(builder, monkeypatch):
    from types import SimpleNamespace
    from clasher.rl.public_scripted_opponent import PublicScriptedOpponent
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    def runtime():
        return SimpleNamespace(R=SimpleNamespace(builder=builder, bots={s: PublicScriptedOpponent(
            builder, style=s, card_scope='c56') for s in ('balanced', 'pressure', 'defense')}))
    a, b = runtime(), runtime()
    monkeypatch.setattr(placement, 'proof', lambda: {'version': placement.VERSION})
    state = placement.install_runtime(a)
    assert placement.install_runtime(a) is state
    assert all(isinstance(bot.mask_builder, placement.PlacementMask) for bot in a.R.bots.values())
    assert all(type(bot.mask_builder) is ContractV5ActionMaskBuilder for bot in b.R.bots.values())
    wrapper = a.R.bots['balanced'].mask_builder
    a.R.bots['balanced'].mask_builder = wrapper.base
    with pytest.raises(ValueError, match='replaced'):
        placement.install_runtime(a)


def test_identified_champion_miner_and_special_land_masks_preserved(builder, monkeypatch):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    base = ContractV5ActionMaskBuilder(builder)
    original = np.ones(2306, dtype=bool)
    original[::11] = False
    monkeypatch.setattr(base, 'build', lambda _: original)
    source = request(builder, ['ArcherQueen', 'Miner', 'Fireball', 'GoblinDrill'])
    source = replace(source, hand_id_confidence=np.zeros(4))
    expected = original.copy()
    for slot in (0, 1, 3):
        expected[slot*576:(slot+1)*576][expected_water()] = False
    assert np.array_equal(placement.PlacementMask(base).build(source), expected)


def test_unclassifiable_static_card_and_recursive_mirror_fail_closed(builder, monkeypatch):
    from clasher.rl.contract_v5 import ContractV5ActionMaskBuilder
    from clasher.rl.own_card_history import AcceptedOwnPlay
    base = ContractV5ActionMaskBuilder(builder)
    monkeypatch.setattr(base, 'build', lambda _: np.ones(2306, dtype=bool))
    wrapper = placement.PlacementMask(base)
    wrapper.cards = dict(wrapper.cards, Knight={'kind': 'unrecognized'})
    source = request(builder, ['Knight', 'Mirror', 'Fireball', 'Cannon'], history=AcceptedOwnPlay('Mirror', 1))
    after = wrapper.build(source)
    assert not after[:1152].any() and after[2304]
    assert after[1152:1728].all()


def _proof_fixture():
    identity = dict(placement_probe.PINS, version='0.1.34', client='16.402')
    rows = []
    for seat in (0, 1):
        for down in placement_probe.PATTERNS:
            for xy in placement_probe.FAILED + placement_probe.CONTROLS:
                ok = xy in placement_probe.CONTROLS
                rows.append(dict(seat=seat, enemy_down=list(down), own_tile=list(xy), passed=True,
                    accepted=ok, reason='OK' if ok else ('WATER' if xy == (13, 16) else 'OUT_OF_TERRITORY'),
                    relocated=ok, resolved_own_tiles=[xy[0]+.5, 13.5 if xy[1] == 14 else xy[1]+.5]))
    matrix = []
    for s in (0, 1):
        for p in placement_probe.PATTERNS:
            for c in placement_probe.MATRIX_CARDS:
                for xy in placement_probe.MATRIX_TILES:
                    reason = placement_probe.expected_verdict(c, xy, p)
                    matrix.append(dict(seat=s, enemy_down=list(p), card=c, own_tile=list(xy), passed=True,
                                       accepted=reason == 'OK', reason=reason))
    descriptive = [dict(row) for row in matrix if row['enemy_down'] == [True, True]
                   and row['card'] in placement_probe.DESCRIPTIVE_CARDS
                   and tuple(row['own_tile']) in placement_probe.DESCRIPTIVE_TILES]
    _, cards = placement.static_rules()
    # Complete structural fixture only; native classification evidence is checked separately above.
    kinds = {name: placement.card_kind(row, cards) for name, row in cards.items()}
    classifications = [dict(card=c, kind=k, placement=placement_probe.KIND_CODES[k][0], passed=True) for c, k in kinds.items()]
    return dict(protocol=placement.VERSION, identity=identity, passed=True, rows=rows, river_matrix=matrix,
                nonbuilding_descriptive=descriptive, classifications=classifications)


def test_proof_is_complete_pinned_and_exact_bytes(tmp_path, monkeypatch):
    value = _proof_fixture()
    placement_probe.validate_receipt(value, value['identity'])
    path = tmp_path/'proof.json'
    path.write_text(json.dumps(value))
    monkeypatch.setenv(placement.PROOF_ENV, str(path))
    monkeypatch.setattr(placement_probe, 'installed_identity', lambda: value['identity'])
    first = placement.proof()
    path.write_text(json.dumps(value, indent=2))
    second = placement.proof()
    assert first['sha256'] != second['sha256']  # even semantically identical bytes are bound
    for change in ('missing', 'failed', 'stale', 'missing_matrix', 'air_edge', 'class', 'missing_class',
                   'lateral_fit', 'outward_fit', 'old_version', 'old_v2'):
        changed = copy.deepcopy(value)
        if change == 'missing':
            changed['rows'].pop()
        elif change == 'failed':
            changed['rows'][0]['passed'] = False
        elif change == 'stale':
            changed['identity']['binary_sha256'] = '0'*64
        elif change == 'missing_matrix':
            changed['river_matrix'].pop()
        elif change == 'air_edge':
            row = next(r for r in changed['river_matrix'] if r['card'] == 'Minions' and r['own_tile'] == [13, 16])
            row.update(accepted=True, reason='OK')
        elif change == 'class':
            changed['classifications'][0]['placement'] = 2
        elif change == 'missing_class':
            changed['classifications'].pop()
        elif change in ('lateral_fit', 'outward_fit'):
            row = next(r for r in changed['rows'] if r['own_tile'] == [4, 14])
            row['resolved_own_tiles'] = [3.5, 14.5] if change == 'lateral_fit' else [4.5, 15.5]
        elif change == 'old_version':
            changed['protocol'] = 'rsim-own-half-intersection-v1'
        else:
            changed['protocol'] = 'rsim-static-water-intersection-v2'
        path.write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            placement.proof()
    monkeypatch.delenv(placement.PROOF_ENV)
    with pytest.raises(ValueError, match=placement.PROOF_ENV):
        placement.proof()


def test_proof_identity_and_resume_are_bound(tmp_path, monkeypatch):
    from . import run
    # Reuse protocol fixtures without constructing a runtime or an external process.
    old = dict(arm='A', index=0, seed=1, seat=0, opponent='v1', decks=[], profile={}, view={})
    identity = {'placement_compatibility': {'sha256': 'a'*64}}
    path = tmp_path/'row.json'
    path.write_text(json.dumps(dict(old, **identity)))
    monkeypatch.setattr(run, 'row_issues', lambda row: {})
    assert run.resume_done(path, old, 'A', identity)
    with pytest.raises(ValueError, match='identity differs'):
        run.resume_done(path, old, 'A', {'placement_compatibility': {'sha256': 'b'*64}})
    invalid = dict(source_sha256={'bot/levels/placement.py': 'a'*64})
    assert 'missing exact-byte placement microprobe identity' in run.identity_problems(invalid)


@pytest.mark.parametrize('all11', [False, True])
def test_bank_scope_exact_match_and_explicit_legacy_exception(all11):
    from types import SimpleNamespace
    from .run import validate_bank_scope
    rt = SimpleNamespace(levels_scope={'restricted_sha256': 'fixed', 'retained_decks': 2500})
    validate_bank_scope({'scope': dict(rt.levels_scope)}, rt, all11_gate=all11)
    with pytest.raises(ValueError, match='bank scope'):
        validate_bank_scope({'scope': dict(rt.levels_scope, retained_decks=2499)}, rt, all11_gate=all11)
    with pytest.raises(ValueError, match='bank scope'):
        validate_bank_scope({'scope': None}, rt, all11_gate=all11)
    if all11:
        validate_bank_scope({}, rt, all11_gate=True)
    else:
        with pytest.raises(ValueError, match='bank scope'):
            validate_bank_scope({}, rt, all11_gate=False)


def test_observed_installation_evidence_cannot_be_missing_stale_or_unexercised():
    from .run import placement_evidence_ok, row_issues
    proof = dict(version=placement.VERSION, sha256='a'*64)
    mask = dict(version=placement.VERSION, calls=1, removed=0, unknown_slots=0, mirror_slots=0, water_removed=0)
    observed = dict(version=placement.VERSION, proof=proof, actors={
        str(seat): dict(kind=kind, path='poller.player.mask_builder',
                       candidate_path='p.core.bots[balanced].mask_builder' if kind == 'search' else None,
                       mask=dict(mask)) for seat, kind in enumerate(('search', 'policy'))},
        scripts={f'R.bots[{s}].mask_builder': dict(mask) for s in ('balanced', 'pressure', 'defense')})
    row = dict(placement_compatibility=proof, placement_diagnostics=observed)
    assert placement_evidence_ok(row)
    for field, value in [('placement_diagnostics', None), ('placement_diagnostics', {}),
                         ('placement_compatibility', dict(proof, sha256='b'*64))]:
        changed = dict(row, **{field: value})
        assert not placement_evidence_ok(changed) and row_issues(changed)['placement_failures'] == 1
    for path, value in [(('actors', '1', 'mask', 'calls'), 0),
                        (('scripts', 'R.bots[balanced].mask_builder', 'calls'), None),
                        (('actors', '0', 'candidate_path'), 'wrong.path')]:
        changed = copy.deepcopy(row)
        target = changed['placement_diagnostics']
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        assert not placement_evidence_ok(changed)


@pytest.fixture(scope='module')
def runtime(bootstrap):
    if bootstrap.rt is None:
        pytest.skip('set CLASHER_PLACEMENT_INTEGRATION=1 after reviewed exact-binary microprobe')
    return bootstrap.rt


DECK = ('Knight', 'Minions', 'Cannon', 'Fireball', 'Giant', 'Musketeer', 'Archers', 'Arrows')


def test_certified_binary_matrix_against_actual_public_mask(runtime):
    """No measured refusal may be admitted; accepted base-eligible controls must survive."""
    rt = runtime
    receipt = json.loads(Path(rt._placement['proof']['path']).read_bytes())
    wrapper = rt.R.bots['balanced'].mask_builder
    contradictions, overmasked = [], []
    for row in receipt['river_matrix']:
        source = request(wrapper.builder, ['Knight', 'Fireball', row['card'], 'Arrows'], row['seat'], tuple(row['enemy_down']))
        before, after = wrapper.base.build(source), wrapper.build(source)
        assert not (after & ~before).any() and np.array_equal(before[2304:], after[2304:])
        if row['card'] == 'Fireball':
            assert np.array_equal(before[1152:1728], after[1152:1728])
        x, y = row['own_tile']
        if after[1152+y*18+x] and not row['accepted']:
            contradictions.append(row)
        if row['accepted'] and before[1152+y*18+x] and not after[1152+y*18+x]:
            overmasked.append(row)
    assert not contradictions, 'public mask admits installed-binary refusals: ' + json.dumps(contradictions)
    assert not overmasked, 'accepted eligible controls were removed: ' + json.dumps(overmasked)


def _match(rt, seat, down, *, recorded=False, hidden=False, ordinary='Cannon'):
    from bot.players.royalesim_match import RsimMatch
    from bot.players.royalesim_vocab import load
    deck = tuple(ordinary if c == 'Cannon' else c for c in DECK)
    match = RsimMatch(rt, load(rt), [deck, deck], 1701, client='16.402', record_commands=recorded)
    hp = [list(p['tower_max_hp']) for p in match.state['players']]
    for slot, dead in zip((1, 2) if seat == 0 else (2, 1), down):
        if dead:
            hp[1-seat][slot] = 0
    decks = [[match.ids[{'Archers': 'Archer'}.get(c, c)] for c in deck] for _ in (0, 1)]
    levels = [[11]*8, [11]*8]
    elixir, spawns = [10000, 10000], []
    if hidden:
        decks[1-seat] = list(reversed(decks[1-seat]))
        levels[1-seat], elixir[1-seat] = [7]*8, 6000
        x, y = (13.5, 28.5) if seat == 0 else (4.5, 3.5)
        spawns = [(1-seat, match.ids['Ghost'], round(x*18000), round(y*18000), -1)]
    match.b.reset(seed=1701, decks=decks, shuffle=0, start_tick=100, elixir_milli=elixir,
                  tower_hp=hp, spawns=spawns, levels=levels, tower_levels=[11, 11])
    if hidden:
        match.b.set_command_delay_ticks(1000 if seat == 1 else 0, 1000 if seat == 0 else 0)
        # Pending opponent command remains hidden and does not enter accepted public events.
        match.b.step([(1-seat, 0, 9*18000, (28 if seat == 0 else 4)*18000)], 0)
    match.b.step([], 80)  # Royal Ghost can become invisible; both fixtures have the same tick.
    match.refresh()
    return match


@pytest.mark.parametrize('seat, down, ordinary',
    [(seat, down, 'Cannon') for seat in (0, 1) for down in placement_probe.PATTERNS]
    + [(seat, (True, True), 'Tesla') for seat in (0, 1)])
def test_actual_candidates_policy_fallback_and_both_opponents(runtime, seat, down, ordinary):
    from bot.levels.player import make_arm_player
    from bot.players.policy import PolicyPlayer
    from bot.players.base import MatchContext, PublicView
    from clasher.rl.public_action_mask import PublicActionMaskInput
    from bot.search.lopp import FAILURES
    rt = runtime
    match = _match(rt, seat, down, ordinary=ordinary)
    info = match.information(seat)
    view = PublicView(info.tick, seat, info, info, [], (), True)
    ctx = MatchContext(seat=seat, seed=1701, own_order=tuple(match.decks[seat]))
    fair = dict(own_levels=dict.fromkeys(match.decks[seat], 11), own_tower=11, opp_tower=11)
    install = placement.install_runtime(rt)
    assert placement.install_runtime(rt) is install
    actors = [make_arm_player(rt, arm, view=fair, parity_all11=arm == 'B') for arm in ('A', 'B0', 'B')]
    actors += [placement.install_player(PolicyPlayer(rt, source), kind='policy') for source in ('R3a', 'v1')]
    for player in actors:
        try:
            assert placement.install_player(player, kind=player._placement_actor['kind']) is player
            player.start(ctx)
            wrapper = player.poller.player.mask_builder
            assert isinstance(wrapper, placement.PlacementMask)
            req = PublicActionMaskInput.from_confidence_observation(info.packet)
            before = wrapper.base.build(req)
            expected = wrapper.build(req)
            assert np.array_equal(expected[2*576:2*576+15*18], before[2*576:2*576+15*18])
            assert not expected[2*576+15*18:3*576].any()
            assert not (expected & ~before).any() and expected[2304]
            for x, y in placement_probe.FAILED:
                assert not expected[2*576+y*18+x]
            for slot in (0, 1):  # Knight AND flying Minions share the fixed WATER test.
                assert not expected[slot*576:(slot+1)*576][expected_water()].any()
                assert np.array_equal(expected[slot*576:(slot+1)*576][~expected_water()],
                                      before[slot*576:(slot+1)*576][~expected_water()])
            assert np.array_equal(expected[3*576:4*576], before[3*576:4*576])  # Fireball.
            if all(down):
                assert before[2*576+15*18:3*576].any()
                assert before[:576][expected_water()].any() and wrapper.water_removed > 0
            if player._placement_actor['kind'] == 'search':
                illegal = [2*576+y*18+x for x, y in placement_probe.FAILED]
                illegal += [slot*576+y*18+x for slot in (0, 1) for y in (15, 16) for x in (2, 4, 13, 15)]
                candidates, mask = player.p.core.candidates(info.packet, illegal)
                assert 2304 in candidates and all(candidate_allowed(a, mask) for a in candidates)
                assert not set(candidates).intersection(illegal)
                assert not any(a//576 == 2 and a%576//18 >= 15 for a in candidates if a < 2304)
                bot = player.p.core.bots['balanced']
                assert all(candidate_allowed(r.action_id, mask) for r in bot._ranked_actions(info.packet, all_plays=True))
                assert candidate_allowed(bot.decide(info.packet).action_id, mask)
            failures = dict(FAILURES)
            decision = player.act(view)  # Real fallback/proposals/scorer or real sampled policy opponent.
            assert dict(FAILURES) == failures
            assert 0 <= decision.action <= 2304 and expected[decision.action]
            selected = (decision.stats or {}).get('action')
            from bot.search.players import TIMED_WAITS
            if selected in TIMED_WAITS:
                assert decision.action == 2304 and decision.wait_ticks == TIMED_WAITS[selected]
            if player.cached is not None:
                from imitation.evaluation.d1 import model_packet
                proposals = player.cached.propose(model_packet(info.packet, player.poller.mask), player.poller.player.last_d1)
                assert all(candidate_allowed(p['action'], expected) for p in proposals)
            if player._placement_actor['kind'] == 'search' and hasattr(player, 'level_root') and hasattr(player.level_root, 'lc'):
                assert player.level_root.lc is rt._level_configs
            placement.validate_player(player, require_calls=True)
            print(json.dumps(dict(seat=seat, down=down, ordinary=ordinary, player=player.name, action=decision.action,
                                  mask=wrapper.diagnostics())), flush=True)
        finally:
            player.close()
    # Replacing an actual path is an error, not a stats-only successful installation.
    poller = actors[-1].poller.player
    wrapped = poller.mask_builder
    poller.mask_builder = wrapped.base
    with pytest.raises(ValueError, match='missing/replaced'):
        placement.validate_player(actors[-1])
    poller.mask_builder = wrapped


@pytest.mark.parametrize('seat', [0, 1])
def test_hidden_state_invariance_and_recorder(runtime, seat):
    from bot.players.base import MatchContext, PublicView
    from bot.players.policy import PolicyPlayer
    from .gates import _plain, _difference
    from .player import make_arm_player
    from bot.search.lopp import FAILURES
    rt = runtime
    matches = [_match(rt, seat, (True, True), hidden=hidden) for hidden in (False, True)]
    infos = [m.information(seat) for m in matches]
    assert _plain(infos[0]) == _plain(infos[1]), _difference(_plain(infos[0]), _plain(infos[1]))
    fair = dict(own_levels=dict.fromkeys(DECK, 11), own_tower=11, opp_tower=11)
    for source in ('A', 'B0', 'B', 'R3a', 'v1'):
        decisions, roots = [], []
        for info in infos:
            player = (make_arm_player(rt, source, view=fair) if source in ('A', 'B0', 'B') else
                      placement.install_player(PolicyPlayer(rt, source), kind='policy'))
            try:
                player.start(MatchContext(seat=seat, seed=1701, own_order=DECK))
                if source == 'B':
                    assert player.level_root.lc is rt._level_configs
                if source in ('A', 'B0', 'B'):
                    rng = np.random.default_rng(7712)
                    belief = player.p.belief.sample(rng)
                    root_fn = player.root_fn or rt.R.root
                    roots.append(json.loads(root_fn(info, belief, rng).snapshot()))
                before = player.level_root.stats['roots'] if source == 'B' else 0
                failures = dict(FAILURES)
                decision = player.act(PublicView(info.tick, seat, info, info, [], (), True))
                assert dict(FAILURES) == failures
                if source == 'B':
                    assert player.level_root.stats['roots'] > before
                placement.validate_player(player, require_calls=True)
                decisions.append((decision.action, decision.wait_ticks, player.poller.mask.copy()))
            finally:
                player.close()
        assert decisions[0][:2] == decisions[1][:2]
        assert np.array_equal(decisions[0][2], decisions[1][2])
        if roots:
            assert roots[0] == roots[1], _difference(roots[0], roots[1])
    # Recorder is offline only: accepted and deliberately refused commands have identical public effects.
    a, b = [_match(rt, seat, (True, True), recorded=flag) for flag in (False, True)]
    for action in (2*576+19*18+9, 2*576+10*18+9):
        results = [m.execute([(seat, action, 'Cannon')]) for m in (a, b)]
        assert results[0] == results[1]
        assert _plain(a.information(seat)) == _plain(b.information(seat))
        assert a.public_events == b.public_events
    assert a.command_results is None
    assert [row['ok'] for row in b.command_results] == [False, True]
    assert all({'reason', 'result', 'target_subtiles'} <= row.keys() for row in b.command_results)
