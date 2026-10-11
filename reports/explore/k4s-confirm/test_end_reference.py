"""PREREG-K4S END reference/pool tests (no torch, no native, no corpus, no network, no outcomes).

The fleet fixture is producer-shaped: common/host pins come from the real ``end_reference.frozen_identity`` for two
hosts with different (host-naming) bundles, every receipt is written through ``end_reference.run_attempt`` after a
real ``end_evidence.producer_claim`` under a committed END-JOB (each scenario in its own clone of the evidence
repository), the registry and the round's finalization record are committed, and the committed supervisor exits
carry the counted descriptors verbatim. Only the native/corpus binaries and the TIERS bundle validation are stand-ins.
"""
import copy
import json
import math
import shutil
import subprocess
import sys
from argparse import Namespace
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'mac'), str(HERE)]
import end_pool as P  # noqa: E402
import end_evidence as E  # noqa: E402
import end_reference as R  # noqa: E402
import k4s_logic as L  # noqa: E402
import build_manifest as B  # noqa: E402
import measure_k4s as M  # noqa: E402
import schedule  # noqa: E402  (K4S block descriptors, read only)
from end_reference import CELLS, Timed, charge_scale, measure, raw_record, k4s_pins, frozen_identity  # noqa: E402
from end_pool import pool  # noqa: E402

E4V3 = L.REPO_ROOT / L.E4V3_REL
INVENTORY = L.REPO_ROOT / 'reports/explore/t1/corpora/corpus-03-a51ea64c/corpora.json'
IDS = L.check_corpus(L.T1_K4_CORPUS_SHA, L.T1_K4_CORPUS_SHA, json.loads(INVENTORY.read_text()), None, None)
KERNEL, SCORER = 'reports/explore/k4s-confirm/sdefault.py', 'reports/explore/k4s-confirm/anchor_x.py'
SHARED = dict(bundle_runtime_files_sha256='2' * 64, bundle_measurement_files_sha256='3' * 64,
              bundle_model_files={'v1.pt': '4' * 64, 'R3a.pt': L.SD1_CHECKPOINT_SHA,
                                  'R3a-calibration.json': L.SD1_CALIBRATION_SHA, 'states.pkl': '5' * 64})
_BUILT = {}


def built_manifest():
    if 'm' not in _BUILT:
        _BUILT['m'] = B.build(L.REPO_ROOT, [KERNEL, SCORER], True)
    return copy.deepcopy(_BUILT['m'])


def frozen_e4v3():
    if str(E4V3) not in sys.path:
        sys.path.insert(0, str(E4V3))
    import fleet_pool
    import fleet_validity
    import fleet_profile
    import fleet_end
    return fleet_pool, fleet_validity, fleet_profile, fleet_end


def pins(**over):
    """Synthetic common pins (frozen keys from a frozen build of this worktree + shared bundle pins)."""
    base = dict(L.end_frozen_pins(built_manifest(), '1' * 64, KERNEL, SCORER), **copy.deepcopy(SHARED))
    base.update(over)
    return base


def own(host):
    return dict(bundle_manifest_sha256=L.sha_bytes(host.encode()), bundle_profile_host=host)


def raw(host, factor=1.0, ids=None, slow=(), slow_factor=2.0, cutoff=lambda i, r: r == 0, common=None, host_pins=None):
    """A conforming raw END record: 3 timings per state, every (cell, state, repeat) once."""
    ids = list(IDS if ids is None else ids)
    states = {}
    for i in ids:
        f = factor * (slow_factor if i in slow else 1.)
        states[i] = dict(k4_wall=[.1 * f] * 3, k4s_wall=[.1 * f * (1 + k / 100) for k in range(3)], sd1_poll=[.004] * 3,
                         v1_poll=[.005] * 3, result=dict(action=1, candidates=[1, 2304], scores=[.5, .4]))
    deadline = {cell: dict(budget_ms=b, charge_scale=L.charge_scale_text(cell), rows=[
        dict(id=i, repeat=r, cutoff=cutoff(i, r), no_complete_play=False, fallback=False, wall_seconds=.15,
             poll_seconds=.004, scale_sleep_seconds=0.) for i in ids for r in range(3)]) for cell, b in L.BUDGET_MS.items()}
    return dict(schema=P.RAW_SCHEMA, host=host, corpus_sha256=L.T1_K4_CORPUS_SHA, repeats=3,
                pins=pins() if common is None else common, host_pins=own(host) if host_pins is None else host_pins,
                states=states, deadline=deadline)


# ---------------------------------------------------------------- charge and timing wrapper

def test_charge_scale_strings():
    assert [charge_scale(c) for c, _ in CELLS] == ['1', '10/9', '5/4', '10/7', '5/3']
    assert [L.charge_scale_text(c) for c in L.BUDGET_MS] == ['1', '10/9', '5/4', '10/7', '5/3']
    assert [b for _, b in CELLS] == [200, 180, 160, 140, 120]


def test_timed_records_pure_poll_and_charges_inside():
    now = [0.]

    class Policy:
        def sample(self, *a): now[0] += .010; return 7
        def propose(self, *a): return 'p'

    def sleep(x): now[0] += x
    t = Timed(Policy(), sleep=sleep, clock=lambda: now[0])
    assert t.sample() == 7 and t.last_poll == pytest.approx(.010) and t.last_sleep == 0. and t.propose() == 'p'
    t.scale = Fraction(5, 3); t.sample()
    assert t.last_poll == pytest.approx(.010) and t.last_sleep == pytest.approx(.010*2/3)
    assert t.last_sleep/(t.last_poll+t.last_sleep) == pytest.approx(1-3/5)


# ---------------------------------------------------------------- pool validation

def test_pool_conforms_and_counts():
    ids = IDS[:6]
    out = pool([raw('127x01', 1.0, ids), raw('127x03', 1.02, ids)], ids)
    assert out['pool_conforms'] and out['hosts'] == ['127x01', '127x03']
    cell = out['deadline']['0.8']
    assert (cell['n'], cell['cutoff_count'], cell['cutoff'], cell['charge_scale'], cell['budget_ms']) == (36, 12, 1/3, '5/4', 160)
    assert out['deadline']['0.6']['charge_scale'] == '5/3' and set(out['deadline']) == set(L.BUDGET_MS)


def test_pool_fails_closed_outside_window():
    ids = IDS[:6]
    out = pool([raw('127x01', 1.0, ids), raw('127x03', 1.2, ids)], ids)
    assert not out['pool_conforms'] and out['host_ratio_to_pool']['127x03'] < .95 < 1.05 < out['host_ratio_to_pool']['127x01']


def mutate(fn, ids=None):
    ids = IDS[:6] if ids is None else ids
    bad = raw('127x03', 1.0, ids)
    fn(bad)
    return [raw('127x01', 1.0, ids), bad], ids


@pytest.mark.parametrize('case,message', [
    (lambda r: r['states'].pop(IDS[0]), 'inventory'),
    (lambda r: r['states'].update(extra=r['states'][IDS[0]]), 'inventory'),
    (lambda r: r['states'][IDS[1]].update(k4s_wall=[.1]), 'Exactly three'),
    (lambda r: r['states'][IDS[1]].update(sd1_poll=[.1, .1, .1, .1]), 'Exactly three'),
    (lambda r: r['states'][IDS[1]].update(k4_wall=[.1, float('nan'), .1]), 'Invalid'),
    (lambda r: r['states'][IDS[1]].update(v1_poll=[.1, 0., .1]), 'Invalid'),
    (lambda r: r['states'][IDS[1]].update(k4s_wall=[.1, True, .1]), 'Invalid'),
    (lambda r: r['states'][IDS[2]].update(result=dict(action=2, candidates=[2], scores=[1.])), 'Exactness mismatch'),
    (lambda r: r['deadline']['0.9']['rows'].append(dict(r['deadline']['0.9']['rows'][0])), 'Duplicate'),
    (lambda r: r['deadline']['0.9']['rows'].pop(), 'exactly once'),
    (lambda r: r['deadline']['0.9']['rows'][0].update(repeat=3), 'repeat'),
    (lambda r: r['deadline']['0.9']['rows'][0].update(cutoff=1), 'Boolean'),
    (lambda r: r['deadline']['0.9']['rows'][0].update(id='unknown'), 'Unknown deadline state'),
    (lambda r: r['deadline']['0.9']['rows'][0].update(wall_seconds=-1.), 'Invalid deadline timing'),
    (lambda r: r['deadline']['0.9'].update(budget_ms=999), 'budget'),
    (lambda r: r['deadline']['0.9'].update(charge_scale='1'), 'charge'),
    (lambda r: r['deadline'].pop('0.6'), 'five cells'),
    (lambda r: r.update(repeats=1), '3 repeats'),
    (lambda r: r.update(pins=pins(kernel_sha256='0' * 64)), 'common pins'),
    (lambda r: r['pins']['bundle_model_files'].update(**{'states.pkl': '6' * 64}), 'common pins'),
    (lambda r: r.update(host_pins=own('127x01')), 'per-host'),
    (lambda r: r.update(host='127x01'), 'One raw END record per host|per-host'),
])
def test_pool_validation_negatives(case, message):
    raws, ids = mutate(case)
    with pytest.raises(P.PoolError, match=message):
        pool(raws, ids)


def test_reviewer_counterexample_one_timing_duplicate_rows_bad_budget_is_rejected():
    ids = IDS[:6]
    bad = raw('127x03', 1.0, ids)
    for state in bad['states'].values():
        state.update(k4s_wall=state['k4s_wall'][:1])
    with pytest.raises(P.PoolError):
        pool([raw('127x01', 1.0, ids), bad], ids)
    bad = raw('127x03', 1.0, ids)
    rows = bad['deadline']['0.8']['rows']
    rows[:] = [dict(rows[0]) for _ in rows]           # one (id, repeat) row repeated, all others absent
    with pytest.raises(P.PoolError, match='Duplicate'):
        pool([raw('127x01', 1.0, ids), bad], ids)


def test_pool_checks_survive_python_optimisation():
    code = ('import sys, json; sys.path.insert(0, %r); import end_pool as P, test_end_reference as T; '
            'r = T.raw("h2", 1.0, T.IDS[:6]); r["states"][T.IDS[0]]["k4s_wall"] = [.1]\n'
            'try:\n    P.pool([T.raw("h1", 1.0, T.IDS[:6]), r], T.IDS[:6])\nexcept P.PoolError:\n    print("refused")\n')
    out = subprocess.run([sys.executable, '-O', '-B', '-c', code % str(HERE)], capture_output=True, text=True, cwd=HERE, check=True)
    assert out.stdout.strip() == 'refused'


# ---------------------------------------------------------------- host ratio statistic and inclusive window

def test_host_ratio_is_frozen_geometric_pooled_over_host():
    fleet_pool = frozen_e4v3()[0]
    walls = {'h1': {i: [.1, .101, .102] for i in IDS}, 'h2': {i: [.11, .1, .105] for i in IDS}}
    pooled, ratios = P.host_ratios(walls)
    for host, w in walls.items():
        per_state = [pooled[k] / L.quantiles(w[k])['p50'] for k in sorted(w)]
        assert ratios[host] == fleet_pool.geometric(per_state) == P.geometric(per_state)
    assert ratios['h2'] < 1 < ratios['h1']           # slower host -> ratio below one (frozen direction)


def fleet_pool_hosts(walls):
    """The same K4S walls replicated on every frozen TIERS tier, as fleet_pool.pool_rows input."""
    fleet_pool = frozen_e4v3()[0]
    hosts = {}
    for host, w in walls.items():
        speed = [dict(tier=t, id=i, repeat=r, wall_seconds=w[i][r]) for t in fleet_pool.TIERS for i in w for r in range(3)]
        deadlines = [dict(tier=t, id=i, cell=c, repeat=r, deadline_seconds={'1.0': .2, '0.8': .16}[c], cutoff=False,
                          fallback=False, no_complete_play=False, over_200_ms=False, cut_return_over_208_ms=False,
                          wall_seconds=.1, selected_wait_ticks=None, completed=1, candidates=1)
                     for t in fleet_pool.TIERS for i in w for c in ('1.0', '0.8') for r in range(3)]
        hosts[host] = dict(speed=speed, deadlines=deadlines)
    return hosts


@pytest.mark.parametrize('slow_factor', [1.0, 1.04, 2.0])
def test_host_ratio_cross_checks_frozen_pool_rows(slow_factor):
    fleet_pool = frozen_e4v3()[0]
    slow = set(IDS[:100])
    walls = {'h1': {i: [.1, .101, .102] for i in IDS}, 'h3': {i: [.1, .1015, .103] for i in IDS},
             'h2': {i: [v * (slow_factor if i in slow else 1.) for v in (.1, .101, .102)] for i in IDS}}
    _, ratios = P.host_ratios(walls)
    frozen = fleet_pool.pool_rows(fleet_pool_hosts(walls), end_mode=False)
    for host in walls:
        assert ratios[host] == pytest.approx(frozen['initial_host_ratios'][host], rel=1e-12, abs=0)


def test_slow_subset_fails_where_a_median_statistic_would_pass():
    """Reviewer's case: twice as slow on 100 of 300 states, equal elsewhere."""
    ids = IDS
    out = pool([raw('a', 1.0, ids), raw('b', 1.0, ids, slow=set(ids[:100]))], ids)
    host_over_pool_median = L.quantiles([L.quantiles(r['states'][i]['k4s_wall'])['p50'] / out['states'][i]['k4s_wall_seconds']
                                         for r in (raw('b', 1.0, ids, slow=set(ids[:100])),) for i in ids])['p50']
    assert host_over_pool_median == pytest.approx(1.0)     # the old statistic would have passed
    expected = ((.102 + .2) / 2 / .202) ** (1 / 3)        # pooled slow-state median over host b's median
    assert out['host_ratio_to_pool']['b'] == pytest.approx(expected, rel=1e-12) and out['host_ratio_to_pool']['b'] < .95
    assert out['pool_conforms'] is False


def test_ratio_window_is_inclusive_at_both_bounds():
    assert P.within_window(.95) and P.within_window(1.05) and P.within_window(1.0)
    assert not P.within_window(math.nextafter(.95, 0)) and not P.within_window(math.nextafter(1.05, 2))
    with pytest.raises(L.GateInputError):
        P.within_window(float('nan'))
    # Inside the window the pool conforms; a host 20% slower takes both ratios outside and fails closed.
    for factor, conforms in ((1.0, True), (1.10, True), (1.2, False)):
        out = pool([raw('a', 1.0, IDS[:4]), raw('b', factor, IDS[:4])], IDS[:4])
        assert out['pool_conforms'] is conforms


def test_k4s_inclusive_window_differs_from_frozen_tiers_float_check_only_at_the_endpoint_doubles():
    """r3 §4.5 says inclusive; the frozen TIERS form ``abs(r-1) <= .05`` rejects the 0.95/1.05 doubles."""
    source = (E4V3 / 'fleet_pool.py').read_text()
    assert 'abs(r-1) <= .05' in source and 'abs(v-1) > .05' in source      # the frozen TIERS expression, verbatim

    def tiers(r):
        return abs(r - 1) <= .05
    for r in (.95, 1.05):
        assert P.within_window(r) is True and L.in_host_ratio_window(r) is True and tiers(r) is False
    for r in (math.nextafter(.95, 1), math.nextafter(1.05, 0), 1.0):
        assert P.within_window(r) and tiers(r)
    for r in (math.nextafter(.95, 0), math.nextafter(1.05, 2)):
        assert not P.within_window(r) and not tiers(r)


# ---------------------------------------------------------------- producer loop with a fake backend

class FakeBackend:
    def __init__(self, ids, mismatch=None):
        self.k4s_rows = {i: dict(id=i) for i in ids}
        self.mismatch = mismatch
        now = [0.]

        def clock():
            now[0] += .001
            return now[0]
        self.sd1, self.v1 = (Timed(self.Policy(), sleep=lambda x: None, clock=clock) for _ in range(2))
        self.prepared = []

    class Policy:
        def sample(self, *a):
            return 1

    def work(self, row, tier):
        self.v1.sample()
        return dict(action=1, candidates=[1], scores=[.5]), dict(wall_seconds=.1)

    def k4s_work(self, row, deadline=None, packet_entry=None):
        self.sd1.sample()
        action = 9 if row['id'] == self.mismatch else 1
        return dict(action=action, candidates=[1], scores=[.5]), dict(
            wall_seconds=.11, cutoff=deadline is not None and deadline < .15, no_complete_play=False, fallback=False)

    def prepare_work(self, row):
        self.prepared.append(row['id'])


def test_measure_loop_writes_a_poolable_raw_with_guarded_blocks():
    ids, blocks, phases = IDS, [], []

    @contextmanager
    def guarded(identity):
        blocks.append(identity)
        yield
    be = FakeBackend(ids)
    states, deadline = measure(be, ids, guarded, phases.append, lambda: None)
    record = raw_record('a', pins(), own('a'), states, deadline)
    P.validate_raw(record, ids)
    assert set(blocks) == P.expected_blocks(ids) and len(blocks) == len(set(blocks))
    assert phases == ['reference-speed', 'reference-deadlines'] * 3
    assert sum(r['cutoff'] for r in deadline['0.6']['rows']) == 900 and not any(r['cutoff'] for r in deadline['0.9']['rows'])
    assert len(be.prepared) == 5 * 3 * 300 and be.sd1.scale == 1
    with pytest.raises(ValueError, match='Exactness mismatch'):
        measure(FakeBackend(ids, mismatch=ids[7]), ids, guarded, phases.append, lambda: None)


# ---------------------------------------------------------------- frozen identity (findings 5, 11, 15)

def runtime_with_network(tmp_path):
    """A runtime root mirroring this worktree plus the (untracked) SD1 network.py source."""
    root = tmp_path / 'runtime'
    manifest = built_manifest()
    pinned = [*manifest['k4s_files'], *manifest['end_files'], *manifest['reused_readonly'], *manifest['k4s_kernel']['files'],
              *L.SD1_SOURCES[:-1]]
    for rel in pinned:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((L.REPO_ROOT / rel).read_bytes())
    network = root / 'student-source/exit_r3/network.py'
    network.parent.mkdir(parents=True)
    network.write_text('# synthetic network source for an offline pin test\n')
    sd1 = json.loads((HERE / 'SD1-MANIFEST.json').read_text())
    sd1['inference_sources']['student-source/exit_r3/network.py'] = L.sha(network)
    sd1_path = tmp_path / 'SD1-MANIFEST.json'
    sd1_path.write_text(json.dumps(sd1, indent=2) + '\n')
    manifest['sd1_manifest']['sha256'] = L.sha(sd1_path)
    manifest_path = tmp_path / 'K4S-MAC-MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return root, sd1_path, manifest_path, manifest


def bundle_manifest(host, states='7' * 64):
    return dict(schema='clasher.e4v3.inputs.v1', profile='fleet-reference',
                runtime_files={L.TIERS_SCORER_REL: L.sha(L.REPO_ROOT / L.TIERS_SCORER_REL)},
                measurement_files={'fleet_end.py': L.sha(E4V3 / 'fleet_end.py')},
                files={'v1.pt': '8' * 64, 'R3a.pt': L.SD1_CHECKPOINT_SHA, 'R3a-calibration.json': L.SD1_CALIBRATION_SHA,
                       'states.pkl': states, 'plan.json': '9' * 64, 'end-evidence.json': '9' * 64},
                reference_load_profile=dict(PROFILE, host=host, plan='plan.json', end_evidence='end-evidence.json'))


def producer_args(tmp_path, host, runtime, sd1_path, manifest_path, **bundle_over):
    bundle = tmp_path / ('bundle-' + host)
    bundle.mkdir()
    (bundle / 'tiers-pins.json').write_text(json.dumps(bundle_manifest(host, **bundle_over), sort_keys=True))
    native, corpus = tmp_path / 'native-stand-in.so', tmp_path / 'K4-states-stand-in.pkl'
    return Namespace(bundle=bundle, runtime_root=runtime, native=native, corpus=corpus, corpus_sha256=L.T1_K4_CORPUS_SHA,
                     k4s_manifest=manifest_path, k4s_manifest_sha256=L.sha(manifest_path), kernel=KERNEL, scorer=SCORER,
                     sd1_manifest=sd1_path, sd1_manifest_sha256=L.sha(sd1_path))


def stand_in_digest(a):
    """Only the two large binaries are stand-ins; every other pin is hashed for real."""
    def digest(path):
        return {str(a.native): L.NATIVE_PROVENANCE_SHA, str(a.corpus): L.T1_K4_CORPUS_SHA}.get(str(path)) or L.sha(path)
    return digest


def read_bundle(bundle, root, **kw):
    return json.loads((Path(bundle) / 'tiers-pins.json').read_text())


def test_k4s_pins_bind_kernel_scorer_sd1_and_sources_before_any_backend(tmp_path):
    root, sd1_path, manifest_path, manifest = runtime_with_network(tmp_path)
    bundle = dict(profile='fleet-reference', runtime_files={L.TIERS_SCORER_REL: L.sha(L.REPO_ROOT / L.TIERS_SCORER_REL)},
                  files={'R3a.pt': L.SD1_CHECKPOINT_SHA, 'R3a-calibration.json': L.SD1_CALIBRATION_SHA})
    a = Namespace(runtime_root=root, k4s_manifest=manifest_path, k4s_manifest_sha256=L.sha(manifest_path),
                  kernel=KERNEL, scorer=SCORER, sd1_manifest=sd1_path, sd1_manifest_sha256=L.sha(sd1_path))
    got = k4s_pins(a, bundle)
    assert got == L.end_frozen_pins(manifest, L.sha(manifest_path), KERNEL, SCORER)
    assert set(got) == set(L.END_FROZEN_PIN_KEYS) and got['sd1_manifest_sha256'] == L.sha(sd1_path)
    assert set(got['measurement_files']) == set(L.END_MEASUREMENT_FILES)
    assert got['measurement_files']['reports/explore/k4s-confirm/end_background.py'] == L.sha(HERE / 'end_background.py')
    with pytest.raises(P.PoolError, match='TIERS-qualified scorer'):
        k4s_pins(a, dict(bundle, runtime_files={L.TIERS_SCORER_REL: '0' * 64}))
    with pytest.raises(L.PreconditionRefusal, match="SD1's bytes"):
        k4s_pins(a, dict(bundle, files=dict(bundle['files'], **{'R3a.pt': '0' * 64})))
    with pytest.raises(P.PoolError, match='SD1 manifest differs'):
        k4s_pins(Namespace(**dict(vars(a), sd1_manifest=HERE / 'SD1-MANIFEST.json',
                                  sd1_manifest_sha256=L.sha(HERE / 'SD1-MANIFEST.json'))), bundle)
    draft = tmp_path / 'draft.json'
    draft.write_text(json.dumps(dict(manifest, frozen=False)))
    with pytest.raises(L.PreconditionRefusal, match='frozen'):
        k4s_pins(Namespace(**dict(vars(a), k4s_manifest=draft, k4s_manifest_sha256=L.sha(draft))), bundle)
    forged = tmp_path / 'forged.json'
    forged.write_text(json.dumps(dict(manifest, k4s_kernel=dict(manifest['k4s_kernel'], files={KERNEL: '0' * 64, SCORER: pins()['scorer_sha256']}))))
    with pytest.raises(L.PreconditionRefusal, match='Pin mismatch'):
        k4s_pins(Namespace(**dict(vars(a), k4s_manifest=forged, k4s_manifest_sha256=L.sha(forged))), bundle)
    # A changed END source under the runtime root is refused (the manifest load catches it first).
    (root / 'reports/explore/k4s-confirm/end_background.py').write_text('# changed\n')
    with pytest.raises(L.PreconditionRefusal, match='Pin mismatch'):
        k4s_pins(a, bundle)


def test_executing_sources_must_equal_the_frozen_source_pins():
    sources = L.end_frozen_pins(built_manifest(), '1' * 64, KERNEL, SCORER)['measurement_files']
    assert R.executing_sources(sources) is True
    with pytest.raises(P.PoolError, match='Executing END source differs'):
        R.executing_sources(dict(sources, **{'reports/explore/k4s-confirm/end_evidence.py': '0' * 64}))
    with pytest.raises(P.PoolError, match='inventory differs'):
        R.executing_sources({k: v for k, v in sources.items() if not k.endswith('end_background.py')})


def test_frozen_identity_validates_bundle_and_native_before_anything_else(tmp_path):
    calls = []

    def refuse(bundle, root, **kw):
        calls.append(kw)
        raise ValueError('Pin mismatch: states.pkl')
    native = tmp_path / 'native.so'
    native.write_bytes(b'not the qualified native')
    a = Namespace(bundle=tmp_path, runtime_root=tmp_path, native=native, corpus=native, corpus_sha256=L.T1_K4_CORPUS_SHA)
    with pytest.raises(ValueError, match='states.pkl'):
        frozen_identity(a, refuse, L.NATIVE_PROVENANCE_SHA)
    assert calls == [dict(dry_run=True, require_references=False)]
    with pytest.raises(P.PoolError, match='fleet-reference'):
        frozen_identity(a, lambda *x, **k: dict(profile='mac-preregistered'), L.NATIVE_PROVENANCE_SHA)
    with pytest.raises(P.PoolError, match='Unqualified native'):
        frozen_identity(a, lambda *x, **k: dict(profile='fleet-reference'), L.NATIVE_PROVENANCE_SHA)


def test_frozen_identity_splits_common_pins_from_per_host_bundle_receipts(tmp_path):
    """Finding 11: genuine per-host bundles (each names its own host) give different bundle SHAs but equal
    common pins; the frozen subset equals the frozen K4S manifest's values."""
    runtime, sd1_path, manifest_path, manifest = runtime_with_network(tmp_path)
    out = {}
    for host in ('a', 'b'):
        a = producer_args(tmp_path, host, runtime, sd1_path, manifest_path)
        _, common, host_pins = frozen_identity(a, read_bundle, L.NATIVE_PROVENANCE_SHA, digest=stand_in_digest(a))
        out[host] = (common, host_pins)
    assert out['a'][0] == out['b'][0] and out['a'][1] != out['b'][1]
    assert out['a'][1]['bundle_profile_host'] == 'a' and out['b'][1]['bundle_manifest_sha256'] == L.sha(tmp_path / 'bundle-b/tiers-pins.json')
    assert L.check_end_pins(out['a'][0], L.end_frozen_pins(manifest, L.sha(manifest_path), KERNEL, SCORER), 'x')
    (tmp_path / 'other').mkdir()
    other = producer_args(tmp_path / 'other', 'a', runtime, sd1_path, manifest_path, states='6' * 64)
    _, changed, _ = frozen_identity(other, read_bundle, L.NATIVE_PROVENANCE_SHA, digest=stand_in_digest(other))
    assert changed != out['a'][0] and changed['bundle_model_files']['states.pkl'] == '6' * 64


# ---------------------------------------------------------------- committed END evidence fixture

PLAN = dict(study='PREREG-K4S', compute=dict(hosts={h: dict(physical_cpus=list(range(10)), census_cpu=10) for h in ('a', 'b')},
            nice=10, scheduler='SCHED_OTHER', slots=2, console_slots=2, slot_width=5, smt=False, forbidden_hosts=[]))
PROFILE = dict(reference_slot=0, slot_count=2, console_rule=False, warmup_seconds=300, perception='none')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def commit_all(repo, paths, message):
    git(repo, 'add', '--', *paths)
    git(repo, '-c', 'user.name=K4S fixture', '-c', 'user.email=k4s-fixture@example.invalid', 'commit', '-q', '-m', message)
    return git(repo, 'rev-parse', 'HEAD')


def block_descriptor(population, index, host, dispatch):
    """The real K4S schedule.block descriptor (rotation/subsample/replacement_k included) + host/dispatch."""
    return dict(schedule.block(population, index), host=host, dispatch=dispatch)


def dump(value):
    return ('\n'.join(json.dumps(v) for v in value) + '\n') if isinstance(value, list) else json.dumps(value)


def committed_evidence(base, hosts=('a', 'b'), mhz=2000., loss=False, change=None, counted=(3000, 900)):
    """Committed K4S END evidence. ``loss``: primary-0007 fails on its host (blind ledger loss) and its replacement
    primary-3007 completes on host a in phase replacement-r1. ``change(sources)`` tampers before commit."""
    repo = base / 'repo'
    repo.mkdir()
    phases_by_host = {h: ['reporting'] for h in hosts}
    exits = {(h, 'reporting'): dict(completed=[], failed=[], unstarted=[]) for h in hosts}
    rows, events, n = [], [], 0
    for population, count in (('primary', 3000), ('guard', 900)):
        for index in range(count):
            host = hosts[n % len(hosts)]
            d = block_descriptor(population, index, host, n)
            n += 1
            if loss and d['id'] == 'primary-0007':
                exits[(host, 'reporting')]['failed'].append(d)
                events.append(dict(utc='2026-10-13T12:00:00Z', lost=copy.deepcopy(d), reason='crash',
                                   evidence_sha256=(host, 'reporting')))
                continue
            exits[(host, 'reporting')]['completed'].append(d)
            rows.append(dict(host=host, phase='reporting', descriptor=copy.deepcopy(d)))
    if loss:
        bank = schedule.block('primary', 3007, cell=7, replaces='primary-0007', logical=7, replacement_k=0)
        events[0]['replacement'] = bank
        ran = dict(bank, host='a', dispatch=0)
        phases_by_host['a'].append('replacement-r1')
        exits[('a', 'replacement-r1')] = dict(completed=[ran], failed=[], unstarted=[])
        rows.append(dict(host='a', phase='replacement-r1', descriptor=copy.deepcopy(ran)))
    sources = {'plan.json': PLAN, 'blind-ledger.json': dict(utc='2026-10-14T00:30:00Z', sealed=True, events=events),
               'counted-inventory.json': dict(schema='clasher.t1.counted-blocks.v1', outcomes_sealed=True, blocks=rows)}
    names = {}
    for (host, phase), exit_ in exits.items():
        values = dict(launch=dict(host=host, phase='replacement' if phase != 'reporting' else 'reporting', slots=2,
                                  utc='2026-10-13T00:00:00Z'),
                      supervisor_exit=dict(host=host, reason=None, utc='2026-10-14T00:59:00Z', **exit_),
                      mhz=[dict(utc=f'{phase}-{i}', slots=2, physical_core_mhz=[dict(cpu=c, mhz=mhz) for c in range(10)])
                           for i in range(3)],
                      census=[dict(host=host, utc=f'{phase}-{i}', inflight=2, reason=None) for i in range(3)])
        for key, value in values.items():
            name = f'{host}-{phase}-{key}' + ('.jsonl' if isinstance(value, list) else '.json')
            sources[name] = value
            names[(host, phase, key)] = name
    if change is not None:
        change(sources)
    for event in sources['blind-ledger.json']['events']:
        if isinstance(event.get('evidence_sha256'), tuple):
            event['evidence_sha256'] = L.sha_bytes(dump(sources[names[(*event['evidence_sha256'], 'supervisor_exit')]]).encode())
    completion = dict(reporting_complete=True, outcomes_sealed=True, counted_primary_blocks=counted[0], counted_guard_blocks=counted[1],
                      completed_at_utc='2026-10-14T01:00:00Z', counted_host_phases=phases_by_host,
                      blind_ledger_sha256=L.sha_bytes(dump(sources['blind-ledger.json']).encode()),
                      counted_inventory_sha256=L.sha_bytes(dump(sources['counted-inventory.json']).encode()))
    sources['completion.json'] = completion
    for name, value in sources.items():
        (repo / name).write_text(dump(value))
    git(repo, 'init', '-q')
    commit = commit_all(repo, list(sources), 'END fixture')

    def item(name):
        return dict(path=name, repository_path=name, commit=commit, sha256=L.sha(repo / name))
    phases = [dict(host=h, phase=p, **{k: item(names[(h, p, k)]) for k in ('launch', 'supervisor_exit', 'mhz', 'census')})
              for (h, p) in exits]
    evidence = dict(schema=E.EVIDENCE_SCHEMA, kind='counted-reporting', plan=item('plan.json'), completion=item('completion.json'),
                    blind_ledger=item('blind-ledger.json'), counted_inventory=item('counted-inventory.json'), phases=phases)
    path = repo / 'end-evidence.json'
    path.write_text(json.dumps(evidence))
    return repo, path


def test_end_evidence_binds_committed_completion_and_host_set(tmp_path):
    fleet_end = frozen_e4v3()[3]
    repo, evidence_path = committed_evidence(tmp_path)
    e = E.end_evidence(evidence_path, L.sha(evidence_path), repo, fleet_end)
    assert e['counted_hosts'] == ['a', 'b'] and e['membership'] == dict(blocks=3900, losses=0,
                                                                         host_phases=[('a', 'reporting'), ('b', 'reporting')])
    completion = json.loads((repo / 'completion.json').read_text())
    completion['counted_host_phases'].pop('b')            # uncommitted local edit, evidence re-pointed
    (repo / 'completion.json').write_text(json.dumps(completion))
    evidence = json.loads(evidence_path.read_text())
    evidence['completion']['sha256'] = L.sha(repo / 'completion.json')
    forged = repo / 'forged-evidence.json'
    forged.write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match='committed'):
        E.end_evidence(forged, L.sha(forged), repo, fleet_end)
    git(repo, 'checkout', '-q', '--', 'completion.json')
    evidence = json.loads(evidence_path.read_text())
    evidence['phases'].pop()
    forged.write_text(json.dumps(evidence))
    with pytest.raises(P.PoolError, match='Missing counted'):
        E.end_evidence(forged, L.sha(forged), repo, fleet_end)
    with pytest.raises(P.PoolError, match='SHA mismatch'):
        E.end_evidence(evidence_path, '0' * 64, repo, fleet_end)


def test_ledger_loss_and_replacement_reconcile_with_verbatim_exits(tmp_path):
    repo, path = committed_evidence(tmp_path, loss=True)
    e = E.end_evidence(path, L.sha(path), repo, frozen_e4v3()[3])
    assert e['membership'] == dict(blocks=3900, losses=1, host_phases=[('a', 'replacement-r1'), ('a', 'reporting'),
                                                                       ('b', 'reporting')])


def first_counted(sources, host='a'):
    return sources[f'{host}-reporting-supervisor_exit.json']['completed'][0]


@pytest.mark.parametrize('loss,change,message', [
    # counted block absent from the raw supervisor exit (nonexistent/failed work cannot be counted)
    (False, lambda s: s['a-reporting-supervisor_exit.json']['completed'].pop(0), 'exact completed raw exit membership'),
    # counted descriptor differs from its raw exit descriptor (not verbatim)
    (False, lambda s: s['counted-inventory.json']['blocks'][0]['descriptor'].update(seed=1), 'exact completed raw exit'),
    # non-health field in a descriptor, the inventory and a ledger event
    (False, lambda s: [first_counted(s).update(winner='blue'), s['counted-inventory.json']['blocks'][0]['descriptor'].update(winner='blue')],
     'unknown/non-health'),
    (False, lambda s: s['counted-inventory.json'].update(wins=1), 'non-health'),
    (False, lambda s: s['counted-inventory.json']['blocks'][0].update(outcome='loss'), 'health-only membership rows'),
    (True, lambda s: s['blind-ledger.json']['events'][0].update(result='loss'), 'non-health blind ledger'),
    # the lost block is counted anyway
    (True, lambda s: s['counted-inventory.json']['blocks'].append(dict(host='b', phase='reporting',
                                                                     descriptor=s['blind-ledger.json']['events'][0]['lost'])),
     'lost block counted'),
    # failed block without a ledger loss
    (True, lambda s: s['blind-ledger.json'].update(events=[]), 'absent from blind ledger'),
    # ledger loss bound to the wrong exit evidence
    (True, lambda s: s['blind-ledger.json']['events'][0].update(evidence_sha256='0' * 64), 'verbatim raw exit binding'),
    # replacement changes cell / logical block
    (True, lambda s: s['blind-ledger.json']['events'][0]['replacement'].update(cell=8), 'Invalid blind ledger replacement'),
    (True, lambda s: s['blind-ledger.json']['events'][0]['replacement'].update(replaces='primary-0008'), 'logical block'),
    # launch phase identity and registered phase names
    (False, lambda s: s['a-reporting-launch.json'].update(phase='replacement'), 'host/launch mismatch'),
    (True, lambda s: s['a-replacement-r1-launch.json'].update(phase='reporting'), 'host/launch mismatch'),
    # K4S's registered descriptor fields are allowed only as extensions; T1's unknown ones still are not
    (False, lambda s: [first_counted(s).update(arm='K4S-200'), s['counted-inventory.json']['blocks'][0]['descriptor'].update(arm='K4S-200')],
     'unknown/non-health'),
])
def test_counting_port_rejects_unreconciled_membership(tmp_path, loss, change, message):
    repo, path = committed_evidence(tmp_path, loss=loss, change=change)
    with pytest.raises(P.PoolError, match=message):
        E.end_evidence(path, L.sha(path), repo, frozen_e4v3()[3])


def test_descriptor_allow_list_extends_frozen_only_by_registered_k4s_fields():
    import inspect
    frozen = inspect.getsource(frozen_e4v3()[3].counting)
    assert all(f'"{name}"' in frozen for name in E.FROZEN_DESCRIPTOR_FIELDS)
    assert E.DESCRIPTOR_FIELDS - E.FROZEN_DESCRIPTOR_FIELDS == {'rotation', 'subsample', 'replacement_k'}
    replacement = schedule.block('guard', 900 + 18 + 4, cell=4, replaces='guard-0004', logical=4, replacement_k=1)
    assert set(schedule.block('primary', 5)) | {'host', 'dispatch'} == set(replacement) | {'host', 'dispatch'} \
        == E.DESCRIPTOR_FIELDS


def test_unregistered_phase_name_is_refused(tmp_path):
    repo, path = committed_evidence(tmp_path)
    evidence = json.loads(path.read_text())
    evidence['phases'][0]['phase'] = 'reporting-2'
    forged = repo / 'forged.json'
    forged.write_text(json.dumps(evidence))
    with pytest.raises(P.PoolError, match='Duplicate/unknown END host phase'):
        E.end_evidence(forged, L.sha(forged), repo, frozen_e4v3()[3])


# ---------------------------------------------------------------- producer-shaped host receipts

def produce(fleet, ref, name, host, kind='good', *, utc=1000., factor=1.0, mhz=2000., mutate=lambda n, v: v,
            common=None, host_pins=None, claim=None):
    """One END attempt: a real producer claim under the committed END-JOB, then the producer's run_attempt lifecycle
    with fake work. ``claim(directory)`` overrides the claim (tests of claims outside the canonical registry)."""
    _, fleet_validity, fleet_profile, fleet_end = frozen_e4v3()
    directory = fleet.tmp / name
    claim, claim_sha = (claim or (lambda d: E.producer_claim(ref.repo, ref.job, ref.round, host, d, now=utc,
                                                             context=pool_context(fleet, ref) if ref.round else None)))(directory)
    store = L.K4SStore(directory, P.REFERENCE_SCOPE)
    profile = dict(PROFILE, host=host)
    search, background, census_cpu = fleet_profile.slot_layout(profile, PLAN, host, 10)
    common = fleet.identity[host][0] if common is None else common
    host_pins = fleet.identity[host][1] if host_pins is None else host_pins

    def write(n, value):
        store.write(n, mutate(n, value))

    def body():
        write('attempt-claim.json', dict(claim=claim, claim_sha256=claim_sha))
        write('end-identity.json', dict(host=host, utc=utc, nice=10, scheduler='SCHED_OTHER', end_kind='counted-reporting',
                                        end_evidence_sha256=fleet.evidence['sha256'], counted_hosts=fleet.evidence['counted_hosts'],
                                        plan_sha256=fleet.evidence['plan_sha256'], attempt=claim['attempt'],
                                        attempt_claim_sha256=claim_sha, end_job_sha256=ref.job['sha256'], round=ref.round,
                                        load_profile=profile, search_cpus=search,
                                        background_masks=background, census_cpu=census_cpu, pins=common, host_pins=host_pins))
        reporting = fleet_end.host_reporting(fleet.evidence, profile, PLAN)
        write('reporting-full-occupancy-mhz.json', dict(rows=reporting))
        if kind == 'crash':
            raise fleet_validity.FleetTechnicalError('crash', 'Reference telemetry/guard process stopped')
        if kind == 'exact':
            raise ValueError('Exactness mismatch: no-deadline K4S != K4 on state ' + IDS[0])
        write('slot-evidence.json', dict(reference_affinity=search, reference_nice=10, background_affinity=background,
                                         background_nice=[10] * len(background)))
        write('guard-admission.json', dict(event='admit', id='reference-admission', reporting_guard=guard()))
        census = [dict(phase=phase, utc=float(i), cpu_clock_mhz_by_processor={str(c): mhz for c in range(11)},
                       per_cpu_idle={str(c): 0. for c in range(11)}, reporting_guard=guard())
                  for i, phase in enumerate(('reference-speed', 'reference-speed', 'reference-deadlines', 'reference-deadlines'))]
        for row in census:
            store.append('capacity.jsonl', mutate('capacity.jsonl', row))
        ssh = dict(interfered=False, stop=False)
        for identity in ['warm-0-0'] + sorted(P.expected_blocks(IDS)):
            for event in ('begin', 'end'):
                g = guard(**({'completed_block': dict(id=identity, seconds=10., ssh_family=ssh)} if event == 'end' else {}))
                store.append('guard-blocks.jsonl', dict(id=identity, event=event, reporting_guard=g))
        write('reference-warmup.json', dict(seconds=301., reference_slot_work=40, all_background_slots=1, all_slots_active=True))
        write('reporting-mhz-comparison.json', fleet_profile.compare_mhz(reporting, json.loads(json.dumps(census)),
                                                                         search + sum(background, []), 2))
        write('end-raw.json', raw(host, factor, common=common, host_pins=host_pins))

    def cleanup():
        if kind == 'cleanup':
            raise RuntimeError('Reference census process had to be terminated')
    completion = mutate('end-complete.json', dict(completed=True, repeats=3, reporting_load_profile=True, poolable=True,
                                                  outcome_access=False, live_actions=False, host=host, utc=utc + 1,
                                                  final=False))
    try:
        status = R.run_attempt(store, body, cleanup, completion, technical=(fleet_validity.FleetTechnicalError,))
        assert kind == 'good' and status == 'complete'
    except (fleet_validity.FleetTechnicalError, ValueError, RuntimeError):
        assert kind != 'good'
    return directory, L.sha(directory / 'receipt-manifest.json')


def guard(**over):
    g = dict(passes=True, rules=frozen_e4v3()[1].GUARD_RULES, console=dict(positive=False), memavailable_bytes=64 * 2 ** 30,
             foreign_compute=[], foreign_active=[], ssh_family_sample=dict(stop=False, core_fraction=0.))
    g.update(over)
    return g


GOOD = {'a': [('good', {})], 'b': [('good', dict(factor=1.02))]}


ROOT = E.REGISTRY_ROOT


def job_dict(fleet, evidence=None, **over):
    evidence = fleet.evidence if evidence is None else evidence
    job = dict(schema=E.JOB_SCHEMA, study='PREREG-K4S', end_evidence_sha256=evidence['sha256'],
               completion_sha256=evidence['completion_sha256'], plan_sha256=evidence['plan_sha256'],
               k4s_manifest_sha256=fleet.manifest_sha, counted_hosts=evidence['counted_hosts'],
               declared_utc='2026-10-14T02:00:00Z', declared_by='coordinator')
    job.update(over)
    return job


def job_repo(fleet, name):
    """A clone of the committed evidence repository with the committed END-JOB at its fixed path (before any claim)."""
    repo = fleet.tmp / f'repo-{name}'
    git(fleet.tmp, 'clone', '-q', str(fleet.repo), str(repo))
    (repo / 'end-evidence.json').write_bytes(fleet.evidence_path.read_bytes())
    (repo / E.END_DIR).mkdir(parents=True)
    (repo / E.END_JOB_PATH).write_text(L.canonical(job_dict(fleet)) + '\n')
    commit_all(repo, [E.END_JOB_PATH], 'END job')
    sha = L.sha(repo / E.END_JOB_PATH)
    return Namespace(repo=repo, evidence_path=repo / 'end-evidence.json', round=0,
                     job=E.end_job(repo, fleet.evidence, sha, fleet.manifest_sha))


def finalize(ref, round_, prior=(), utc=10. ** 6, commit=True):
    """Commit END-FINAL-round-RR.json: every claim of rounds 0..RR at HEAD and every earlier pool round."""
    layout = E.registry_at(ref.repo, 'HEAD')
    claims = E._digests(E._claims(ref.repo, ref.job, 'HEAD', layout))
    final = dict(schema=E.FINAL_SCHEMA, job_sha256=ref.job['sha256'], round=round_, claims=claims,
                 prior_rounds=list(prior), finalized_utc=utc, finalized_by='coordinator')
    name = E.final_path(round_)
    (ref.repo / name).write_text(L.canonical(final) + '\n')
    if commit:
        commit_all(ref.repo, [name], f'END finalization round {round_}')
    ref.final_sha, ref.round = L.sha(ref.repo / name), round_
    return ref


def scenario(fleet, name, plan=GOOD, commit=True, ref=None, round_=0, final=True, prior=()):
    """plan: {host: [(kind, kwargs), ...]} in launch order -> descriptor host entries + END job/finalization ref."""
    ref = job_repo(fleet, name) if ref is None else ref
    ref.round = round_
    fleet.repos[name] = ref.repo
    hosts = []
    for host, attempts in plan.items():
        made = [produce(fleet, ref, f'{name}-r{round_}-{host}-{i}', host, kind, utc=1000. + 100 * round_ + i, **kw)
                for i, (kind, kw) in enumerate(attempts)]
        hosts.append((host, made))
    if commit:
        commit_all(ref.repo, [ROOT], f'{name} claims round {round_}')
        if final:
            finalize(ref, round_, prior)
    return hosts, ref


def descriptor(fleet, hosts, ref, name='pool-input.json', **over):
    d = dict(schema=P.POOL_INPUT_SCHEMA, pooled_by='pooler-agent',
             k4s_manifest=dict(path=str(fleet.manifest_path), sha256=fleet.manifest_sha),
             corpus_inventory=dict(path=str(INVENTORY), sha256=L.sha(INVENTORY)),
             end_evidence=dict(path=str(ref.evidence_path), sha256=L.sha(ref.evidence_path)), kernel_rel=KERNEL,
             scorer_rel=SCORER, end_job=dict(sha256=ref.job['sha256']),
             finalization=dict(sha256=getattr(ref, 'final_sha', '0' * 64)), round=ref.round,
             hosts=[dict(host=h, attempts=[dict(directory=str(d), manifest_sha256=s) for d, s in attempts]) for h, attempts in hosts])
    d.update(over)
    path = fleet.tmp / name
    path.write_text(json.dumps(d, indent=2))
    return path, L.sha(path)


@pytest.fixture
def fleet(tmp_path):
    helpers = frozen_e4v3()
    repo, evidence_path = committed_evidence(tmp_path)
    evidence = E.end_evidence(evidence_path, L.sha(evidence_path), repo, helpers[3])
    runtime, sd1_path, manifest_path, manifest = runtime_with_network(tmp_path)
    identity = {}
    for host in ('a', 'b'):
        a = producer_args(tmp_path, host, runtime, sd1_path, manifest_path)
        _, common, host_pins = frozen_identity(a, read_bundle, L.NATIVE_PROVENANCE_SHA, digest=stand_in_digest(a))
        identity[host] = (common, host_pins)
    sha = L.sha(manifest_path)
    return Namespace(tmp=tmp_path, repo=repo, evidence_path=evidence_path, evidence=evidence, manifest_path=manifest_path,
                     manifest_sha=sha, frozen=L.end_frozen_pins(manifest, sha, KERNEL, SCORER), identity=identity,
                     repos={})


def pool_context(fleet, ref):
    """The producer's shared-input pool context for a later round (end_reference.reference)."""
    return P.pool_context(P.shared_request(fleet.manifest_path, fleet.manifest_sha, INVENTORY, ref.evidence_path,
                                           L.sha(ref.evidence_path), KERNEL, SCORER), ref.repo)


def pool_dir(fleet, name='pool', plan=GOOD, hosts=None, ref=None, output=None):
    if hosts is None:
        hosts, ref = scenario(fleet, name, plan)
    path, digest = descriptor(fleet, hosts, ref, name + '-input.json')
    return path, digest, P.run_pool(path, digest, output or fleet.tmp / name, repository=ref.repo)


def test_pool_recheck_mac_and_gate_inputs_end_to_end(fleet):
    """Producer-shaped receipts (two hosts, different bundles) -> pool -> independent re-check -> Mac reader."""
    assert fleet.identity['a'][1] != fleet.identity['b'][1]           # genuinely different per-host bundle receipts
    path, digest, document = pool_dir(fleet)
    reference_file = fleet.tmp / 'pool' / 'end-reference.json'
    assert document['pool_conforms'] and document['reporting_load_profile'] is True and document['hosts'] == ['a', 'b']
    prov = document['provenance']
    assert prov['counted_hosts'] == ['a', 'b'] and prov['host_receipts']['a']['reference_to_reporting_mean'] == 1.0
    assert prov['completion_sha256'] == fleet.evidence['completion_sha256'] and prov['k4s_manifest_sha256'] == fleet.manifest_sha
    assert prov['host_receipts']['b']['host_pins'] == fleet.identity['b'][1] and document['pins'] == fleet.identity['a'][0]
    receipt = P.recheck(path, digest, fleet.tmp / 'pool', 'checker-agent', fleet.tmp / 'end-recheck.json',
                        repository=fleet.repos['pool'])
    assert receipt['reference_sha256'] == L.sha(reference_file)
    consumed = json.loads((fleet.tmp / 'pool' / 'pool-inputs.json').read_text())['consumed']
    assert set(consumed) <= set(receipt['input_files']) and all(receipt['input_files'][p] == d for p, d in consumed.items())
    for host in ('a', 'b'):
        assert str((fleet.tmp / f'pool-r0-{host}-0' / 'end-raw.json').resolve()) in consumed
    assert str((fleet.repos['pool'] / 'a-reporting-census.jsonl').resolve()) in consumed
    assert prov['end_job']['sha256'] == L.sha(fleet.repos['pool'] / E.END_JOB_PATH) and prov['round'] == 0
    assert receipt['end_job_sha256'] == prov['end_job']['sha256'] and receipt['finalization_sha256'] == prov['finalization']['sha256']
    ref = json.loads(reference_file.read_text())
    recheck = json.loads((fleet.tmp / 'end-recheck.json').read_text())
    kwargs = dict(dry_run=False, reference_sha256=L.sha(reference_file), recheck=recheck, expected_pins=fleet.frozen,
                  end_pool_sha256=L.sha(HERE / 'end_pool.py'))
    fleet_ref = L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, IDS, **kwargs)
    assert set(fleet_ref['cells']) == set(L.BUDGET_MS)
    for cell, values in fleet_ref['cells'].items():
        assert values['n'] == 1800 and all(type(values[k + '_count']) is int for k in L.DEADLINE_RATE_KEYS)
        assert values['cutoff_count'] == 600 and values['cutoff'] == 1 / 3
    mac = dict(n=300, cutoff=.1, cutoff_count=30, no_complete_play=0., no_complete_play_count=0)
    speed = dict(r=1.0, p10=.95)
    gate = M.gate_inputs(gate0=dict(passes=True, parts={}), speed=speed, poll=dict(r_inf=1., p99_seconds=.01),
                         perception=dict(fps=20., processed_fraction=1.), gc_result=dict(passes=True), mac_deadline=mac,
                         fleet_deadline=fleet_ref['cells'])
    assert set(gate['fleet_deadline']) == set(L.BUDGET_MS)
    assert L.map_cell(gate)['c_M_k4s'] == '0.9'
    # The re-check binds its inputs: an arbitrary SHA string or a self-check is not accepted.
    for mutation, message in ((dict(reference_sha256='e' * 64), 'reference_sha256'),
                              (dict(host_receipts=dict(recheck['host_receipts'], b='0' * 64)), 'host_receipts'),
                              (dict(pool_input_sha256='0' * 64), 'pool_input_sha256'),
                              (dict(checker_sha256='0' * 64), 'checker_sha256'),
                              (dict(checked_by='pooler-agent'), 'someone other'),
                              (dict(finalization_sha256='0' * 64), 'finalization_sha256'),
                              (dict(end_job_sha256='0' * 64), 'end_job_sha256'),
                              (dict(passes=False), 'passes')):
        with pytest.raises(L.PreconditionRefusal, match=message):
            L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, IDS, **dict(kwargs, recheck=dict(recheck, **mutation)))
    with pytest.raises(L.PreconditionRefusal, match='re-check'):
        L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, IDS, **dict(kwargs, recheck=None))
    # Finding 15 on the Mac side: the complete frozen identity, incl. the K4S manifest SHA and every END source.
    for over, message in ((dict(kernel_sha256='0' * 64), 'different kernel_sha256'),
                          (dict(k4s_manifest_sha256='0' * 64), 'different k4s_manifest_sha256'),
                          (dict(measurement_files=dict(fleet.frozen['measurement_files'],
                                                       **{'reports/explore/k4s-confirm/end_reference.py': '0' * 64})),
                           'different measurement_files')):
        with pytest.raises(L.PreconditionRefusal, match=message):
            L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, IDS, **dict(kwargs, expected_pins=dict(fleet.frozen, **over)))
    with pytest.raises(L.PreconditionRefusal, match='complete frozen identity'):
        L.check_fleet_reference(ref, L.T1_K4_CORPUS_SHA, IDS, **dict(kwargs, expected_pins={
            k: v for k, v in fleet.frozen.items() if k != 'measurement_files'}))
    for mutation, message in ((lambda r: r['provenance']['reporting_load_profile_evidence'].update(reporting_guard=False), 'reporting-load evidence'),
                              (lambda r: r['provenance'].pop('end_job'), 'END job'),
                              (lambda r: r['provenance'].update(round=1), 'END job'),
                              (lambda r: r.update(hosts=['a']), 'host'),
                              (lambda r: r['host_ratio_to_pool'].update(b=.94), 'outside'),
                              (lambda r: r['pins'].pop('bundle_model_files'), 'key set'),
                              (lambda r: r['provenance']['host_receipts']['a'].update(host_pins=fleet.identity['b'][1]), 'own bundle'),
                              (lambda r: r['deadline']['0.9'].update(n=900, cutoff_count=300, cutoff=1 / 3), 'every host x state')):
        forged = copy.deepcopy(ref)
        mutation(forged)
        with pytest.raises(L.PreconditionRefusal, match=message):
            L.check_fleet_reference(forged, L.T1_K4_CORPUS_SHA, IDS, **kwargs)


def test_mac_stage_inputs_expected_pins_are_the_complete_frozen_identity(fleet):
    manifest = json.loads(fleet.manifest_path.read_text())
    assert L.end_frozen_pins(manifest, fleet.manifest_sha, KERNEL, SCORER) == fleet.frozen
    assert set(fleet.frozen['measurement_files']) == set(L.END_MEASUREMENT_FILES)


def test_pool_refuses_receipts_measured_on_other_sources_or_manifest(fleet):
    """Finding 15 at pooling: raw K4S-manifest SHA / measurement-source pins must equal the descriptor's frozen ones."""
    for name, over in (('stale-manifest', dict(k4s_manifest_sha256='0' * 64)),
                       ('stale-source', dict(measurement_files=dict(fleet.frozen['measurement_files'],
                                                                    **{'reports/explore/k4s-confirm/end_reference.py': '0' * 64})))):
        common = dict(fleet.identity['b'][0], **over)
        hosts, ref = scenario(fleet, name, {'a': [('good', {})], 'b': [('good', dict(common=common))]})
        with pytest.raises(P.PoolError, match='different ' + next(iter(over))):
            pool_dir(fleet, name, hosts=hosts, ref=ref)
    common = dict(fleet.identity['b'][0], bundle_runtime_files_sha256='0' * 64)       # a shared pin differs across hosts
    hosts, ref = scenario(fleet, 'shared', {'a': [('good', {})], 'b': [('good', dict(common=common))]})
    with pytest.raises(P.PoolError, match='different common pins'):
        pool_dir(fleet, 'shared', hosts=hosts, ref=ref)
    hosts, ref = scenario(fleet, 'own', {'a': [('good', {})], 'b': [('good', dict(host_pins=fleet.identity['a'][1]))]})
    with pytest.raises(P.PoolError, match='own bundle/profile'):
        pool_dir(fleet, 'own', hosts=hosts, ref=ref)


def test_pool_refuses_omitted_host_bad_mhz_slots_and_unrepeatable_attempts(fleet):
    hosts, ref = scenario(fleet, 'one-host')
    with pytest.raises(P.PoolError, match='ALL committed counted hosts'):
        pool_dir(fleet, 'one-host', hosts=hosts[:1], ref=ref)
    cases = (
        ('reporting-mhz-comparison.json', 'reference_to_reporting_mean', 1.2, 'recompute'),
        ('reporting-full-occupancy-mhz.json', 'rows', [], 'reporting rows do not recompute'),
        ('slot-evidence.json', 'background_affinity', [[0, 1, 2, 3, 4]], 'background slot'),
        ('slot-evidence.json', 'reference_nice', 0, 'priority'),
        ('end-identity.json', 'nice', 0, 'priority|nice'),
        ('end-identity.json', 'counted_hosts', ['b'], 'counted-host'),
        ('end-identity.json', 'pins', pins(scorer_sha256='0' * 64), 'scorer_sha256'),
        ('reference-warmup.json', 'seconds', 10., 'warm'),
        ('end-complete.json', 'reporting_load_profile', False, 'Unqualified'),
    )
    for index, (target, field, value, message) in enumerate(cases):
        def change(n, v, target=target, field=field, value=value):
            return dict(v, **{field: value}) if n == target else v
        hosts, ref = scenario(fleet, f'case{index}', {'a': [('good', {})], 'b': [('good', dict(factor=1.02, mutate=change))]})
        with pytest.raises((P.PoolError, ValueError), match=message):
            pool_dir(fleet, f'case{index}', hosts=hosts, ref=ref)
    hosts, ref = scenario(fleet, 'slow-mhz', {'a': [('good', {})], 'b': [('good', dict(mhz=1500.))]})
    with pytest.raises(P.PoolError, match='MHz differs'):
        pool_dir(fleet, 'slow-mhz', hosts=hosts, ref=ref)
    flag = dict(mutate=lambda n, v: dict(v, reporting_guard=guard(passes=False, reason='console_user')) if n == 'capacity.jsonl' else v)
    hosts, ref = scenario(fleet, 'flagged', {'a': [('good', {})], 'b': [('good', flag)]})
    with pytest.raises((ValueError, RuntimeError), match='guard'):
        pool_dir(fleet, 'flagged', hosts=hosts, ref=ref)
    # All original attempts: a mechanically classified technical crash may be repeated once ...
    _, _, document = pool_dir(fleet, 'repeat', {'a': [('good', {})], 'b': [('crash', {}), ('good', {})]})
    attempts = document['provenance']['host_receipts']['b']['attempts']
    assert [x['passes'] for x in attempts] == [False, True] and attempts[0]['technical_repeat_candidate'] is True
    assert document['provenance']['claims']['0']['b'] == [x['claim_sha256'] for x in attempts]
    # ... but an exactness failure never earns a repeat.
    with pytest.raises(P.PoolError, match='Unrepeatable'):
        pool_dir(fleet, 'exact', {'a': [('good', {})], 'b': [('exact', {}), ('good', {})]})


# ---------------------------------------------------------------- attempt registry (finding 14)

def test_registry_detects_an_omitted_exactness_failure_and_reordering(fleet):
    hosts, ref = scenario(fleet, 'omit', {'a': [('good', {})], 'b': [('exact', {}), ('good', {})]})
    b = dict(hosts)['b']
    with pytest.raises(P.PoolError, match='differ from the committed END attempt registry'):
        pool_dir(fleet, 'omit', hosts=[('a', dict(hosts)['a']), ('b', b[1:])], ref=ref)      # omits the exact attempt
    with pytest.raises(P.PoolError, match="registry's claim"):
        pool_dir(fleet, 'omit', hosts=[('a', dict(hosts)['a']), ('b', b[::-1])], ref=ref)     # reorders
    with pytest.raises(P.PoolError, match='Unrepeatable'):
        pool_dir(fleet, 'omit', hosts=hosts, ref=ref)                                         # complete list: refused


def test_registry_refuses_excess_technical_attempts(fleet):
    hosts, ref = scenario(fleet, 'excess', {'a': [('good', {})], 'b': [('crash', {}), ('crash', {}), ('good', {})]})
    with pytest.raises(P.PoolError, match='at most one repeat'):
        pool_dir(fleet, 'excess', hosts=hosts, ref=ref)
    b = dict(hosts)['b']
    with pytest.raises(P.PoolError, match='differ from the committed END attempt registry'):
        pool_dir(fleet, 'excess', hosts=[('a', dict(hosts)['a']), ('b', b[1:])], ref=ref)   # hides one crash


def test_registry_must_be_committed_finalized_and_contiguous(fleet, tmp_path):
    hosts, ref = scenario(fleet, 'late', commit=False)                     # claims never committed
    with pytest.raises(P.PoolError, match='END finalization record is not committed'):
        pool_dir(fleet, 'late', hosts=hosts, ref=ref)
    commit_all(ref.repo, [ROOT], 'late claims')
    with pytest.raises(P.PoolError, match='END finalization record is not committed'):   # committed, not finalized
        pool_dir(fleet, 'late', hosts=hosts, ref=ref)
    finalize(ref, 0)
    pool_dir(fleet, 'late', hosts=hosts, ref=ref)                          # finalized: poolable
    directory = tmp_path / 'reg'
    E.claim_attempt(directory, tmp_path / 'x', job=ref.job, round_=0, host='a')
    (directory / 'attempt-00.json').rename(directory / 'attempt-01.json')
    with pytest.raises(P.PoolError, match='contiguous'):
        E.claim_attempt(directory, tmp_path / 'y', job=ref.job, round_=0, host='a')
    claim, _ = E.claim_attempt(tmp_path / 'reg2', tmp_path / 'z', job=ref.job, round_=0, host='b', now=5.)
    assert claim['attempt'] == 0 and claim['receipt_directory'] == 'z' and claim['launched_utc'] == 5.
    assert claim['job_sha256'] == ref.job['sha256'] and claim['end_evidence_sha256'] == fleet.evidence['sha256']
    assert set(claim) == E.CLAIM_FIELDS
    with pytest.raises(P.PoolError, match='lost a committed claim'):
        E.claim_attempt(tmp_path / 'reg2', tmp_path / 'w', job=ref.job, round_=0, host='b', committed=['attempt-07.json'])


# ---------------------------------------------------------------- seals (finding 13)

def test_pool_reads_only_through_the_seal(fleet):
    hosts, ref = scenario(fleet, 'unsealed')
    b_dir = Path(dict(hosts)['b'][0][0])
    # The reviewer's case: end-raw.json outside the seal, its timing bytes changed afterwards.
    manifest = json.loads((b_dir / 'receipt-manifest.json').read_text().splitlines()[0])
    raw_record_b = json.loads((b_dir / 'end-raw.json').read_text())
    for state in raw_record_b['states'].values():
        state['k4s_wall'] = [.00001] * 3
    manifest['files'].pop('end-raw.json')
    (b_dir / 'end-raw.json').write_text(L.canonical(raw_record_b) + '\n')
    (b_dir / 'receipt-manifest.json').write_text(L.canonical(manifest) + '\n')
    digest = L.sha(b_dir / 'receipt-manifest.json')
    (b_dir / 'receipt-manifest.sha256').write_text(digest + '  receipt-manifest.json\n')
    forged_hosts = [('a', dict(hosts)['a']), ('b', [(b_dir, digest)])]
    with pytest.raises(P.PoolError, match='differs from its sealed inventory'):
        pool_dir(fleet, 'unsealed', hosts=forged_hosts, ref=ref)
    (b_dir / 'end-raw.json').unlink()                     # sealed inventory now consistent but incomplete
    with pytest.raises(P.PoolError, match='complete seal lacks: end-raw.json'):
        pool_dir(fleet, 'unsealed', hosts=forged_hosts, ref=ref)


def test_unsealed_classifier_input_is_refused_before_the_frozen_classifier_reads_it(fleet):
    hosts, ref = scenario(fleet, 'planted', {'a': [('good', {})], 'b': [('crash', {}), ('good', {})]})
    crash_dir = Path(dict(hosts)['b'][0][0])
    (crash_dir / 'exactness-tiers.json').write_text(json.dumps(dict(passes=True)) + '\n')
    with pytest.raises(P.PoolError, match='differs from its sealed inventory'):
        pool_dir(fleet, 'planted', hosts=hosts, ref=ref)


def test_recheck_requires_every_consumed_input(fleet):
    path, digest, _ = pool_dir(fleet, 'rc')
    inputs = fleet.tmp / 'rc' / 'pool-inputs.json'
    consumed = json.loads(inputs.read_text())['consumed']
    assert any(p.endswith('end-raw.json') for p in consumed) and any(p.endswith('capacity.jsonl') for p in consumed)
    request = json.loads(path.read_text())
    before = P.input_files(request, path, fleet.repo)
    assert set(consumed) <= set(before)
    # A consumed file that the before/after inventory cannot see is refused (forged pool-inputs, re-sealed).
    forged = dict(consumed, **{str(fleet.tmp / 'elsewhere.json'): '0' * 64})
    sealed = json.loads((fleet.tmp / 'rc' / 'receipt-manifest.json').read_text().splitlines()[0])
    inputs.write_text(L.canonical(dict(scope=P.POOL_SCOPE, consumed=forged)) + '\n')
    sealed['files']['pool-inputs.json'] = L.sha(inputs)
    (fleet.tmp / 'rc' / 'receipt-manifest.json').write_text(L.canonical(sealed) + '\n')
    (fleet.tmp / 'rc' / 'receipt-manifest.sha256').write_text(L.sha(fleet.tmp / 'rc' / 'receipt-manifest.json')
                                                              + '  receipt-manifest.json\n')
    with pytest.raises(P.PoolError, match='omits/changes consumed'):
        P.recheck(path, digest, fleet.tmp / 'rc', 'checker-agent', fleet.tmp / 'rc-recheck.json', repository=fleet.repo)


# ---------------------------------------------------------------- failure / cleanup lifecycle (finding 16)

def test_cleanup_failure_after_a_clean_measurement_seals_failed_without_completion(tmp_path):
    fleet_validity = frozen_e4v3()[1]
    store = L.K4SStore(tmp_path / 'r', P.REFERENCE_SCOPE)

    def body():
        store.write('end-raw.json', dict(placeholder=True))

    def cleanup():
        raise RuntimeError('Reference census process had to be terminated')
    with pytest.raises(RuntimeError, match='terminated'):
        R.run_attempt(store, body, cleanup, dict(completed=True), technical=(fleet_validity.FleetTechnicalError,))
    manifest = json.loads((tmp_path / 'r' / 'receipt-manifest.json').read_text().splitlines()[0])
    assert manifest['status'] == 'failed' and 'end-complete.json' not in manifest['files']
    assert {'failure.json', 'cleanup-failure.json'} <= set(manifest['files'])
    failure = json.loads((tmp_path / 'r' / 'failure.json').read_text())
    assert failure['fleet_technical_cause'] == 'crash' and failure['cleanup'] is True
    verdict = fleet_validity.classify_attempt(tmp_path / 'r', manifest)
    assert verdict['passes'] is False and verdict['technical_repeat_candidate'] is True


def test_cleanup_failure_never_masks_an_exactness_failure(tmp_path):
    fleet_validity = frozen_e4v3()[1]
    store = L.K4SStore(tmp_path / 'r', P.REFERENCE_SCOPE)

    def body():
        raise ValueError('Exactness mismatch: no-deadline K4S != K4 on state s')

    def cleanup():
        raise RuntimeError('backend close failed')
    with pytest.raises(ValueError, match='Exactness'):
        R.run_attempt(store, body, cleanup, dict(completed=True), technical=(fleet_validity.FleetTechnicalError,))
    manifest = json.loads((tmp_path / 'r' / 'receipt-manifest.json').read_text().splitlines()[0])
    assert manifest['status'] == 'failed' and json.loads((tmp_path / 'r' / 'cleanup-failure.json').read_text())['primary_failure']
    verdict = fleet_validity.classify_attempt(tmp_path / 'r', manifest)
    assert verdict['exactness_failure'] is True and verdict['technical_repeat_candidate'] is False


def test_completion_is_written_only_after_cleanup_and_typed_only_for_fleet_errors(tmp_path):
    fleet_validity = frozen_e4v3()[1]
    order = []
    store = L.K4SStore(tmp_path / 'ok', P.REFERENCE_SCOPE)
    real_write = store.write
    store.write = lambda name, value: (order.append(name), real_write(name, value))
    assert R.run_attempt(store, lambda: order.append('body'), lambda: order.append('cleanup'), dict(completed=True)) == 'complete'
    assert order == ['body', 'cleanup', 'end-complete.json', 'receipt-manifest.json']      # then the seal
    assert json.loads((tmp_path / 'ok' / 'end-complete.json').read_text())['cleanup_succeeded'] is True
    store = L.K4SStore(tmp_path / 'typed', P.REFERENCE_SCOPE)

    def body():
        raise fleet_validity.FleetTechnicalError('mhz_gate', 'Reference/reporting MHz differs by >5%')
    with pytest.raises(fleet_validity.FleetTechnicalError):
        R.run_attempt(store, body, lambda: None, dict(completed=True), technical=(fleet_validity.FleetTechnicalError,))
    assert json.loads((tmp_path / 'typed' / 'failure.json').read_text())['fleet_technical_cause'] == 'mhz_gate'
    store = L.K4SStore(tmp_path / 'untyped', P.REFERENCE_SCOPE)
    with pytest.raises(L.PreconditionRefusal):
        R.run_attempt(store, lambda: (_ for _ in ()).throw(L.PreconditionRefusal('rows differ')), lambda: None,
                      dict(completed=True), technical=(fleet_validity.FleetTechnicalError,))
    assert 'fleet_technical_cause' not in json.loads((tmp_path / 'untyped' / 'failure.json').read_text())


def test_cleanup_steps_stop_the_monitor_first_and_close_everything(tmp_path):
    events = []

    class Monitor:
        pid, alive = 7, True

        def join(self, seconds):
            events.append(('join', seconds))

        def is_alive(self):
            return self.alive

        def terminate(self):
            events.append('terminate'); self.alive = False

    class Thing:
        def __init__(self, name, fail=False):
            self.name, self.fail = name, fail

        def set(self):
            events.append('stop')

        def close(self):
            events.append('close-' + self.name)
            if self.fail:
                raise OSError(self.name)
    state = SimpleNamespace(stop=Thing('stop'), monitor=Monitor(), channel=Thing('channel', fail=True),
                            monitor_channel=Thing('monitor'), backend=Thing('backend'))
    with pytest.raises(RuntimeError, match='terminated'):
        R.cleanup_steps(state, join_seconds=0)
    assert events == ['stop', ('join', 0), 'terminate', ('join', 0), 'close-channel', 'close-monitor', 'close-backend']
    events.clear()
    state = SimpleNamespace(stop=Thing('stop'), monitor=SimpleNamespace(pid=None), channel=None, monitor_channel=None,
                            backend=Thing('backend'))
    R.cleanup_steps(state)
    assert events == ['stop', 'close-backend']


def test_pool_reconciles_failure_and_completion_receipts(fleet):
    _, _, document = pool_dir(fleet, 'cleanup', {'a': [('good', {})], 'b': [('cleanup', {}), ('good', {})]})
    assert [x['cause'] if not x['passes'] else 'pass' for x in document['provenance']['host_receipts']['b']['attempts']] \
        == ['crash', 'pass']
    with pytest.raises(P.PoolError, match='No passing'):
        pool_dir(fleet, 'cleanup-only', {'a': [('good', {})], 'b': [('cleanup', {})]})
    # A forged "complete" seal carrying cleanup evidence (the r2 scenario) is contradictory and never poolable.
    hosts, ref = scenario(fleet, 'forged')
    b_dir = Path(dict(hosts)['b'][0][0])
    manifest = json.loads((b_dir / 'receipt-manifest.json').read_text().splitlines()[0])
    (b_dir / 'cleanup-failure.json').write_text(L.canonical(dict(error='close failed')) + '\n')
    manifest['files']['cleanup-failure.json'] = L.sha(b_dir / 'cleanup-failure.json')
    (b_dir / 'receipt-manifest.json').write_text(L.canonical(manifest) + '\n')
    digest = L.sha(b_dir / 'receipt-manifest.json')
    (b_dir / 'receipt-manifest.sha256').write_text(digest + '  receipt-manifest.json\n')
    with pytest.raises(P.PoolError, match='Contradictory END attempt seal'):
        pool_dir(fleet, 'forged', hosts=[('a', dict(hosts)['a']), ('b', [(b_dir, digest)])], ref=ref)


def test_reporting_load_profile_is_set_only_when_evidenced():
    ids = IDS[:4]
    timing = pool([raw('a', 1.0, ids), raw('b', 1.0, ids)], ids)
    assert P.reference_document(timing, dict(reporting_load_profile_evidence={}))['reporting_load_profile'] is False
    full = {k: True for k in L.REPORTING_EVIDENCE_KEYS}
    assert P.reference_document(timing, dict(reporting_load_profile_evidence=full))['reporting_load_profile'] is True
    assert P.reference_document(timing, dict(reporting_load_profile_evidence=dict(full, reporting_guard=False)))[
        'reporting_load_profile'] is False


# ---------------------------------------------------------------- END job authority (r3 finding 19)

EXACT_B = {'a': [('good', {})], 'b': [('exact', {})]}


def test_producer_requires_the_committed_end_job_and_an_open_round(fleet, tmp_path):
    ref = job_repo(fleet, 'producer')
    bare = fleet.tmp / 'repo-bare'
    git(fleet.tmp, 'clone', '-q', str(fleet.repo), str(bare))
    with pytest.raises(P.PoolError, match='END-JOB declaration is not committed'):
        E.end_job(bare, fleet.evidence, ref.job['sha256'], fleet.manifest_sha)
    with pytest.raises(P.PoolError, match='END-JOB SHA mismatch'):
        E.end_job(ref.repo, fleet.evidence, '0' * 64, fleet.manifest_sha)
    with pytest.raises(P.PoolError, match='different frozen K4S manifest'):
        E.end_job(ref.repo, fleet.evidence, ref.job['sha256'], '0' * 64)
    with pytest.raises(P.PoolError, match='no counted blocks'):
        E.producer_claim(ref.repo, ref.job, 0, 'c', tmp_path / 'c0')
    with pytest.raises(P.PoolError, match='requires the committed finalization of round 00'):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1')
    hosts, ref = scenario(fleet, 'producer', ref=ref)                      # round 0 claimed, committed, finalized
    with pytest.raises(P.PoolError, match='already finalized'):
        E.producer_claim(ref.repo, ref.job, 0, 'b', tmp_path / 'b-late')
    assert sorted(E.registry_at(ref.repo, 'HEAD')[0]) == ['a', 'b']
    pool_dir(fleet, 'producer', hosts=hosts, ref=ref)
    # The producer CLI no longer accepts a caller-chosen registry; it requires the END-JOB SHA.
    with pytest.raises(SystemExit):
        R.main(['--bundle', 'B', '--runtime-root', 'R', '--native', 'N', '--corpus', 'K', '--corpus-inventory', 'I',
                '--k4s-manifest-sha256', 'S', '--sd1-manifest-sha256', 'S', '--end-evidence', 'E',
                '--end-evidence-sha256', 'S', '--attempt-registry', 'REG', '--out', 'O'])


def clone_at(fleet, source, name, rev):
    """A fresh clone of scenario ``source`` reset to ``rev`` (each tampering case gets its own repository)."""
    repo = fleet.tmp / f'repo-{name}'
    git(fleet.tmp, 'clone', '-q', str(fleet.repos[source]), str(repo))
    git(repo, 'reset', '-q', '--hard', rev)
    return repo


def test_switching_roots_after_an_exactness_failure_is_refused(fleet, tmp_path):
    hosts, ref = scenario(fleet, 'switch', EXACT_B)
    with pytest.raises(P.PoolError, match='Unrepeatable'):
        pool_dir(fleet, 'switch', hosts=hosts, ref=ref)
    base = git(ref.repo, 'rev-parse', 'HEAD')
    # (1) Re-declare the fixed END-JOB after the failure: the producer and the pool both refuse it.
    other = clone_at(fleet, 'switch', 'switch1', base)
    (other / E.END_JOB_PATH).write_text(L.canonical(job_dict(fleet, declared_utc='2026-10-15T00:00:00Z')) + '\n')
    commit_all(other, [E.END_JOB_PATH], 're-declare after exactness failure')
    new_sha = L.sha(other / E.END_JOB_PATH)
    with pytest.raises(P.PoolError, match='END-JOB declaration is not append-only'):
        E.end_job(other, fleet.evidence, new_sha, fleet.manifest_sha)
    forged = Namespace(**dict(vars(ref), repo=other, job=dict(ref.job, sha256=new_sha)))
    with pytest.raises(P.PoolError, match='END-JOB declaration is not append-only'):
        pool_dir(fleet, 'switch1', hosts=hosts, ref=forged)
    # (2) A second registry root inside the END namespace: refused by path name (producer and pool).
    other = clone_at(fleet, 'switch', 'switch2', base)
    E.claim_attempt(other / E.END_DIR / 'registry-b' / 'round-00' / 'b', tmp_path / 'b-rerun', job=ref.job, round_=0,
                    host='b', now=2000.)
    commit_all(other, [E.END_DIR], 'b re-run in a second root')
    with pytest.raises(P.PoolError, match='claim outside the registry root'):
        pool_dir(fleet, 'switch2', hosts=hosts, ref=Namespace(**dict(vars(ref), repo=other)))
    with pytest.raises(P.PoolError, match='claim outside the registry root'):
        E.producer_claim(other, ref.job, 1, 'b', tmp_path / 'b-next')
    # (3) Same root, but the failed claim and the finalization deleted and redone: not append-only.
    third = clone_at(fleet, 'switch', 'switch4', base)
    final_rel = E.final_path(0)
    git(third, 'rm', '-q', f'{ROOT}/round-00/b/attempt-00.json', final_rel)
    commit_all(third, [ROOT], 'drop the exactness failure')
    redo = Namespace(repo=third, evidence_path=ref.evidence_path, round=0, job=E.end_job(
        third, fleet.evidence, ref.job['sha256'], fleet.manifest_sha))
    b = produce(fleet, redo, 'switch4-b', 'b', utc=3000.)
    commit_all(third, [ROOT], 'b again')
    finalize(redo, 0)
    with pytest.raises(P.PoolError, match='END finalization record is not append-only'):
        pool_dir(fleet, 'switch4', hosts=[('a', dict(hosts)['a']), ('b', [b])], ref=redo)
    # Even with a fresh (never deleted) finalization path the deleted claim is caught by the registry history.
    with pytest.raises(P.PoolError, match=r'registry is not append-only \(claim deleted/modified\)'):
        E.registry_append_only(third)


def test_copied_completion_and_repackaged_evidence_cannot_open_a_second_authority(fleet, tmp_path):
    """Sol r4 finding 19: retain an exactness failure, copy the completion to another committed directory, repackage
    the END evidence and try a second job/registry. The END-JOB location is fixed and unique, so every route fails."""
    hosts, ref = scenario(fleet, 'copy', EXACT_B)
    with pytest.raises(P.PoolError, match='Unrepeatable'):
        pool_dir(fleet, 'copy', hosts=hosts, ref=ref)
    base = git(ref.repo, 'rev-parse', 'HEAD')
    repo = clone_at(fleet, 'copy', 'copy-b', base)
    (repo / 'copied-reporting').mkdir()
    (repo / 'copied-reporting' / 'completion.json').write_bytes((repo / 'completion.json').read_bytes())
    copied = commit_all(repo, ['copied-reporting'], 'byte-identical copy of the completion')
    packaged = json.loads(ref.evidence_path.read_text())
    packaged['completion'].update(repository_path='copied-reporting/completion.json', commit=copied)
    path_b = repo / 'end-evidence-b.json'
    path_b.write_text(json.dumps(packaged))
    evidence_b = E.end_evidence(path_b, L.sha(path_b), repo, frozen_e4v3()[3])    # the repackaging itself validates
    assert evidence_b['sha256'] != fleet.evidence['sha256']
    assert (evidence_b['completion_sha256'], evidence_b['plan_sha256'], evidence_b['membership']) == \
        (fleet.evidence['completion_sha256'], fleet.evidence['plan_sha256'], fleet.evidence['membership'])
    assert E.job_path() == E.END_JOB_PATH                         # never derived from the completion location
    # The one END-JOB is bound to the original evidence: the producer under the repackaged evidence is refused.
    with pytest.raises(P.PoolError, match='not bound to this committed completion/END evidence'):
        E.end_job(repo, evidence_b, ref.job['sha256'], fleet.manifest_sha)
    # A second END-JOB beside the copy (the reviewer's layout, outside the study tree) with its own registry B:
    # never consulted; the producer/pool read only the fixed END_JOB_PATH, whose SHA differs.
    job_b = job_dict(fleet, evidence_b)
    (repo / 'copied-reporting' / 'END-JOB.json').write_text(L.canonical(job_b) + '\n')
    sha_b = L.sha(repo / 'copied-reporting' / 'END-JOB.json')
    E.claim_attempt(repo / 'copied-reporting' / 'registry' / 'round-00' / 'b', tmp_path / 'b-again',
                    job=dict(job_b, sha256=sha_b), round_=0, host='b', now=2000.)
    commit_all(repo, ['copied-reporting'], 'second job + registry B for the copied completion')
    with pytest.raises(P.PoolError, match='END-JOB SHA mismatch'):
        E.end_job(repo, evidence_b, sha_b, fleet.manifest_sha)
    second = Namespace(**dict(vars(ref), repo=repo, evidence_path=path_b, job=dict(ref.job, sha256=sha_b)))
    with pytest.raises(P.PoolError, match='END-JOB SHA mismatch'):
        pool_dir(fleet, 'copy-b', hosts=hosts, ref=second)
    with pytest.raises(P.PoolError, match='not bound to this committed completion/END evidence'):
        pool_dir(fleet, 'copy-b2', hosts=hosts, ref=Namespace(**dict(vars(second), job=ref.job)))
    with pytest.raises(P.PoolError, match='Unrepeatable'):           # the original failure is still the outcome
        pool_dir(fleet, 'copy-a', hosts=hosts, ref=Namespace(**dict(vars(ref), repo=repo)))
    # A second END-JOB-like declaration inside the study tree (any directory, any END-JOB*.json name) is refused
    # outright, for the original authority too.
    for name, rel in (('copy-c', f'{E.STUDY_DIR}/copied-reporting/END-JOB.json'), ('copy-d', f'{E.END_DIR}/END-JOB-b.json')):
        clone = clone_at(fleet, 'copy', name, base)
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(L.canonical(job_b) + '\n')
        commit_all(clone, [rel], 'second END-JOB-like declaration')
        with pytest.raises(P.PoolError, match='END-JOB-like declaration outside the fixed END-JOB location'):
            E.end_job(clone, fleet.evidence, ref.job['sha256'], fleet.manifest_sha)
        with pytest.raises(P.PoolError, match='END-JOB-like declaration outside the fixed END-JOB location'):
            pool_dir(fleet, name, hosts=hosts, ref=Namespace(**dict(vars(ref), repo=clone)))


# ---------------------------------------------------------------- health-only read boundary (Sol r4 finding 20)

def fake_git(listing, calls):
    """A mocked git transport: only name listings are answered; any blob read fails the test."""
    def run(args, **kw):
        calls.append(list(args))
        assert args[3] == 'ls-tree' and '--name-only' in args, args
        prefix = args[args.index('--') + 1]
        return SimpleNamespace(returncode=0, stdout='\0'.join(n for n in listing if n.startswith(prefix)).encode(),
                               stderr=b'')
    return SimpleNamespace(run=run)


def test_namespace_and_declarations_are_checked_by_path_name_only(monkeypatch):
    good = [E.END_JOB_PATH, E.final_path(0), E.claim_path(0, 'a', 'attempt-00.json'),
            f'{E.POOLS_ROOT}/round-00/end-reference.json', f'{E.RECEIPTS_ROOT}/round-00/b/raw-b-0/attempt-claim.json',
            f'{E.RECEIPTS_ROOT}/round-00/b/raw-b-0/end-raw.json',
            f'{E.STUDY_DIR}/outcomes/attempt-00.json', f'{E.STUDY_DIR}/outcomes/marker.json', 'games/outcome-marker.json']
    calls = []
    monkeypatch.setattr(E, 'subprocess', fake_git(good, calls))
    assert E.namespace('R') == [(f'{E.RECEIPTS_ROOT}/round-00/b/raw-b-0/attempt-claim.json', 0, 'b', 'raw-b-0')]
    E.declarations('R')
    assert E.finals_at_head('R') == [0]
    assert all(c[3] == 'ls-tree' for c in calls)                   # names only; no blob was opened
    for bad, message in ((f'{E.END_DIR}/registry-b/round-00/b/attempt-00.json', 'claim outside the registry root'),
                         (f'{E.END_DIR}/attempt-00.json', 'claim outside the registry root'),
                         (f'{E.POOLS_ROOT}/round-00/attempt-claim.json', 'claim outside the registry root'),
                         (f'{E.RECEIPTS_ROOT}/round-00/b/raw-b-0/attempt-01.json', 'claim outside the registry root'),
                         (f'{E.RECEIPTS_ROOT}/round-00/b/attempt-claim.json', 'claim outside the registry root'),
                         (f'{E.END_DIR}/notes/claims.json', 'Unregistered path in the END namespace')):
        monkeypatch.setattr(E, 'subprocess', fake_git(good + [bad], []))
        with pytest.raises(P.PoolError, match=message):
            E.namespace('R')
    for bad, message in ((f'{E.STUDY_DIR}/other/END-JOB.json', 'END-JOB-like declaration'),
                         (f'{E.END_DIR}/end-job-copy.json', 'END-JOB-like declaration'),
                         (f'{E.END_DIR}/sub/END-FINAL-round-00.json', 'finalization-like record')):
        monkeypatch.setattr(E, 'subprocess', fake_git(good + [bad], []))
        with pytest.raises(P.PoolError, match=message):
            E.declarations('R')
    with pytest.raises(P.PoolError, match='outside the health-only END namespace'):
        E.namespace_blob('R', 'games/outcome-marker.json', 'probe')


def test_pool_authority_never_reads_outside_the_end_namespace(fleet, monkeypatch):
    """Synthetic marker files (claim-shaped, claim-named, outcome-named) outside the END namespace are never opened,
    searched or named in any git command of the authority; the pool still conforms."""
    hosts, ref = scenario(fleet, 'boundary')
    claim = json.loads((ref.repo / E.claim_path(0, 'a', 'attempt-00.json')).read_text())
    markers = {'games/outcome-marker.json': json.dumps(dict(claim=claim, claim_sha256='0' * 64), indent=2),
               f'{E.STUDY_DIR}/outcomes/attempt-00.json': json.dumps(claim, indent=2),
               f'{E.STUDY_DIR}/outcomes/marker.txt': E.REGISTRY_SCHEMA + ' marker\n'}
    for rel, text in markers.items():
        (ref.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (ref.repo / rel).write_text(text)
    commit_all(ref.repo, list(markers), 'synthetic markers outside the END namespace')
    calls, real = [], subprocess.run

    def recording(args, **kw):
        calls.append(list(args))
        return real(args, **kw)
    monkeypatch.setattr(E, 'subprocess', SimpleNamespace(run=recording))
    _, _, document = pool_dir(fleet, 'boundary', hosts=hosts, ref=ref)
    assert document['pool_conforms'] and calls
    assert {c[3] for c in calls} <= {'show', 'ls-tree', 'log', 'merge-base'}
    for c in calls:
        assert c[:3] == ['git', '-C', str(ref.repo)]
        if c[3] == 'show':
            assert c[4].split(':', 1)[1].startswith(E.END_DIR + '/'), c
        if c[3] in ('ls-tree', 'log'):
            assert '--name-only' in c or '--format=%H' in c, c
            assert all(p.startswith(E.STUDY_DIR + '/') for p in c[c.index('--') + 1:]), c
    named = ' '.join(' '.join(c) for c in calls)
    assert not any(rel in named for rel in markers) and 'outcome' not in named


# ---------------------------------------------------------------- complete-bytes parsing (Sol r4 finding 21)

FORMS = ('compact', 'indented', 'malformed')


def reformat(data, form):
    value = json.loads(data)
    return {'compact': json.dumps(value, separators=(',', ':')), 'indented': json.dumps(value, indent=2),
            'malformed': json.dumps(value, indent=2)[:-1]}[form] + '\n'


def final_manual(ref, utc=10. ** 6):
    """A finalization written from the committed claim file SHAs (does not parse the claims)."""
    root = ref.repo / E.REGISTRY_ROOT / 'round-00'
    claims = {'0': {h: [L.sha(p) for p in sorted((root / h).iterdir())] for h in sorted(p.name for p in root.iterdir())}}
    final = dict(schema=E.FINAL_SCHEMA, job_sha256=ref.job['sha256'], round=0, claims=claims, prior_rounds=[],
                 finalized_utc=utc, finalized_by='coordinator')
    (ref.repo / E.final_path(0)).write_text(L.canonical(final) + '\n')
    commit_all(ref.repo, [E.final_path(0)], 'END finalization round 0')
    ref.final_sha, ref.round = L.sha(ref.repo / E.final_path(0)), 0
    return ref


@pytest.mark.parametrize('form', FORMS)
def test_registry_claims_are_parsed_from_their_complete_bytes(fleet, form):
    ref = job_repo(fleet, f'claim-{form}')

    def formatted(directory):
        claim, _ = E.producer_claim(ref.repo, ref.job, 0, 'a', directory, now=1000.)
        path = ref.repo / E.claim_path(0, 'a', 'attempt-00.json')
        path.write_text(reformat(path.read_bytes(), form))
        return claim, L.sha(path)
    plan = {'a': [('good', dict(claim=formatted))], 'b': [('good', dict(factor=1.02))]}
    hosts, ref = scenario(fleet, f'claim-{form}', plan, ref=ref, final=False)
    final_manual(ref)
    if form == 'malformed':
        with pytest.raises(P.PoolError, match='not one well-formed JSON document'):
            pool_dir(fleet, f'claim-{form}', hosts=hosts, ref=ref)
    else:                                                          # compact and indented claims are equivalent
        assert pool_dir(fleet, f'claim-{form}', hosts=hosts, ref=ref)[2]['pool_conforms']


@pytest.mark.parametrize('form', FORMS)
def test_receipt_copies_and_stray_claims_in_any_serialization(fleet, form):
    ref = job_repo(fleet, f'copies-{form}')

    def hidden(directory):                                         # a claim outside the fixed registry root
        return E.claim_attempt(fleet.tmp / f'uncommitted-{form}', directory, job=ref.job, round_=0, host='b', now=900.)
    plan = {'a': [('good', {})], 'b': [('crash', dict(claim=hidden)), ('good', {})]}
    hosts, ref = scenario(fleet, f'copies-{form}', plan, ref=ref)
    base = git(ref.repo, 'rev-parse', 'HEAD')
    listed = [('a', dict(hosts)['a']), ('b', dict(hosts)['b'][1:])]
    crash_dir, good_dir = (Path(d) for d, _ in dict(hosts)['b'])

    def case(suffix, rel, data):
        clone = clone_at(fleet, f'copies-{form}', f'copies-{form}-{suffix}', base)
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(data)
        commit_all(clone, [rel], 'committed ' + suffix)
        return lambda: pool_dir(fleet, f'copies-{form}-{suffix}', hosts=listed, ref=Namespace(**dict(vars(ref), repo=clone)))
    malformed = 'not one well-formed JSON document'
    # A receipt copy of a registry claim: compact/indented are equivalent and accepted; malformed is refused.
    run = case('registered', f'{E.RECEIPTS_ROOT}/round-00/b/{good_dir.name}/attempt-claim.json',
               reformat((good_dir / 'attempt-claim.json').read_bytes(), form))
    if form == 'malformed':
        with pytest.raises(P.PoolError, match=malformed):
            run()
    else:
        assert run()[2]['pool_conforms']
    # A receipt copy of the hidden claim: refused in every serialization (the r4 indented bypass is closed).
    run = case('hidden', f'{E.RECEIPTS_ROOT}/round-00/b/{crash_dir.name}/attempt-claim.json',
               reformat((crash_dir / 'attempt-claim.json').read_bytes(), form))
    with pytest.raises(P.PoolError, match=malformed if form == 'malformed' else 'claim is not in the registry'):
        run()
    # The hidden claim itself committed in a second root: refused by its path name, whatever its bytes.
    run = case('stray', f'{E.END_DIR}/hidden/round-00/b/attempt-00.json',
               reformat((fleet.tmp / f'uncommitted-{form}' / 'attempt-00.json').read_bytes(), form))
    with pytest.raises(P.PoolError, match='claim outside the registry root'):
        run()


def test_an_older_finalization_snapshot_after_additional_claims_is_refused(fleet, tmp_path):
    hosts, ref = scenario(fleet, 'snapshot')
    pool_dir(fleet, 'snapshot', hosts=hosts, ref=ref)
    with pytest.raises(P.PoolError, match='already finalized'):           # the producer refuses a late claim ...
        E.producer_claim(ref.repo, ref.job, 0, 'b', tmp_path / 'extra')
    E.claim_attempt(ref.repo / ROOT / 'round-00' / 'b', tmp_path / 'extra', job=ref.job, round_=0, host='b', now=5000.)
    commit_all(ref.repo, [ROOT], 'additional claim after finalization')    # ... and one forced in anyway is seen
    with pytest.raises(P.PoolError, match='not the complete claim inventory at HEAD'):
        pool_dir(fleet, 'snapshot2', hosts=hosts, ref=ref)
    # A finalization committed before the claims it lists is refused even if HEAD matches it.
    hosts, ref = scenario(fleet, 'early')
    final_rel = E.final_path(0)
    data = (ref.repo / final_rel).read_bytes()
    git(ref.repo, 'reset', '-q', 'HEAD~2')                                 # un-commit claims and finalization
    commit_all(ref.repo, [final_rel], 'finalization first')
    commit_all(ref.repo, [ROOT], 'claims afterwards')
    assert (ref.repo / final_rel).read_bytes() == data
    with pytest.raises(P.PoolError, match='committed before every claim'):
        pool_dir(fleet, 'early', hosts=hosts, ref=ref)


# ---------------------------------------------------------------- earlier rounds re-validated (Sol r5 finding 22)

def commit_round(ref, round_, hosts, pool=None, only=None):
    """Commit round RR's original attempt receipt directories (all hosts, or ``only``) under RECEIPTS_ROOT and, if
    given, its pool directory already written at the fixed POOLS_ROOT/round-RR."""
    for host, attempts in hosts:
        if only is None or host in only:
            for directory, _ in attempts:
                shutil.copytree(directory, ref.repo / E.RECEIPTS_ROOT / f'round-{round_:02d}' / host / Path(directory).name)
    commit_all(ref.repo, [E.END_DIR], f'round {round_} receipts' + (' and pool' if pool else ''))
    return L.sha(ref.repo / E.pool_path(round_) / 'receipt-manifest.json') if pool else None


def forge_pool(ref, round_, files, status='nonconforming'):
    """Commit a hand-made pool at the fixed location: the given files plus a self-consistent seal and sidecar."""
    directory = ref.repo / E.pool_path(round_)
    directory.mkdir(parents=True)
    for name, value in files.items():
        data = value if isinstance(value, bytes) else (L.canonical(dict(scope=P.POOL_SCOPE, **value)) + '\n').encode()
        (directory / name).write_bytes(data)
    seal = dict(scope=P.POOL_SCOPE, status=status, files={n: L.sha(directory / n) for n in sorted(files)})
    (directory / 'receipt-manifest.json').write_text(L.canonical(seal) + '\n')
    (directory / 'receipt-manifest.sha256').write_text(L.sha(directory / 'receipt-manifest.json') + '  receipt-manifest.json\n')
    commit_all(ref.repo, [E.pool_path(round_)], f'hand-made round {round_} pool')
    return L.sha(directory / 'receipt-manifest.json')


def forced(ref, round_, host, utc):
    """A claim written directly into the registry, bypassing the producer's predecessor check."""
    return lambda d: E.claim_attempt(ref.repo / ROOT / f'round-{round_:02d}' / host, d, job=ref.job, round_=round_,
                                     host=host, now=utc)


def forced_round(fleet, ref, name, prior):
    """Round 01 claimed and measured (good on both hosts) despite the producer, then finalized naming ``prior``."""
    plan = {'a': [('good', dict(claim=forced(ref, 1, 'a', 1100.)))],
            'b': [('good', dict(factor=1.02, claim=forced(ref, 1, 'b', 1101.)))]}
    hosts1, ref = scenario(fleet, name, plan, ref=ref, round_=1, final=False)
    finalize(ref, 1, prior)
    return hosts1, ref


def test_rerun_rounds_record_and_reconcile_the_earlier_nonconforming_pool(fleet, tmp_path):
    """A genuine ratio-only nonconforming round 00 permits round 01; both the producer and the pool re-validate round 00
    by the pool's own code path, and the fresh-interpreter re-check repeats it."""
    hosts0, ref = scenario(fleet, 'rounds', {'a': [('good', {})], 'b': [('good', dict(factor=1.2))]})
    _, _, doc0 = pool_dir(fleet, 'rounds0', hosts=hosts0, ref=ref, output=ref.repo / E.pool_path(0))
    assert doc0['pool_conforms'] is False and doc0['provenance']['round'] == 0
    with pytest.raises(P.PoolError, match='Earlier END pool round 00 is not committed'):     # pool not yet committed
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a-early', context=pool_context(fleet, ref))
    final0_head = git(ref.repo, 'rev-parse', 'HEAD')
    seal = commit_round(ref, 0, hosts0, pool=True)
    prior = [dict(round=0, pool_repository_path=E.pool_path(0), pool_manifest_sha256=seal)]
    # The same pool committed only after a round-01 claim: the re-run needs the validated pool first.
    late = clone_at(fleet, 'rounds', 'rounds-late', final0_head)
    late_ref = Namespace(**dict(vars(ref), repo=late))
    E.claim_attempt(late / ROOT / 'round-01' / 'b', tmp_path / 'b-late', job=ref.job, round_=1, host='b', now=1200.)
    commit_all(late, [ROOT], 'round 01 claim before the round 00 pool')
    shutil.copytree(ref.repo / E.pool_path(0), late / E.pool_path(0))
    commit_round(late_ref, 0, hosts0, pool=True)
    with pytest.raises(P.PoolError, match="committed after a later round's claim"):
        E.producer_claim(late, ref.job, 1, 'a', tmp_path / 'a-late', context=pool_context(fleet, late_ref))
    with pytest.raises(P.PoolError, match='no pool context given'):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a-blind')
    assert P.predecessors(ref.repo, ref.job, 1, pool_context(fleet, ref))[0]['status'] == 'nonconforming'
    hosts1, ref = scenario(fleet, 'rounds', GOOD, ref=ref, round_=1, final=False)        # the producer accepts round 01
    before_final = git(ref.repo, 'rev-parse', 'HEAD')
    for name, bad, message in (('rounds-omit', [], 'record every earlier pool round'),
                               ('rounds-seal', [dict(prior[0], pool_manifest_sha256='0' * 64)], 'seal mismatch')):
        clone = fleet.tmp / f'repo-{name}'
        git(fleet.tmp, 'clone', '-q', str(ref.repo), str(clone))
        git(clone, 'reset', '-q', '--hard', before_final)
        variant = finalize(Namespace(repo=clone, evidence_path=ref.evidence_path, job=ref.job, round=1), 1, bad)
        with pytest.raises(P.PoolError, match=message):
            pool_dir(fleet, name, hosts=hosts1, ref=variant)
    finalize(ref, 1, prior)
    path, digest, doc1 = pool_dir(fleet, 'rounds1', hosts=hosts1, ref=ref)
    prov = doc1['provenance']
    assert doc1['pool_conforms'] is True and prov['round'] == 1 and sorted(prov['claims']) == ['0', '1']
    assert prov['prior_rounds'] == [dict(prior[0], status='nonconforming',
                                         finalization_sha256=L.sha(ref.repo / E.final_path(0)))]
    receipt = P.recheck(path, digest, fleet.tmp / 'rounds1', 'checker-agent', fleet.tmp / 'rounds1-recheck.json',
                        repository=ref.repo)
    assert receipt['passes'] and receipt['round'] == 1
    # Pooling the older round again after round 1 exists is refused (latest finalized round only).
    with pytest.raises(P.PoolError, match='exactly rounds 00..00'):
        pool_dir(fleet, 'rounds0-again', hosts=hosts0, ref=Namespace(**dict(vars(ref), round=0, final_sha=L.sha(
            ref.repo / E.final_path(0)))))


def test_forged_predecessor_certificate_is_refused_by_producer_pool_and_recheck(fleet, tmp_path, monkeypatch, capfd):
    """Sol r5 finding 22, the reviewer's probe: round 00 retains an exactness failure; a provenance-only reference under
    a seal listing only end-reference.json is offered as the nonconforming round-00 pool."""
    hosts0, ref = scenario(fleet, 'forged', EXACT_B)
    with pytest.raises(P.PoolError, match='Unrepeatable'):
        pool_dir(fleet, 'forged0', hosts=hosts0, ref=ref)
    commit_round(ref, 0, hosts0)
    final0 = json.loads((ref.repo / E.final_path(0)).read_text())
    certificate = dict(provenance=dict(end_job=dict(sha256=ref.job['sha256']), round=0, claims=final0['claims'],
                                       finalization=dict(sha256=L.sha(ref.repo / E.final_path(0)))))
    seal = forge_pool(ref, 0, {'end-reference.json': certificate})
    refused = 'Earlier END pool round 00 is not a complete sealed nonconforming pool'
    with pytest.raises(P.PoolError, match=refused):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1', context=pool_context(fleet, ref))
    prior = [dict(round=0, pool_repository_path=E.pool_path(0), pool_manifest_sha256=seal)]
    hosts1, ref = forced_round(fleet, ref, 'forged', prior)
    with pytest.raises(P.PoolError, match=refused):
        pool_dir(fleet, 'forged1', hosts=hosts1, ref=ref)
    # A pooler that trusted the certificate (the r5 behaviour) is caught by the independent fresh-interpreter re-check.
    trusted = [dict(prior[0], finalization_sha256=L.sha(ref.repo / E.final_path(0)), status='nonconforming')]
    monkeypatch.setattr(P, 'validated_priors', lambda *a: trusted)
    path, digest, doc = pool_dir(fleet, 'forged1-trusting', hosts=hosts1, ref=ref)
    assert doc['pool_conforms'] is True
    monkeypatch.undo()
    capfd.readouterr()
    with pytest.raises(subprocess.CalledProcessError):
        P.recheck(path, digest, fleet.tmp / 'forged1-trusting', 'checker-agent', fleet.tmp / 'forged-recheck.json',
                  repository=ref.repo)
    assert refused in capfd.readouterr().err and not (fleet.tmp / 'forged-recheck.json').exists()


def full_shaped_pool(fleet, ref, hosts0, r=0):
    """A complete, self-consistent nonconforming pool inventory (reference, descriptor bound to the round's
    finalization and to exactly the committed receipts, inputs, ratio record) that the pooler never produced."""
    path, _ = descriptor(fleet, hosts0, ref, f'hand-{r}-input.json')
    document = dict(pool_conforms=False, host_ratio_to_pool={'a': 1.1, 'b': 0.9}, provenance=dict(round=r))
    raw_descriptor = path.read_bytes()
    return forge_pool(ref, r, {'end-reference.json': document,
                               'pool-input.json': dict(sha256=L.sha_bytes(raw_descriptor), text=raw_descriptor.decode()),
                               'pool-inputs.json': dict(consumed={}),
                               'pool-nonconforming.json': dict(host_ratio_to_pool=document['host_ratio_to_pool'])})


@pytest.mark.parametrize('case', ('exactness', 'excess-repeats'))
def test_an_unrepeatable_earlier_round_fails_the_whole_end_job(fleet, tmp_path, case):
    """A retained round-00 exactness failure (or an invalid excess repeat) under a complete, hash-consistent
    nonconforming pool shell: the re-validation reclassifies round 00 and refuses round 01 (producer and pool)."""
    plan = EXACT_B if case == 'exactness' else {'a': [('good', {})], 'b': [('crash', {}), ('crash', {}), ('good', {})]}
    message = 'Unrepeatable END failure' if case == 'exactness' else 'at most one repeat'
    hosts0, ref = scenario(fleet, f'unrep-{case}', plan)
    with pytest.raises(P.PoolError, match=message):
        pool_dir(fleet, f'unrep-{case}0', hosts=hosts0, ref=ref)
    commit_round(ref, 0, hosts0)
    seal = full_shaped_pool(fleet, ref, hosts0)
    with pytest.raises(P.PoolError, match=message):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1', context=pool_context(fleet, ref))
    prior = [dict(round=0, pool_repository_path=E.pool_path(0), pool_manifest_sha256=seal)]
    hosts1, ref = forced_round(fleet, ref, f'unrep-{case}', prior)
    with pytest.raises(P.PoolError, match=message):                  # round 01 is good, yet never conforms
        pool_dir(fleet, f'unrep-{case}1', hosts=hosts1, ref=ref)


def test_producer_refuses_a_new_round_without_a_validated_nonconforming_predecessor(fleet, tmp_path):
    hosts0, ref = scenario(fleet, 'pred', GOOD)
    context = pool_context(fleet, ref)
    with pytest.raises(P.PoolError, match='no pool context given'):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1')
    with pytest.raises(P.PoolError, match='Earlier END pool round 00 is not committed'):        # finalized, no pool
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1', context=context)
    base = git(ref.repo, 'rev-parse', 'HEAD')
    # (1) The genuine CONFORMING round-00 pool (status complete): that is the END reference; no re-run.
    pool_dir(fleet, 'pred0', hosts=hosts0, ref=ref, output=ref.repo / E.pool_path(0))
    commit_round(ref, 0, hosts0, pool=True)
    with pytest.raises(P.PoolError, match='is not a complete sealed nonconforming pool'):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1', context=context)
    # (2) The same conforming pool relabeled nonconforming (complete inventory, self-consistent seal): recomputed.
    clone = clone_at(fleet, 'pred', 'pred-relabel', base)
    relabel = Namespace(**dict(vars(ref), repo=clone))
    genuine = ref.repo / E.pool_path(0)
    files = {n: (genuine / n).read_bytes() for n in P.POOL_FILES}
    files['pool-nonconforming.json'] = dict(host_ratio_to_pool=json.loads(files['end-reference.json'])['host_ratio_to_pool'])
    forge_pool(relabel, 0, files)
    commit_round(relabel, 0, hosts0)
    with pytest.raises(P.PoolError, match='conforms on recomputation'):
        E.producer_claim(clone, ref.job, 1, 'a', tmp_path / 'a1', context=pool_context(fleet, relabel))
    # (3) A genuine nonconforming round-00 pool whose original attempt receipts are not all committed.
    hosts0, ref = scenario(fleet, 'pred-missing', {'a': [('good', {})], 'b': [('good', dict(factor=1.2))]})
    pool_dir(fleet, 'pred-missing0', hosts=hosts0, ref=ref, output=ref.repo / E.pool_path(0))
    commit_round(ref, 0, hosts0, pool=True, only=('a',))
    with pytest.raises(P.PoolError, match='original attempt receipts are not committed exactly'):
        E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1m', context=pool_context(fleet, ref))
    # (4) ... and once they are committed the same pool re-validates: the producer opens round 01.
    commit_round(ref, 0, hosts0, only=('b',))
    claim, _ = E.producer_claim(ref.repo, ref.job, 1, 'a', tmp_path / 'a1ok', context=pool_context(fleet, ref))
    assert claim['round'] == 1 and claim['attempt'] == 0
