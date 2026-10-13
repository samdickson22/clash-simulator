#!/usr/bin/python3
"""Runner: production S4 (b3-r7) bundle builds on 05 into end-staging/bundles/ (IR-03: 03 bus only). Sequential;
stops at the first refusal. Admission SHAs from the A1b S1b manifest (64c2fc8d)."""
import hashlib, json, os, subprocess, sys, time
ST = "/mpac/sdicks02/k4s-runner/run-r1/end-staging"
EP = "/mpac/sdicks02/k4s-runner/run-r1/end-prep"
S4 = EP + "/b3-r7/assemble_fleet_reference.py"
REPO = EP + "/repo-full"
PY = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
ADM = "reports/explore/k4s-confirm/end-guard-admissions/{host}-{name}"
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
s1b = json.load(open(EP + "/admissions-copy-r1/s1b-admissions-manifest.json"))
bus = {f["host"]: f["local_sha256"] for f in s1b["files"] if f["name"] == "system-bus-admission.json"}
jobs = [(h, t, (EP + "/b3-r7/requests-ir03" if h == "127x03" else ST + "/requests") + "/request-%s-%s.json" % (h, t))
        for h in ("127x03", "127x04") for t in ("pf00", "rd00-a00", "rd00-a01")]
out = []
for host, tag, req in jobs:
    dest = ST + "/bundles/end-ref-%s-%s" % (host, tag)
    argv = [PY, "-I", "-B", S4, "--request", req, "--request-sha256", sha(req), "--repository", REPO,
            "--committed-admission", "system-bus-admission.json", ADM.format(host=host, name="system-bus-admission.json"),
            bus[host], "--out", dest]
    t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    p = subprocess.run(["nice", "-n", "19", "taskset", "-c", "8-15", *argv], cwd="/tmp",
                       env=dict(PATH="/usr/bin:/bin", HOME="/home/sdicks02", LANG="C.UTF-8"), capture_output=True, text=True)
    row = dict(host=host, tag=tag, request=req, request_sha256=sha(req), rc=p.returncode, started_utc=t0,
               finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), stderr_tail=p.stderr[-600:], out=dest)
    if p.returncode == 0:
        for f in ("tiers-pins.json", "assembly-receipt.json"):
            if os.path.exists(os.path.join(dest, f)): row[f] = sha(os.path.join(dest, f))
    out.append(row); print(json.dumps(row)[:400], flush=True)
    if p.returncode != 0: break
json.dump(dict(s4_sha256=sha(S4), rows=out), open(ST + "/r4-rebuild/BUNDLES-r4.json", "x"), indent=1)
