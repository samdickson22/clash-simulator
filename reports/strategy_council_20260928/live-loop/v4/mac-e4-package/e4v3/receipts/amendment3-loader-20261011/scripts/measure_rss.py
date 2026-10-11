"""One offline TierBackend: memory after construction (T1's 20:33Z method) and after a bounded lookup probe."""
import json, os, sys, time, resource, gc
sys.path.insert(0, os.path.dirname(__file__))
from common import *
mode = sys.argv[1]
prepare(OLD if mode.startswith("before") else NEW)
from tier_backend import TierBackend
started = time.monotonic()
backend = TierBackend(BUNDLE, RT, NATIVE)
built = time.monotonic() - started
after_init = status()
manifest = backend.manifest
probe = dict(lookups=0)
lookup, admission, both = [], [], []
# Same sequence in both modes: golden rows, then all four 300-state tier corpora; each is looked
# up and admitted (prepare_work) exactly as before a decision timer. Untimed by the session.
start = time.monotonic()
for identity in manifest["sets"]["golden"] + [i for t in ("K0c", "S", "K2", "K4") for i in manifest["sets"]["speed"][t]]:
    t0 = time.monotonic(); row = backend.by_id[identity]; t1 = time.monotonic()
    if "belief_before" in row:  # golden125 rows are exactness-only (no admission)
        backend.prepare_work(row); t2 = time.monotonic(); backend.prepared_work = None
        admission.append(t2 - t1); both.append(t2 - t0)
    del row
    lookup.append(t1 - t0); probe["lookups"] += 1
probe["seconds"] = time.monotonic() - start
def q(v):
    v = sorted(v); return dict(median=v[len(v)//2], p90=v[int(.9*(len(v)-1))], p99=v[int(.99*(len(v)-1))], max=v[-1])
probe["lookup_seconds"], probe["admission_seconds"] = q(lookup), q(admission)
probe["lookup_plus_admission_seconds"] = q(both)
if mode.startswith("after"):
    # Mac sizing: resident cost of retained policy inputs (Mac keeps agreement2000 of them).
    gc.collect(); before = status()["RssAnon"]
    kept = [backend.policy_input(backend.by_id[i]) for i in manifest["sets"]["speed"]["S"][:200]]
    gc.collect(); probe["retained_input_bytes_each"] = (status()["RssAnon"] - before) / len(kept)
    del kept
after_probe = status()
gc.collect()
result = dict(mode=mode, host=os.uname().nodename, nice=os.getpriority(os.PRIO_PROCESS, 0), cpus=sorted(os.sched_getaffinity(0)),
              rows=len(backend.rows), inputs_retained=len(backend.inputs), construct_seconds=built,
              after_construction=after_init, after_probe=after_probe, probe=probe,
              maxrss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              tier_backend_sha256=__import__("hashlib").sha256(Path(sys.modules["tier_backend"].__file__).read_bytes()).hexdigest(),
              outcomes_read=False, timing=False)
backend.close()
print(json.dumps(result, sort_keys=True), flush=True)
(W / ("rss-" + mode + ".json")).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
