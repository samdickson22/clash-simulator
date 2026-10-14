"""Classify every audited write/raise/info event and diff the before/after inventories.
usage: python3 -I analyze.py BASE TRACELOG_DIR INV_BEFORE INV_AFTER OUT.json"""
import collections
import glob
import json
import sys

base, tracedir, before_p, after_p, out_p = sys.argv[1:6]
TREES = {"runtime": base + "/runtime-98566c032d0b", "bundle": base + "/bundles/end-ref-127x03-pf00",
         "bundles-parent": base + "/bundles", "end-inputs": base + "/end-inputs-r1", "repository": base + "/repository",
         "base": base}
HARNESS = (tracedir + "/", base.rsplit("/", 1)[0] + "/logs/")


def where(path):
    if not isinstance(path, str) or not path.startswith("/"):
        return "non-path"
    for name in ("runtime", "bundle", "end-inputs", "repository", "bundles-parent", "base"):
        root = TREES[name]
        if path == root or path.startswith(root + "/"):
            return "INSIDE:" + name
    if path.startswith(HARNESS):
        return "harness-log"
    return "outside"


events, starts, exits = [], {}, {}
for f in sorted(glob.glob(tracedir + "/audit-*.jsonl")):
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            e = dict(kind="corrupt-line", raw=line[:300])
        if e.get("kind") == "start":
            starts[e["pid"]] = e
        elif e.get("kind") == "exit":
            exits[e["pid"]] = e
        else:
            events.append(e)

writes = []
for e in events:
    if e.get("kind") != "write":
        continue
    paths = [e["path"]] if "path" in e else e.get("paths", [])
    for p in paths:
        if isinstance(p, str) and p.startswith("fd:"):
            loc = "fd:" + ("pipe/socket/anon" if ("pipe:" in p or "socket:" in p or "anon_inode" in p)
                           else where(p.split("->", 1)[1]))
        else:
            loc = where(p)
        writes.append(dict(loc=loc, path=p, event=e["event"], pid=e["pid"], mode=e.get("mode"), flags=e.get("flags"),
                           frame=(e.get("stack") or ["?"])[0], stack=e.get("stack")))

inside = [w for w in writes if w["loc"].startswith("INSIDE") or w["loc"].startswith("fd:INSIDE")]
raises = [e for e in events if e.get("kind") == "raise"]
infos = collections.Counter((e["event"]) for e in events if e.get("kind") == "info")
execs = [dict(pid=e["pid"], event=e["event"], args=e["args"][:2]) for e in events
         if e.get("kind") == "info" and e["event"] in ("subprocess.Popen", "os.exec", "os.posix_spawn", "os.system")]
shims = collections.Counter(e["event"] for e in events if e.get("kind") == "shim")

before, after = json.load(open(before_p)), json.load(open(after_p))
diff = {}
for root in sorted(set(before) | set(after)):
    b, a = before.get(root, {}), after.get(root, {})
    d = dict(added=sorted(set(a) - set(b)), removed=sorted(set(b) - set(a)),
             changed=sorted(k for k in set(a) & set(b) if a[k] != b[k]))
    d["changed_detail"] = {k: dict(before=b[k], after=a[k]) for k in d["changed"][:50]}
    diff[root] = d

pids = collections.defaultdict(set)
counts = collections.Counter()
for w in writes:
    if w["loc"].startswith("INSIDE") or w["loc"].startswith("fd:INSIDE"):
        continue
    k = (w["loc"], w["event"], str(w["path"]), w["frame"])
    counts[k] += 1
    pids[k].add(w["pid"])
grouped_outside = sorted(({"loc": k[0], "event": k[1], "path": k[2], "frame": k[3], "count": n, "pids": sorted(pids[k])}
                          for k, n in counts.items()), key=lambda r: (r["loc"], r["path"]))

summary = dict(
    processes=sorted((dict(pid=p, ppid=s["ppid"], argv=s["argv"][:3], cwd=s["cwd"],
                          exited=p in exits, read_opens=exits.get(p, {}).get("read_opens")) for p, s in starts.items()), key=lambda d: d["pid"]),
    write_events_total=len(writes),
    by_location=collections.Counter(w["loc"] for w in writes),
    inside_writes=inside,
    outside_writes_grouped=grouped_outside,
    raises=[dict(pid=e["pid"], errno=e["errno"], error=e["error"], filename=e["filename"], loc=where(
        e["filename"]) if str(e["filename"]).startswith("/") else "relative", stack=e["stack"][:4]) for e in raises],
    info_counts=infos, execs=execs, shim_counts=shims,
    corrupt=[e for e in events if e.get("kind") == "corrupt-line"],
    inventory_diff=diff,
    inventory_diff_empty=all(not d["added"] and not d["removed"] and not d["changed"] for d in diff.values()),
)
with open(out_p, "x") as f:
    json.dump(summary, f, indent=1, sort_keys=True, default=repr)
print(json.dumps(dict(by_location=summary["by_location"], inside=len(inside), raises=len(raises),
                      diff_empty=summary["inventory_diff_empty"], processes=len(starts)), default=repr))
