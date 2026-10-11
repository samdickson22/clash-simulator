"""r2b (after Sol review; malloc_trim baseline): offline 05 peak-RSS measurement of the Mac TIERS D-pattern under Amendment 3.
Main: one TierBackend; retains a policy input for every speed row (1,200, the most this bundle has; the
Mac retains its sets.agreement); then, as D1-D9 do, looks up and admits (prepare_work) every golden/speed
row and runs real no-deadline work() decisions on a sample per tier (CPU backend). D6 child (spawned,
concurrent with main): builds its own TierBackend, retains the same 1,200 inputs, and runs a CPU forward
(infer) on each, as forward_worker does. Peaks are reported as measured (VmHWM). Retention is scaled to
the Mac's agreement length only with a positive per-input delta measured in this run; a non-positive
delta is refused, not used. Linux RSS is a proxy for macOS; no timing, no outcomes, no Mac access."""
import gc, json, multiprocessing as mp, os, resource, sys, time
from pathlib import Path
RT = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-bundle-preparation-r1/runtime")
PKG = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-worktree/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3")
BUNDLE = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-loader-20261011/rss-bundle-r4")
NATIVE = Path("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so")
OUT, AGREEMENT, WORK_PER_TIER = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
TIERS = ("K0c", "S", "K2", "K4")

def setup():
    sys.path[:0] = [str(RT / "imitation/evaluation/runtime_dependencies"), str(RT / "reports/strategy_council_20260928/imitation"), str(PKG)]

def status():
    f = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        k, _, v = line.partition(":")
        if k in ("VmRSS", "VmHWM", "RssAnon", "RssFile"):
            f[k] = int(v.split()[0]) * 1024
    return f

def trim():
    gc.collect()
    import ctypes
    ctypes.CDLL("libc.so.6").malloc_trim(0)  # return freed arenas so reuse cannot hide retention growth

def retain(b):
    ids = [i for t in TIERS for i in b.manifest["sets"]["speed"][t]]
    trim(); before = status()["RssAnon"]
    for i in ids:
        b.inputs[i] = b.policy_input(b.by_id[i])
    trim(); after = status()["RssAnon"]
    return ids, (after - before) / len(ids)

def child(queue):
    setup()
    from tier_backend import TierBackend
    b = TierBackend(BUNDLE, RT, NATIVE)
    built = status(); ids, each = retain(b); retained = status()
    for i in ids:
        b.infer(i, "cpu")
    queue.put(dict(after_construction=built, after_retaining=retained, after_forwards=status(), each=each, forwards=len(ids)))
    b.close()

if __name__ == "__main__":
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and len(os.sched_getaffinity(0)) == 1
    setup()
    from tier_backend import TierBackend
    t = time.monotonic(); b = TierBackend(BUNDLE, RT, NATIVE); r = dict(construct_seconds=time.monotonic() - t, after_construction=status())
    ids, each = retain(b); r["after_retaining"] = status(); r["main_retained_bytes_each"] = each
    for i in b.manifest["sets"]["golden"] + ids:
        row = b.by_id[i]
        if "belief_before" in row:
            b.prepare_work(row); b.prepared_work = None
        del row
    r["after_lookup_admission"] = status()
    worked = 0
    for tier in TIERS:
        b.activate(tier)
        for i in b.manifest["sets"]["speed"][tier][:WORK_PER_TIER]:
            b.work(b.by_id[i], tier, backend="cpu"); worked += 1
    r["decisions"] = worked; r["after_decisions"] = status()
    ctx = mp.get_context("spawn"); q = ctx.Queue(); p = ctx.Process(target=child, args=(q,)); p.start()
    c = q.get(timeout=1800); p.join(60); r["d6_child"] = c; r["main_during_child"] = status()
    if each <= 0 or c["each"] <= 0:
        r["refused"] = "Non-positive retention delta; no extrapolation: %r %r" % (each, c["each"])
        OUT.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n")
        raise SystemExit(r["refused"])
    extra_main, extra_child = each * max(0, AGREEMENT - len(ids)), c["each"] * max(0, AGREEMENT - len(ids))
    G = 2 ** 30
    r["mac_estimate_gib"] = dict(agreement_length=AGREEMENT,
        main_peak=(r["after_decisions"]["VmHWM"] + extra_main) / G,
        d6_child_peak=(c["after_forwards"]["VmHWM"] + extra_child) / G,
        concurrent_main_vmrss_plus_child_peak=(r["main_during_child"]["VmRSS"] + extra_main + c["after_forwards"]["VmHWM"] + extra_child) / G,
        excludes="perception worker (torch+ultralytics v3 on MPS), monitor; MPS forward allocations")
    r["maxrss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    r["tier_backend_sha256"] = __import__("hashlib").sha256((PKG / "tier_backend.py").read_bytes()).hexdigest()
    r.update(host=os.uname().nodename, nice=19, cpus=sorted(os.sched_getaffinity(0)), outcomes_read=False, timing=False)
    b.close()
    OUT.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n"); print(json.dumps(r["mac_estimate_gib"]))
