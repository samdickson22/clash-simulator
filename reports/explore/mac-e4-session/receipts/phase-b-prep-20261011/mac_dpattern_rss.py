"""Offline (05, nice 19, one core) peak-RSS estimate for the Mac TIERS D-pattern under TIERS Amendment 3.
Main process = one TierBackend for the whole session, which retains policy inputs (the Mac retains
sets.agreement, >=2000) and looks up every state once, as D1-D9 do. D6 = a spawned forward_worker child
that builds its own TierBackend while main stays resident. Uses the implementer's verified END-like
bundle (rss-bundle-r4, 1,325 rows, fleet profile, sets.agreement empty), so retention is measured on the
1,200 speed rows and scaled linearly to 2,000. No timing, no outcomes, no Mac access."""
import gc, json, multiprocessing as mp, os, resource, sys, time
from pathlib import Path
RT = Path("/mpac/sdicks02/jobs/clasher/t1-20261010-r1/end-bundle-preparation-r1/runtime")
PKG = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-worktree/reports/strategy_council_20260928/live-loop/v4/mac-e4-package/e4v3")
BUNDLE = Path("/mpac/sdicks02/jobs/clasher/e4-amendment3-loader-20261011/rss-bundle-r4")
NATIVE = Path("/mpac/sdicks02/jobs/clasher/e4v3-20261010-r1/native/clasher_core.abi3.so")
OUT = Path(sys.argv[1])

def setup():
    sys.path[:0] = [str(RT / "imitation/evaluation/runtime_dependencies"), str(RT / "reports/strategy_council_20260928/imitation"), str(PKG)]

def status():
    f = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        k, _, v = line.partition(":")
        if k in ("VmRSS", "VmHWM", "RssAnon", "RssFile"):
            f[k] = int(v.split()[0]) * 1024
    return f

def child(queue):
    setup()
    from tier_backend import TierBackend
    b = TierBackend(BUNDLE, RT, NATIVE)
    s = status(); b.close(); queue.put(dict(after_construction=s, final=status()))

if __name__ == "__main__":
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19 and len(os.sched_getaffinity(0)) == 1
    setup()
    from tier_backend import TierBackend
    t = time.monotonic(); b = TierBackend(BUNDLE, RT, NATIVE); built = time.monotonic() - t
    r = dict(construct_seconds=built, after_construction=status())
    ids = [i for tier in ("K0c", "S", "K2", "K4") for i in b.manifest["sets"]["speed"][tier]]
    gc.collect(); base = status()["RssAnon"]
    kept = {i: b.policy_input(b.by_id[i]) for i in ids}
    gc.collect(); r["retained_inputs"] = len(kept); r["after_retaining"] = status()
    each = (r["after_retaining"]["RssAnon"] - base) / len(kept)
    r["retained_bytes_each"] = each
    for i in b.manifest["sets"]["golden"] + ids:
        row = b.by_id[i]; del row
    r["after_full_lookup"] = status()
    ctx = mp.get_context("spawn"); q = ctx.Queue(); p = ctx.Process(target=child, args=(q,)); p.start()
    c = q.get(timeout=900); p.join(60); r["d6_child"] = c; r["main_during_child"] = status()
    main_anon = r["main_during_child"]["RssAnon"] + each * (2000 - len(kept))
    child_peak = c["after_construction"]["VmHWM"] + each * 2000
    r["mac_estimate_bytes"] = dict(
        main_resident_with_agreement2000=main_anon,
        main_peak_vmhwm_plus_extra_retention=r["after_full_lookup"]["VmHWM"] + each * (2000 - len(kept)),
        d6_child_peak_with_agreement2000=child_peak,
        concurrent_main_plus_d6_child_peak=main_anon + child_peak,
        note="Linux RSS on 05 as a proxy for macOS; excludes the perception worker (torch/ultralytics v3 on MPS) and the monitor")
    r["maxrss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    r["tier_backend_sha256"] = __import__("hashlib").sha256((PKG / "tier_backend.py").read_bytes()).hexdigest()
    r.update(host=os.uname().nodename, nice=19, cpus=sorted(os.sched_getaffinity(0)), outcomes_read=False, timing=False)
    b.close()
    OUT.write_text(json.dumps(r, indent=1, sort_keys=True) + "\n"); print(json.dumps(r["mac_estimate_bytes"]))
