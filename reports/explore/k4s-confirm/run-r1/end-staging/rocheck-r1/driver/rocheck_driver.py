"""rocheck-r1 driver: S5 (k4s_end_preflight.preflight) pre-hold steps on 05 with the REAL native/corpus/bundle,
imported from the read-only runtime copy exactly as S5 does (Frozen: sys.path order + import order).

Replicated in preflight() order (k4s_end_preflight.py:756-879):
  frozen_namespace -> state(stop Event) -> frozen_helpers -> frozen_identity -> guard_tools -> [bundle_parity SKIP]
  -> [guard_job_fresh SKIP] -> reporting_profile -> physical_cpus -> [end_job SKIP, as in S5] -> backend_and_corpus
  -> spawn Arrays/Pipe -> topology -> [reference_monitor + guard_admission SKIP: host-specific 127x03 dbus/identity]
  -> K4SFleetBackground (ONE background mask) to readiness -> exit (stop + join) -> cleanup_steps.
NEVER measure(), pool_context, producer_claim, K4SStore, registry or claim.

usage: python -B rocheck_driver.py PREFLIGHT_PY BASE STEPLOG
"""
import importlib.util
import json
import os
import sys
import time
import traceback

PREFLIGHT_SHA256 = "c779345116c1bf6c0ab28af8751a36489642c5b9c870326f516361f54bf115f5"   # TOOLS-FINAL
HOST_BASE = "/mpac/sdicks02/jobs/clasher/k4s-end-r1"


def main(preflight_py, base, steplog):
    log = open(steplog, "a")

    def step(name, **detail):
        log.write(json.dumps(dict(step=name, t=time.time(), **detail), default=repr) + "\n")
        log.flush()
        print("STEP", name, json.dumps(detail, default=repr)[:400], flush=True)

    import hashlib
    data = open(preflight_py, "rb").read()
    if hashlib.sha256(data).hexdigest() != PREFLIGHT_SHA256:
        raise SystemExit("preflight copy is not the TOOLS-FINAL bytes")
    spec_ = importlib.util.spec_from_file_location("k4s_end_preflight", preflight_py)
    PF = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(PF)
    step("preflight-module", sha256=PREFLIGHT_SHA256)

    argv = json.load(open(os.environ["ROCHECK_LAUNCH_ARGV"]))
    run_args = argv[argv.index("run"):]
    run_args = [x.replace(HOST_BASE, base) for x in run_args]
    a = PF.parser().parse_args(run_args)
    step("args", argv=run_args)

    runtime = str(a.runtime_root)
    corpus_inventory = json.loads(open(a.corpus_inventory, "rb").read())
    if hashlib.sha256(open(a.corpus_inventory, "rb").read()).hexdigest() != a.corpus_inventory_sha256:
        raise SystemExit("corpus inventory sha mismatch")

    # frozen_import (k4s_end_preflight.py:1093-1094): Frozen(runtime_root), verbatim.
    F = PF.Frozen(a.runtime_root)
    step("frozen_import", modules=sorted(PF.runtime_modules(runtime)))

    import multiprocessing as mp
    from types import SimpleNamespace
    r = PF.frozen_namespace(a, F)
    state = SimpleNamespace(stop=mp.get_context("spawn").Event(), monitor=None, channel=None, monitor_channel=None,
                            backend=None)
    primary = None
    try:
        spec = F.G.evidence_spec(r.end_evidence, r.end_evidence_sha256, r.repository, r.k4s_manifest,
                                 r.k4s_manifest_sha256)
        _, (fleet_end, fleet_profile, fleet_validity) = F.G.frozen_helpers(spec, r.runtime_root)
        step("frozen_helpers")
        T = F.bundle_tools()
        manifest, pins, host_pins = F.ER.frozen_identity(r, T.validate_bundle, T.NATIVE_SHA)
        PF.require(pins["native_sha256"] == PF.NATIVE_SHA256 and r.corpus_sha256 == PF.CORPUS_SHA256,
                   "Frozen native/corpus identity differs from the K4S END identities")
        step("frozen_identity", native_sha256=pins["native_sha256"], corpus_sha256=r.corpus_sha256,
             host_pins=host_pins)
        W = F.guard_tools()
        step("guard_tools")
        step("bundle_parity", skipped="compare bundle not staged on 05 (pure manifest comparison, no write path)")
        step("guard_job_fresh", skipped="guard job is host-specific (127x03 Q4 guard parent)")
        host_identity = F.G.FrozenHooks().host()
        profile, plan, (search, background_masks, census_cpu), evidence, reporting = \
            F.G.k4s_reporting_profile(r.bundle, manifest, spec, host_identity, fleet_end, fleet_profile)
        PF.require(host_pins["bundle_profile_host"] == host_identity["node"], "Bundle reference profile host")
        step("reporting_profile", host=host_identity, search=search, background_masks=background_masks,
             census_cpu=census_cpu, reporting_rows=len(reporting))
        try:
            W.validate_physical_cpus(search + sum(background_masks, []) + [census_cpu])
            step("physical_cpus", passed=True)
        except Exception:
            step("physical_cpus", passed=False, error=traceback.format_exc()[-1500:])
        os.sched_setaffinity(0, set(search))           # shimmed: logged no-op on 05
        r.cores = search
        step("end_job_read_only", skipped="as in S5 (no --end-job-sha256 in the launch argv)")
        be = state.backend = F.ER.backend(r)
        ids = F.L.check_corpus(r.corpus_sha256, r.corpus_sha256, corpus_inventory, None, list(be.k4s_rows))
        step("backend_and_corpus", corpus_states=len(ids))
        context = mp.get_context("spawn")
        stop, phase = state.stop, context.Array("c", 64)
        owned = context.Array("i", [os.getpid()] + [0] * (len(background_masks) + 1))
        channel, monitor_channel = state.channel, state.monitor_channel = context.Pipe()
        try:
            clusters = W.validate_topology(manifest["topology"], W.cpu_counters(), darwin=False)
            step("topology", passed=True, clusters=len(clusters) if hasattr(clusters, "__len__") else repr(clusters))
        except Exception:
            step("topology", passed=False, error=traceback.format_exc()[-1500:])
        step("guard_admission", skipped="reference_monitor/admission host-specific (127x03 dbus/identity)")
        phase.value = b"reference-warmup"
        masks = background_masks[:1]
        step("background_start", masks=masks, of=len(background_masks))
        load = F.G.K4SFleetBackground(r.bundle, r.runtime_root, r.native, masks, spec)
        load.check_external = lambda: None           # the skipped monitor's liveness check
        t0 = time.monotonic()
        with load as background:
            for index, worker in enumerate(background.workers, 1):
                owned[index] = worker.pid
            step("background_ready", workers=len(background.workers), pids=[w.pid for w in background.workers],
                 seconds=time.monotonic() - t0,
                 background_affinity=[sorted(os.sched_getaffinity(w.pid)) for w in background.workers],
                 background_nice_seen_through_shim=[os.getpriority(os.PRIO_PROCESS, w.pid) for w in background.workers])
            # S5 would now begin "loaded_hold"; this check stops here.
        step("background_closed", exitcodes=[w.exitcode for w in load.workers])
    except BaseException as error:
        primary = error
        step("FAILED", error=traceback.format_exc())
        raise
    finally:
        try:
            F.ER.cleanup_steps(state)
            step("cleanup", passed=True)
        except BaseException:
            step("cleanup", passed=False, error=traceback.format_exc()[-2000:])
            if primary is None:
                raise
    step("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:4]))
