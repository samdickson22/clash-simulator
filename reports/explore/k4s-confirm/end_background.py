"""PREREG-K4S END background slots (r3 §4.5 reporting load profile; delta 8). Never launches games.

The frozen TIERS ``replay_load.FleetBackground`` workers call ``fleet_profile.pinned_profile`` and thus the frozen
``fleet_end.evidence`` reader, which accepts only ``clasher.e4v3.end-evidence.v1`` with 2400/600 counted blocks.
K4S evidence (``clasher.k4s.end-evidence.v1``, 3000/900) can never pass it, so this K4S-owned adapter replaces only
the worker's profile/evidence step and keeps every other frozen convention:

- ``K4SFleetBackground`` builds a subclass of the frozen ``FleetBackground`` (spawn context, readiness wait, typed
  ``check``, error queue, ``close``/``__exit__`` semantics are the frozen code, unchanged), importing the frozen
  module only on first use, after the caller verified its pin;
- each spawned ``k4s_corpus_worker`` re-validates the bundle (frozen ``validate_bundle``, fleet-reference
  profile), the frozen K4S manifest and the frozen e4v3 helper pins, then ``k4s_reporting_profile``: the
  bundle-pinned K4S evidence (SHA = the committed evidence), the K4S evidence itself (``end_evidence``, committed
  bytes), the bundle plan = the committed K4S plan, Linux SCHED_OTHER, the frozen ``fleet_profile.slot_layout``
  and frozen ``fleet_end.host_reporting``; its mask must be one of the pinned background masks;
- the work is the frozen ``fleet_corpus_worker`` loop verbatim: ``TierBackend.work`` on the bundle's TIERS
  speed sets, 50-state offsets, tier rotation starting at the slot index.

``hooks`` injects only the model/native work and host identity (tests run the real chain offline with fake
work); production always uses ``FrozenHooks``.
"""
import os
import platform
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE / "mac"), str(HERE)]      # explicit: `python -I` omits the script directory
import k4s_logic as L  # noqa: E402
import end_evidence as E  # noqa: E402

E4V3 = str(ROOT / L.E4V3_REL)
if E4V3 not in sys.path:
    sys.path.insert(0, E4V3)


class FrozenHooks:
    """Production work and identity: the frozen TIERS backend on this Linux host."""

    def validate_bundle(self, bundle, root):
        from tier_backend import validate_bundle
        return validate_bundle(bundle, root, dry_run=True, require_references=False)

    def host(self):
        return dict(system=platform.system(), node=platform.node(), nice=os.getpriority(os.PRIO_PROCESS, 0),
                    sched_other=os.sched_getscheduler(0) == os.SCHED_OTHER)

    def set_affinity(self, cpus):
        os.sched_setaffinity(0, set(cpus))

    def backend(self, bundle, root, native):
        from tier_backend import TierBackend
        return TierBackend(bundle, root, native)


def evidence_spec(end_evidence, end_evidence_sha256, repository, k4s_manifest, k4s_manifest_sha256):
    return dict(end_evidence=str(end_evidence), end_evidence_sha256=end_evidence_sha256, repository=str(repository),
                k4s_manifest=str(k4s_manifest), k4s_manifest_sha256=k4s_manifest_sha256)


def frozen_helpers(spec, root):
    """The frozen K4S manifest (pins every K4S/END/e4v3 file) and the pin-checked frozen fleet helpers."""
    import end_pool as P
    manifest = L.load_k4s_manifest(spec["k4s_manifest"], spec["k4s_manifest_sha256"], root, require_frozen=True)
    return manifest, P.frozen_helpers(manifest)


def k4s_reporting_profile(bundle, manifest, spec, host, fleet_end, fleet_profile):
    """K4S counterpart of frozen fleet_profile.pinned_profile: the committed K4S evidence, the bundle-pinned
    plan and evidence, the pinned slot layout and the full-occupancy reporting rows for this host."""
    profile = manifest["reference_load_profile"]
    for key in ("plan", "end_evidence"):
        E.require(profile.get(key) in manifest["files"], "Reporting profile source must be SHA-pinned: " + key)
    E.require(manifest["profile"] == "fleet-reference", "END requires the reviewed fleet-reference bundle profile")
    E.require(manifest["files"][profile["end_evidence"]] == spec["end_evidence_sha256"]
              == L.sha(Path(bundle) / profile["end_evidence"]),
              "Bundle-pinned END evidence is not the committed K4S END evidence")
    evidence = E.end_evidence(spec["end_evidence"], spec["end_evidence_sha256"], spec["repository"], fleet_end)
    plan = evidence["plan"]
    E.require(manifest["files"][profile["plan"]] == evidence["plan_sha256"] == L.sha(Path(bundle) / profile["plan"]),
              "Bundle reporting plan is not the committed K4S plan")
    E.require(host["system"] == "Linux" and host["sched_other"] is True, "END requires Linux SCHED_OTHER")
    layout = fleet_profile.slot_layout(profile, plan, host["node"], host["nice"])
    reporting = fleet_end.host_reporting(evidence, profile, plan)
    return profile, plan, layout, evidence, reporting


def corpus_loop(backend, manifest, ready, stop, slot_index):
    """The frozen fleet_corpus_worker work loop, verbatim (all four own-tier corpora, rotated by slot)."""
    from receipts import TIERS
    lap = slot_index
    while not stop.is_set():
        order = TIERS[lap % 4:] + TIERS[:lap % 4]
        for offset in range(0, max(len(manifest["sets"]["speed"][t]) for t in TIERS), 50):
            for tier in order:
                for identity in manifest["sets"]["speed"][tier][offset:offset + 50]:
                    if stop.is_set():
                        return
                    backend.work(backend.by_id[identity], tier)
                    ready.set()
        lap += 1


def k4s_corpus_worker(bundle, root, native, ready, stop, cpus, slot_index, errors, spec, hooks=None):
    """One complete K4S reporting background slot (spawned)."""
    hooks = FrozenHooks() if hooks is None else hooks
    backend = None
    try:
        manifest = hooks.validate_bundle(bundle, root)
        _, (fleet_end, fleet_profile, _) = frozen_helpers(spec, root)
        _, _, (_, background, _), _, _ = k4s_reporting_profile(bundle, manifest, spec, hooks.host(), fleet_end,
                                                               fleet_profile)
        E.require(list(cpus) in background, "Background mask absent from pinned reporting slot layout")
        hooks.set_affinity(cpus)
        backend = hooks.backend(bundle, root, native)
        backend.search_cpus = list(cpus)
        corpus_loop(backend, manifest, ready, stop, slot_index)
    except BaseException:
        if errors is not None:
            errors.put(dict(slot=slot_index, error=traceback.format_exc()))
        raise
    finally:
        if backend is not None:
            backend.close()


_CLASS = {}


def background_class():
    """The frozen FleetBackground subclass, created on first use: the frozen replay_load module is imported only
    after the caller verified its pin (end_reference: frozen_helpers; never at this module's import)."""
    if "class" not in _CLASS:
        from replay_load import FleetBackground   # frozen, read only

        class K4SFleetBackgroundClass(FleetBackground):
            """All other reporting slots under K4S evidence; the frozen FleetBackground lifecycle, unchanged."""

            def __init__(self, bundle, root, native, masks, spec, hooks=None):
                import multiprocessing as mp
                context = mp.get_context("spawn")
                self.stop = context.Event()
                self.errors = context.Queue()
                self.readies = [context.Event() for _ in masks]
                self.workers = [context.Process(target=k4s_corpus_worker,
                                                args=(bundle, root, native, ready, self.stop, mask, index, self.errors,
                                                      spec, hooks))
                                for index, (mask, ready) in enumerate(zip(masks, self.readies))]
                self.ready_timeout = 600
        _CLASS["class"] = K4SFleetBackgroundClass
    return _CLASS["class"]


def K4SFleetBackground(bundle, root, native, masks, spec, hooks=None):  # noqa: N802 (constructor-style factory)
    return background_class()(bundle, root, native, masks, spec, hooks)
