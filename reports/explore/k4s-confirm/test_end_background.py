"""K4S END background adapter (r2 finding 10): the real worker startup/profile/evidence chain, offline.

Only the TIERS bundle validation, the model/native work and the host identity are injected (``Hooks``); the frozen
K4S manifest, frozen e4v3 helper pins, committed K4S evidence, bundle pins, frozen slot layout, frozen reporting join,
frozen FleetBackground lifecycle and the frozen corpus loop all run for real. No torch, native, corpus or outcomes.
"""
import json
import queue
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'mac'), str(HERE)]
import end_background as G  # noqa: E402
import end_evidence as E  # noqa: E402
import k4s_logic as L  # noqa: E402
import test_end_reference as T  # noqa: E402

TIERS = ('K0c', 'S', 'K2', 'K4')
BACKGROUND = [5, 6, 7, 8, 9]                 # PLAN: physical 0-9, 2 slots of 5, reference slot 0 = [0-4]


class FakeWork:
    def __init__(self, manifest, stop=None, limit=None, delay=0.):
        self.by_id = {i: dict(id=i) for t in TIERS for i in manifest['sets']['speed'][t]}
        self.stop, self.limit, self.delay = stop, limit, delay
        self.calls, self.closed, self.search_cpus = [], False, None

    def work(self, row, tier):
        self.calls.append((tier, row['id']))
        if self.delay:
            time.sleep(self.delay)
        if self.limit is not None and len(self.calls) >= self.limit:
            self.stop.set()
        return dict(action=1), dict(wall_seconds=.01)

    def close(self):
        self.closed = True


class Hooks:
    """Injected work/identity only (module level, so a spawned worker can unpickle it)."""

    def __init__(self, manifest, node='a', nice=10, limit=None, delay=0.):
        self.manifest, self.node, self.nice, self.limit, self.delay = manifest, node, nice, limit, delay
        self.stop, self.affinity, self.made = None, [], []

    def validate_bundle(self, bundle, root):
        return json.loads(json.dumps(self.manifest))

    def host(self):
        return dict(system='Linux', node=self.node, nice=self.nice, sched_other=True)

    def set_affinity(self, cpus):
        self.affinity.append(list(cpus))

    def backend(self, bundle, root, native):
        work = FakeWork(self.manifest, self.stop, self.limit, self.delay)
        self.made.append(work)
        return work


def setup(tmp_path, *, evidence_pin=None, counted=(3000, 900)):
    repo, evidence_path = T.committed_evidence(tmp_path, counted=counted)
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    (bundle / 'plan.json').write_bytes((repo / 'plan.json').read_bytes())
    (bundle / 'end-evidence.json').write_bytes(evidence_path.read_bytes())
    manifest = dict(profile='fleet-reference',
                    files={'plan.json': L.sha(bundle / 'plan.json'),
                           'end-evidence.json': evidence_pin or L.sha(bundle / 'end-evidence.json')},
                    reference_load_profile=dict(T.PROFILE, host='a', plan='plan.json', end_evidence='end-evidence.json'),
                    sets=dict(speed={t: [f'{t}-{i:03d}' for i in range(60)] for t in TIERS}))
    k4s = tmp_path / 'K4S-MAC-MANIFEST-frozen.json'
    k4s.write_text(json.dumps(T.built_manifest(), indent=2, sort_keys=True) + '\n')
    spec = G.evidence_spec(evidence_path, L.sha(evidence_path), repo, k4s, L.sha(k4s))
    return bundle, manifest, spec


def run_inline(bundle, hooks, spec, cpus=BACKGROUND, slot=1):
    ready, stop, errors = threading.Event(), threading.Event(), queue.Queue()
    hooks.stop = stop
    try:
        G.k4s_corpus_worker(bundle, L.REPO_ROOT, 'native-unused', ready, stop, cpus, slot, errors, spec, hooks)
    except Exception as error:      # the worker re-raises after queuing the full error, as the frozen worker does
        return ready, errors.get_nowait(), error
    return ready, None, None


def test_frozen_tiers_worker_reader_cannot_accept_k4s_evidence(tmp_path):
    """Why the adapter exists: the frozen fleet_end.evidence (called by every frozen FleetBackground worker
    through fleet_profile.pinned_profile) rejects the K4S schema before anything else."""
    bundle, manifest, spec = setup(tmp_path)
    fleet_end = T.frozen_e4v3()[3]
    with pytest.raises(ValueError, match='Unsupported END evidence'):
        fleet_end.evidence(bundle, manifest, json.loads((bundle / 'plan.json').read_text()))


def test_k4s_worker_runs_the_frozen_corpus_loop_after_the_k4s_evidence_chain(tmp_path):
    bundle, manifest, spec = setup(tmp_path)
    hooks = Hooks(manifest, limit=120)
    ready, error, raised = run_inline(bundle, hooks, spec)
    assert error is None and raised is None and ready.is_set()
    work = hooks.made[0]
    assert hooks.affinity == [BACKGROUND] and work.search_cpus == BACKGROUND and work.closed is True
    # Frozen fleet_corpus_worker order: slot 1 starts its rotation at TIERS[1]; 50-state offsets per tier.
    assert work.calls[:50] == [('S', f'S-{i:03d}') for i in range(50)]
    assert work.calls[50:100] == [('K2', f'K2-{i:03d}') for i in range(50)]
    assert work.calls[100:120] == [('K4', f'K4-{i:03d}') for i in range(20)]


@pytest.mark.parametrize('kind,message', [
    ('reference-mask', 'Background mask absent'),
    ('wrong-nice', 'inherit the pinned reporting host/priority'),
    ('wrong-host', 'inherit the pinned reporting host/priority|absent/forbidden'),
    ('bundle-pin', 'Bundle-pinned END evidence is not the committed'),
    ('not-fleet-reference', 'fleet-reference bundle profile'),
    ('tiers-counts', 'full counted primary population'),
])
def test_k4s_worker_fails_closed_and_queues_the_full_error(tmp_path, kind, message):
    bundle, manifest, spec = setup(tmp_path, evidence_pin='0' * 64 if kind == 'bundle-pin' else None,
                                   counted=(2400, 600) if kind == 'tiers-counts' else (3000, 900))
    if kind == 'not-fleet-reference':
        manifest['profile'] = 'linux-dry-run'
    hooks = Hooks(manifest, nice=0 if kind == 'wrong-nice' else 10, node='b' if kind == 'wrong-host' else 'a', limit=1)
    ready, error, raised = run_inline(bundle, hooks, spec, cpus=[0, 1, 2, 3, 4] if kind == 'reference-mask' else BACKGROUND)
    assert raised is not None and error['slot'] == 1 and __import__('re').search(message, error['error'])
    assert not ready.is_set() and not any(w.calls for w in hooks.made)       # no work before every check passed


def test_k4s_worker_refuses_the_tiers_evidence_schema(tmp_path):
    bundle, manifest, spec = setup(tmp_path)
    tiers = dict(json.loads(Path(spec['end_evidence']).read_text()), schema='clasher.e4v3.end-evidence.v1')
    path = Path(spec['end_evidence']).with_name('tiers-evidence.json')
    path.write_text(json.dumps(tiers))
    (bundle / 'end-evidence.json').write_bytes(path.read_bytes())
    manifest['files']['end-evidence.json'] = L.sha(path)
    spec = dict(spec, end_evidence=str(path), end_evidence_sha256=L.sha(path))
    _, error, raised = run_inline(bundle, Hooks(manifest, limit=1), spec)
    assert raised is not None and 'Unsupported K4S END evidence' in error['error']


def test_k4s_worker_refuses_a_draft_k4s_manifest(tmp_path):
    bundle, manifest, spec = setup(tmp_path)
    draft = tmp_path / 'draft.json'
    draft.write_text(json.dumps(dict(T.built_manifest(), frozen=False)))
    _, error, raised = run_inline(bundle, Hooks(manifest, limit=1), dict(spec, k4s_manifest=str(draft),
                                                                       k4s_manifest_sha256=L.sha(draft)))
    assert raised is not None and 'frozen K4S manifest' in error['error']


def test_spawned_k4s_fleet_background_uses_the_frozen_lifecycle(tmp_path):
    """The real K4SFleetBackground: spawn, readiness wait, check, typed close (frozen FleetBackground code)."""
    bundle, manifest, spec = setup(tmp_path)
    load = G.K4SFleetBackground(bundle, L.REPO_ROOT, 'native-unused', [BACKGROUND], spec, hooks=Hooks(manifest, delay=.002))
    load.ready_timeout = 120
    with load as background:
        background.check()
        assert all(w.is_alive() for w in background.workers) and background.readies[0].is_set()
    assert [w.exitcode for w in load.workers] == [0]
    bad = G.K4SFleetBackground(bundle, L.REPO_ROOT, 'native-unused', [BACKGROUND], spec,
                               hooks=Hooks(manifest, nice=0, delay=.002))
    bad.ready_timeout = 120
    with pytest.raises(RuntimeError, match='(?s)Fleet background failure: .*inherit the pinned reporting host/priority'):
        with bad:
            pass


def test_adapter_overrides_only_the_worker_target_and_imports_frozen_code_lazily():
    import subprocess
    cls = G.background_class()
    from replay_load import FleetBackground
    assert issubclass(cls, FleetBackground)
    assert set(vars(cls)) - {'__module__', '__qualname__', '__doc__', '__init__'} == set()     # frozen lifecycle
    code = ('import sys; sys.path[:0] = [%r, %r]; import end_background; '
            'print(sorted(m for m in ("replay_load", "tier_backend", "fleet_end") if m in sys.modules))')
    out = subprocess.run([sys.executable, '-I', '-B', '-c', code % (str(HERE / 'mac'), str(HERE))],
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == '[]'      # nothing frozen is imported before the caller verified its pins
