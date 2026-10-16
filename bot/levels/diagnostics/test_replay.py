"""Public fixtures for the recorded driver, physics audit and fail-closed evidence.

No Runtime/model construction. Run only on 01 after independent source review.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import shutil
from types import SimpleNamespace as NS

import pytest

from bot.players.base import PublicView
from bot.levels.diagnostics import live, protocol, replay

ONE_OPPORTUNITY = [dict(n=1, tick=100, clock_s=170.)]


def towers(king=1., number=3312):
    return [dict(owner=o, kind=k, side=s, alive=True, hp_frac=king if o == 0 and k == 'king' else 1.,
                 hp_read=number if o == 0 and k == 'king' else (3312 if k == 'king' else 2030))
            for o in (0, 1) for k, s in (('king', 'center'), ('princess', 'left'), ('princess', 'right'))]


def fixture_view(tick=100, can_act=True):
    return PublicView(tick, 0, NS(own=dict(hand=['Cannon', 'Giant', 'Archers', 'Fireball'], elixir=7.),
        packet=NS(public='unchanged')), NS(packet=NS(public='reserved')), [], (), can_act)


class StubShadow:
    def __init__(self, action, *, mutate=False, error=None):
        self.action, self.mutate, self.error = action, mutate, error
        self.views = []

    def act(self, view):
        self.views.append(view)
        sha = protocol.digest(view)
        hand = list(view.info.own['hand'])
        out = dict(view_sha256=sha, chosen=protocol.action_details(self.action, 0, hand),
                   searched=view.can_act, root_calls=int(view.can_act), cannon_available=True,
                   cannon_affordable=True, cannon_home_defense=self.action < 576, threats=[])
        if self.error:
            out['error'] = self.error
        if self.mutate:
            view.info.own['hand'][0] = 'Fireball'
        return out


def fixture_facade(*, shadows=None):
    decision = dict(n=1, poll=100, action=10, submitted=True, card='Cannon', tap_id=7,
                    stats=dict(source='search', action=10))
    output = []
    facade = live.RecordedFacade(shadows or {'A': StubShadow(100), 'B': StubShadow(2304)},
                                {1: decision}, {7}, output.append)
    facade.frame = dict(n=1, clock_s=170., towers=towers())
    facade.expected_poll = 100
    return facade, output


def test_shadows_cannot_drive_commands_or_mutate_common_state():
    a, b = StubShadow(100, mutate=True), StubShadow(2304)
    facade, rows = fixture_facade(shadows={'A': a, 'B': b})
    common = fixture_view()
    before = protocol.digest(common)
    chosen = facade.act(common)
    assert chosen.action == 10  # Recorded tap, regardless of either shadow.
    assert protocol.digest(common) == before
    assert b.views[0].info.own['hand'][0] == 'Cannon'
    assert rows[0]['arms']['A']['view_sha256'] == rows[0]['arms']['B']['view_sha256']
    assert facade.evidence()['missing_decisions'] == []


def test_catchup_is_labelled_maintenance_and_never_searched():
    facade, rows = fixture_facade()
    decision = facade.act(fixture_view(tick=95, can_act=False))
    assert decision.action == 2304
    assert rows[0]['catch_up'] and not rows[0]['opportunity']
    assert all(not v['searched'] for v in rows[0]['arms'].values())
    assert facade.evidence()['missing_decisions'] == [1]


def test_missing_recorded_poll_cannot_invent_a_search_opportunity():
    facade, rows = fixture_facade()
    facade.frame['n'] = 2
    assert facade.act(fixture_view()).action == 2304
    assert not rows[0]['opportunity']
    assert facade.evidence()['mismatches'][0]['kind'] == 'missing_recorded_poll'


def test_wrong_known_own_slot_aborts_driver_instead_of_playing_another_card():
    facade, rows = fixture_facade()
    view = fixture_view()
    view.info.own['hand'][0] = 'Giant'
    with pytest.raises(ValueError, match='command context diverged'):
        facade.act(view)
    assert facade.evidence()['mismatches'][0]['kind'] == 'recorded_card_slot'


@pytest.mark.parametrize('change', [dict(submitted=False), dict(tap_id=8), dict(tap='dry'), dict(error='bad')])
def test_unconfirmed_recorded_commands_fail_closed(change):
    d = dict(n=1, action=10, submitted=True, card='Cannon', tap_id=7)
    with pytest.raises(ValueError):
        protocol.command(dict(d, **change), {7})


def test_recorded_wait_does_not_invent_a_timer():
    assert protocol.command(dict(n=1, action=2304, submitted=False, stats={}), set()) == (2304, 0)
    assert protocol.command(dict(n=1, action=2304, submitted=False, stats={'action': 2402}), set()) == (2304, 40)


def test_pending_replacement_and_unchanged_conditional_HUD_confirmation():
    from bot.players.base import Decision
    old = NS(action=813, card='Giant', submitted=160, cost=5)
    new = NS(action=233, card='Archers', submitted=170, cost=3)
    logged = dict(n=234, poll=170, action=233, submitted=False, stats=dict(source='search'))
    assert protocol.command(logged, {26, 27, 28, 29, 30}) == (233, 0)
    assert protocol.command_kind(logged) == 'unverified_internal_reservation'
    with pytest.raises(ValueError):
        protocol.command(dict(logged, n=235), set())

    class Session:
        def _confirm_pending(self, record, poll):
            self.confirmations += 1
            if poll == 175:  # Subsequent public HUD evidence, not action233 alone.
                record['events'] = [dict(owner=0, card='Archers', tick=poll)]

        def _poll(self, record, poll, catch_up=False):
            self._confirm_pending(record, poll)
            if poll == 170:
                self.ch.pending[:] = [new]
                return Decision(233)
            return Decision(2304)

    rows = []
    s = live.recorded_session_class(Session)()
    s.ch, s.confirmations = NS(pending=[old]), 0
    s.player = NS(decisions={234: logged}, frame={'n': 234}, sink=rows.append,
                  conditional_inferences=[], conditional_context=False)
    pending_count_before = len(s.ch.pending)
    s._poll({}, 170)
    assert len(s.ch.pending) == pending_count_before  # Original submitted-length test misses replacement.
    assert s.ch.pending[0] is new and s._unverified_pending is new
    assert rows[0]['kind'] == 'unverified_internal_reservation'
    assert s.player.conditional_inferences == []  # Action alone creates no event.
    s.player.frame = {'n': 235}
    record = {}
    s._poll(record, 175)
    assert s.confirmations == 2  # The actual public-HUD confirmation pipeline is unchanged.
    assert record['events'] == [dict(owner=0, card='Archers', tick=175)]
    event = s.player.conditional_inferences[0]
    assert not event['verified_actual_play'] and not event['acknowledged_tap']
    assert event['event']['card'] == 'Archers' and s.player.conditional_context
    s.ch.pending[:] = [NS(action=254, card='Archers', submitted=270, cost=3)]
    s._poll({}, 275)
    assert s.confirmations == 3  # A later acknowledged actual command is not altered.


def test_unverified_replacement_contradiction_aborts():
    from bot.players.base import Decision

    class Session:
        def _poll(self, record, poll, catch_up=False):
            return Decision(233)  # No newly reserved command: contradiction.

    s = live.recorded_session_class(Session)()
    s.ch = NS(pending=[])
    s.player = NS(decisions={234: dict(n=234, poll=170, action=233, submitted=False)},
                  frame={'n': 234}, sink=lambda row: None)
    with pytest.raises(ValueError, match='contradicts'):
        s._poll({}, 170)


def test_public_clock_window_and_real_rounding_boundary():
    assert protocol.in_window(176.938373167)
    assert protocol.in_window(134.741730583)
    assert not protocol.in_window(177.)
    assert not protocol.in_window(133.999)
    # n207's metadata was not an explicit input tick. The anchored translator
    # rounds 99.60 to100; flooring would produce the wrong public poll95.
    tick = (22343.765084 - 17363.531709) / 50
    assert int(round(tick)) // 5 * 5 == 100
    assert int(tick) // 5 * 5 == 95


def test_59_hp_fraction_is_retained_and_l6_rounding_exposed():
    record = dict(towers=towers(.0178, 59))
    original = protocol.digest(record)
    t = protocol.tower_audit(record)[0]
    assert t['hp_frac'] == .0178 and t['hp_read'] == 59
    assert t['reconstructed_l6_hp'] == pytest.approx(58.9536)
    assert t['number_consistent']
    assert protocol.digest(record) == original
    record['towers'][3]['hp_read'] = 2400  # Early max inference was imperfect.
    assert not protocol.tower_audit(record)[3]['number_consistent']


def test_missing_tower_cannot_silently_become_alive_full_hp():
    with pytest.raises(ValueError, match='six explicit'):
        protocol.tower_audit(dict(towers=towers()[:-1]))


def test_actual_root_59_hp_cannot_silently_become_40_hp():
    tower = dict(owner=0, name='KingTower', x=9., hp=58.9536, max_hp=3312)
    fractions = [1., 0., .0178, 0., 1., 1.]
    assert protocol.root_tower_audit({'towers': [tower]}, fractions, 'B')[0]['consistent']
    assert not protocol.root_tower_audit({'towers': [dict(tower, hp=40.)]}, fractions, 'B')[0]['consistent']
    assert not protocol.root_tower_audit({'towers': [dict(tower, max_hp=4824)]}, fractions, 'B')[0]['consistent']


def test_error_states_stay_in_pair_denominator_and_fail_acceptance():
    facade, rows = fixture_facade(shadows={'A': StubShadow(100), 'B': StubShadow(2304, error='native panic')})
    facade.act(fixture_view())
    report = protocol.summary(rows, facade.evidence(), {}, ONE_OPPORTUNITY)
    assert report['opportunities'] == 1 and report['matched'] == 0
    assert len(report['errors']) == 1 and not report['pass_checks']
    assert not report['checks']['matched_all_opportunities']


def test_native_failure_returning_a_fallback_is_still_an_error(monkeypatch):
    import numpy as np
    from bot.players.base import Decision
    from bot.search import lopp
    from bot.levels import scope
    counts = Counter()
    monkeypatch.setattr(lopp, 'FAILURES', counts)
    monkeypatch.setattr(scope, 'install', lambda rt: rt.levels_scope)
    prior = dict(decks=[])
    rt = NS(PRIOR=prior, levels_scope={'restricted_sha256': protocol.digest(prior)},
            R=NS(costs={'Cannon': 3}, builder=NS(token_names=[])))

    def failed_act(view):
        counts['native_serial'] += 1
        return Decision(2304, stats={'native_failure': 'native_serial'})

    player = NS(rt=rt, act=failed_act, level_root=None, p=NS(belief=NS()))
    shadow = live.Shadow.__new__(live.Shadow)
    shadow.player, shadow.rt, shadow.arm = player, rt, 'B'
    view = fixture_view()
    view.info.packet.observation = NS(entity_ids=np.empty(0, int), entity_mask=np.zeros(0, bool),
                                     entity_features=np.empty((0, 32)), global_features=np.zeros(32))
    row = shadow.act(view)
    assert row['failures'] == {'native_serial': 1}
    assert 'native/search failure' in row['error']
    assert row['chosen']['action'] == 2304  # Retained as failed evidence, never accepted.


def test_blocked_recorded_search_is_not_a_successful_pair():
    facade, rows = fixture_facade()
    facade.act(fixture_view(can_act=False))
    report = protocol.summary(rows, facade.evidence(), {}, ONE_OPPORTUNITY)
    assert report['matched'] == 0 and not report['pass_checks']


def test_summary_counts_cannon_and_first_difference_without_outcome():
    facade, rows = fixture_facade()
    facade.act(fixture_view())
    report = protocol.summary(rows, facade.evidence(), {}, ONE_OPPORTUNITY)
    assert report['pass_checks'] and report['action_differences'] == 1
    assert report['arms']['A']['cannon_chosen'] == 1
    assert report['arms']['B']['cannon_chosen'] == 0
    assert report['first_differences'][0]['tick'] == 100
    assert 'score' not in report and 'winner' not in report


def test_actual_B_hook_follows_start_replacement_and_consumes_rng_once(monkeypatch):
    import numpy as np
    from bot.levels import root as level_root
    rng = NS(calls=0)
    native = object()
    snapshot_calls = []

    class Native:
        def snapshot(self):
            snapshot_calls.append(1)
            return json.dumps(dict(tick=100, entities=[dict(id=1, owner=0, x=9., y=3., hp=58.9536,
                alive=True, **{'class': 'Building'}, stats=dict(name='KingTower', max_hp=3312, damage=70))]))

    class Exact:
        def __init__(self, *args, **kwargs):
            self.stats = dict(roots=0)

        def root(self, info, opponent, generator):
            generator.calls += 1
            self.stats['roots'] += 1
            return Native()

    monkeypatch.setattr(level_root, 'ExactLevelRoot', Exact)
    monkeypatch.setattr(level_root, 'leaf_native', lambda *args: native)
    rt = NS()
    player = NS(native_threads=1, pool_size=0, roots=1, p=NS(core=object()))
    # Actual serial start reconstructs this core. Hooks must target this one.
    replacement = NS(native=None, candidates=lambda packet, proposals: ([2304], np.ones(2306, dtype=bool)))
    player.p.core = replacement
    live.install_hooks(player, rt, 'B', object())
    player.root_fn(None, None, rng)
    assert rng.calls == 1 and snapshot_calls == [1]
    assert replacement.native is native and player.level_root.stats['roots'] == 1
    assert player._diagnostic_roots[0]['towers'][0]['hp'] == 58.9536
    assert not hasattr(rt, '_placement')


@pytest.fixture
def export_cache(tmp_path, monkeypatch):
    from bot.levels import configs, profile
    config = dict(cards={'Cannon': dict(units=[[], []])})
    rt = NS(R=NS(config=config), pins=dict(native_sha256='native', gamedata_sha256='data'))
    original = configs.LevelConfigs
    lc = original(rt, cache=tmp_path)
    lc.dir.mkdir(parents=True)
    monkeypatch.setattr(configs, 'LevelConfigs', lambda runtime: original(runtime, cache=tmp_path))
    monkeypatch.setattr(profile, 'LIVE_DECK', ('Cannon',))
    monkeypatch.setattr(profile, 'OWN_LEVELS', {'Cannon': 6})
    monkeypatch.setattr(profile, 'OpponentEstimate', lambda runtime: lambda card: 5)
    entry = dict(card=config['cards']['Cannon'], tables={})
    for level in (5, 6, 11):
        lc.path(level).write_text(json.dumps(dict(level=level, cards={'Cannon': entry}, errors={})))
    (lc.dir / 'supported.json').write_text(json.dumps(dict(cards=['Cannon'], unsupported={},
        comparison='native-json-v1', reference_sha256=hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest())))
    return rt, lc


def test_cache_is_read_once_frozen_and_never_exported(export_cache):
    rt, original = export_cache
    lc, manifest = live.existing_configs(rt)
    before = protocol.digest(lc.load(6))
    original.path(6).write_text('{}')
    assert protocol.digest(lc.load(6)) == before
    assert protocol.file_sha(original.path(6)) != manifest['levels']['6']['raw_sha256']
    with pytest.raises(ValueError, match='unregistered'):
        lc.load(7)
    with pytest.raises(ValueError, match='cannot build'):
        lc.build(7)
    assert not lc.path(7).exists()


def test_missing_cache_aborts_without_any_build_or_write(export_cache):
    rt, lc = export_cache
    lc.path(6).unlink()
    before = sorted(p.name for p in lc.dir.iterdir())
    with pytest.raises(FileNotFoundError):
        live.existing_configs(rt)
    assert sorted(p.name for p in lc.dir.iterdir()) == before


def test_cache_error_records_are_retained_but_partial_coverage_rejected(export_cache):
    rt, original = export_cache
    original.path(5).write_text(json.dumps(dict(level=5, cards={}, errors={'Cannon': 'unsupported'})))
    lc, manifest = live.existing_configs(rt)
    assert lc.entry('Cannon', 5) is None
    assert manifest['levels']['5']['errors'] == {'Cannon': 'unsupported'}
    original.path(5).write_text(json.dumps(dict(level=5, cards={}, errors={})))
    with pytest.raises(ValueError, match='incomplete'):
        live.existing_configs(rt)


@pytest.mark.parametrize('name', ['pool.npz', 'main02.pt', 'gamedata.json', 'native/clasher_core.abi3.so',
    'imitation/evaluation/paths.py', 'imitation/evaluation/standalone.py', 'imitation/evaluation/d1.py',
    'imitation/model/inference.py', 'src/clasher/rl/public_action_mask.py',
    'src/clasher/rl/contract_v5.py', 'engine-rs/quickwin_resources.py',
    'src/clasher/rl/contract_v5_tokens.json'])
def test_runtime_identity_detects_referenced_content_tampering(tmp_path, monkeypatch, name):
    root = tmp_path / 'runtime'
    root.mkdir()
    prior = 'reports/strategy_council_20260928/c56/engine/root-v3/human_deck_catalog.json'
    for relative in ('main02.pt', 'R3a.pt', 'gamedata.json', 'pool.npz', 'native/clasher_core.abi3.so', prior,
                     'src/clasher/rl/contract_v5_tokens.json', name):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original')
    monkeypatch.setenv('CLASHER_LOPP_MODELS', str(root))
    monkeypatch.delenv('CLASHER_ROOT', raising=False)
    monkeypatch.delenv('CLASHER_DELAY_NATIVE_DIR', raising=False)
    monkeypatch.delenv('CLASHER_EVAL_RUNTIME_ROOT', raising=False)
    if name.endswith('contract_v5_tokens.json'):
        (root / name).write_text('["Tower"]\n')
        loaded_tokens = json.loads((root / name).read_text())
    before = replay.runtime_content(root)
    if name.endswith('contract_v5_tokens.json'):
        (root / name).write_text(' ["Tower"]\n')  # Same loaded identities, different exact serving bytes.
        assert json.loads((root / name).read_text()) == loaded_tokens
    else:
        (root / name).write_text('tampered')
    assert replay.runtime_content(root) != before


def test_effective_behavior_environment_is_bound(monkeypatch):
    monkeypatch.delenv('BOT_BELIEF_PRIOR', raising=False)
    before = replay.environment()
    monkeypatch.setenv('BOT_BELIEF_PRIOR', 'different')
    assert replay.environment() != before


def test_duplicate_decisions_and_input_bytes_fail_closed(tmp_path):
    with pytest.raises(ValueError, match='duplicate'):
        protocol.unique([dict(n=1), dict(n=1)], 'n')
    # Fixture hashes cover exact bytes, including changes that parse identically.
    names = list(protocol.INPUT_SHA256)
    for name in names:
        (tmp_path / name).write_text('{}\n')
    with pytest.raises(ValueError, match='input hashes differ'):
        protocol.load_inputs(tmp_path)


def test_launch_receipt_serializes_paths_without_execution(tmp_path):
    path = tmp_path / 'receipt.json'
    replay.write(path, dict(args={'out': tmp_path}, identity='fixture'))
    assert json.loads(path.read_text())['args']['out'] == str(tmp_path)


@pytest.fixture
def portable_sources(tmp_path, monkeypatch):
    """Only portable audit files, no live checkout in this serving tree."""
    audit = tmp_path / 'package-audit'
    shutil.copytree(replay.AUDIT, audit)
    repo = tmp_path / 'repo'
    for relative in ('bot/players/royalesim_vocab.json', 'bot/search/lopp_feat.py',
                     'bot/players/runtime.py', 'reports/explore/x4s/sdefault.py'):
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}\n' if path.suffix == '.json' else '# reviewed fixture\n')
    env = tmp_path / 'env.sh'
    env.write_text('# reviewed environment fixture\n')
    monkeypatch.setattr(replay, 'AUDIT', audit)
    monkeypatch.setattr(replay, 'REPO', repo)
    monkeypatch.setattr(replay, 'ENV', env)
    return audit, repo


@pytest.mark.parametrize('name', ['drive.py.txt', 'towers.py.txt', 'provenance.json'])
def test_missing_portable_audit_fails_without_a_live_checkout(portable_sources, name):
    audit, _ = portable_sources
    assert replay.audit_sources()  # Reads raw text, never imports the snapshots.
    (audit / name).unlink()
    with pytest.raises(FileNotFoundError):
        replay.sources()


@pytest.mark.parametrize('name', ['drive.py.txt', 'towers.py.txt', 'provenance.json'])
def test_changed_portable_audit_bytes_are_rejected(portable_sources, name):
    audit, _ = portable_sources
    path = audit / name
    path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises(ValueError, match='portable audit bytes changed'):
        replay.sources()


def test_serving_feature_source_is_bound_before_and_after(portable_sources):
    _, repo = portable_sources
    before = replay.sources()
    feature = repo / 'bot/search/lopp_feat.py'
    assert str(feature.resolve()) in before
    feature.write_text('# changed serving feature definition\n')
    assert replay.sources() != before


@pytest.fixture
def guarded_01(tmp_path, monkeypatch):
    job = tmp_path / 'job'
    expected = job / 'runtime/live16402b-r2'
    monkeypatch.setattr(replay, 'JOB', job)
    monkeypatch.setattr(replay.socket, 'gethostname', lambda: '127x01')
    values = dict(PYTHONHASHSEED='0', CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1',
                  MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', RAYON_NUM_THREADS='1',
                  CLASHER_BOT_RUNTIME_PINS='live16402b-r2', CLASHER_BOT_RUNTIME=str(expected))
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    for key in ('CLASHER_ROOT', 'CLASHER_DELAY_NATIVE_DIR', 'CLASHER_EVAL_RUNTIME_ROOT',
                'CLASHER_LEVELS_PLACEMENT_PROOF'):
        monkeypatch.delenv(key, raising=False)
    return job / 'diagnostic-output', expected


def test_external_evaluation_root_is_refused_before_reserving_output(guarded_01, tmp_path, monkeypatch):
    out, expected = guarded_01
    replay.guard(out)  # Unset safely defaults to the authorized serving tree.
    monkeypatch.setenv('CLASHER_EVAL_RUNTIME_ROOT', str(expected))
    replay.guard(out)
    monkeypatch.setenv('CLASHER_EVAL_RUNTIME_ROOT', str(tmp_path / 'other-serving-root'))
    with pytest.raises(ValueError, match='CLASHER_EVAL_RUNTIME_ROOT'):
        replay.guard(out)
    with pytest.raises(ValueError, match='CLASHER_EVAL_RUNTIME_ROOT'):
        replay.runtime_content(expected)
    assert not out.exists()


@pytest.fixture
def planned_inputs(monkeypatch):
    frames = [dict(n=n, clock_s=170.-i) for i, n in enumerate((1, 2, 3))]
    decisions = {n: dict(n=n, poll=100+10*i, action=10, submitted=True, card='Cannon', tap_id=7+i,
                         stats={'source': 'search'}) for i, n in enumerate((1, 2, 3))}
    data = {'perception': frames, 'session-config': {}, 'session': {}}
    monkeypatch.setattr(replay, 'load_inputs', lambda path: (data, {'fixture': 'pinned'}, decisions, {7, 8, 9}, {}))
    return frames, decisions


@pytest.mark.parametrize('problem', ['missing', 'changed'])
def test_audit_preflight_failure_does_not_occupy_output_name(
        guarded_01, portable_sources, planned_inputs, problem):
    out, _ = guarded_01
    audit, _ = portable_sources
    path = audit / 'towers.py.txt'
    if problem == 'missing':
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b'\n')
    with pytest.raises((ValueError, FileNotFoundError)):
        replay.main(['--inputs', 'fixture', '--out', str(out)])
    assert not out.exists()


def test_failure_after_reservation_writes_launch_error_and_full_denominator(
        guarded_01, portable_sources, planned_inputs, monkeypatch):
    out, _ = guarded_01

    def fail_before_project_import(root):
        raise ValueError('fixture missing serving baseline')

    monkeypatch.setattr(replay, 'runtime_content', fail_before_project_import)
    assert replay.main(['--inputs', 'fixture', '--out', str(out)]) == 1
    launch = json.loads((out / 'launch.json').read_text())
    receipt = json.loads((out / 'receipt.json').read_text())
    report = json.loads((out / 'report.json').read_text())
    assert len(launch['expected_opportunities']) == 3
    assert 'fixture missing serving baseline' in receipt['fatal_error']['error']
    assert report['expected'] == 3 and report['attempted'] == 0 and report['unvisited'] == 3
    assert not report['pass_checks'] and not report['checks']['matched_all_opportunities']
    assert 'fixture missing serving baseline' in (out / 'states.jsonl').read_text()


def test_roster_is_fixed_by_recorded_search_gating_and_public_clock():
    frames = [dict(n=1, clock_s=176.9), dict(n=2, clock_s=177.), dict(n=3, clock_s=170.)]
    decisions = [dict(n=1, poll=100, stats={'source': 'search'}),
                 dict(n=2, poll=110, stats={'source': 'search'}), dict(n=3, poll=120, stats=None)]
    assert protocol.opportunity_roster(frames, decisions) == [dict(n=1, tick=100, clock_s=176.9)]
    with pytest.raises(ValueError, match='duplicate'):
        protocol.opportunity_roster(frames, decisions + decisions[:1])
    decisions[0]['poll'] = 105
    with pytest.raises(ValueError, match='off-cadence'):
        protocol.opportunity_roster(frames, decisions)


def test_pre_row_driver_contradiction_keeps_failed_and_not_reached_opportunities(planned_inputs):
    frames, decisions = planned_inputs
    roster = protocol.opportunity_roster(frames, decisions.values())  # Before any replay.
    output = []
    facade = live.RecordedFacade({'A': StubShadow(100), 'B': StubShadow(2304)},
                                decisions, {7, 8, 9}, output.append)
    facade.frame, facade.expected_poll = dict(frames[0], towers=towers()), 100
    facade.act(fixture_view(100))
    facade.frame, facade.expected_poll = dict(frames[1], towers=towers()), 110
    view = fixture_view(110)
    view.info.own['hand'][0] = 'Giant'  # Real driver's pre-row contradiction path.
    with pytest.raises(ValueError, match='command context diverged') as caught:
        facade.act(view)
    fatal = dict(n=2, tick=110, error=repr(caught.value))
    report = protocol.summary(facade.rows, facade.evidence(), {}, roster, fatal)
    assert (report['expected'], report['attempted'], report['successful'], report['failed'], report['unvisited']) == (3, 2, 1, 1, 1)
    assert [r['status'] for r in report['opportunity_statuses']] == ['success', 'error', 'not_reached']
    failed, unvisited = report['opportunity_statuses'][1:]
    assert failed['error'] == fatal and failed['n'] == 2 and unvisited['n'] == 3
    assert 'arms' not in failed and 'arms' not in unvisited  # Never fabricate decisions/public states.
    assert len(facade.rows) == len(output) == 1  # Original complete prefix is preserved intact.
    assert not report['pass_checks'] and not report['checks']['matched_all_opportunities']


def test_fatal_post_row_queue_contradiction_invalidates_apparent_success():
    facade, rows = fixture_facade()
    facade.act(fixture_view())
    original = protocol.digest(rows)
    fatal = dict(n=1, tick=100, error='unverified reservation replacement contradiction')
    report = protocol.summary(rows, facade.evidence(), {}, ONE_OPPORTUNITY, fatal)
    assert report['expected'] == report['attempted'] == report['failed'] == 1
    assert report['successful'] == report['matched'] == report['unvisited'] == 0
    assert not report['checks']['matched_all_opportunities'] and not report['pass_checks']
    assert protocol.digest(rows) == original
