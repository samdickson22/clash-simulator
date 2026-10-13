#!/usr/bin/python3
"""b3-r6 production proof driver (05 only, offline): runs the b3-r6 S4 on each real request, one at a time, into a
fresh tempdir; records rc, stderr summary, tiers-pins sha, receipt sha + assembler_sha256; then deletes the bundle."""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time
E = "/mpac/sdicks02/k4s-runner/run-r1/end-staging"
S4 = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/b3-r6/assemble_fleet_reference.py"
REPO = "/mpac/sdicks02/k4s-runner/run-r1/end-prep/repo-full"
PY = "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python"
ADM = "reports/explore/k4s-confirm/end-guard-admissions/{host}-{name}"
base = sys.argv[1]                       # scratch parent (a mkdtemp)
out_json = sys.argv[2]
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
meta = json.load(open(E + "/requests/make_requests.out.json"))
results = []
for path in sorted(meta["requests"]):
    r = meta["requests"][path]
    name = os.path.basename(path)[len("request-"):-len(".json")]
    req_sha = sha(path)
    row = dict(request=os.path.basename(path), request_sha256=req_sha, request_sha_matches_out_json=req_sha == r["sha256"],
               host=r["host"], s4_sha256=sha(S4), started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    argv = [PY, "-I", "-B", S4, "--request", path, "--request-sha256", req_sha, "--repository", REPO]
    for adm, asha in sorted(r["admissions"].items()):
        argv += ["--committed-admission", adm, ADM.format(host=r["host"], name=adm), asha]
    out = os.path.join(base, "end-ref-" + name)
    argv += ["--out", out]
    env = dict(PATH="/usr/bin:/bin", HOME="/home/sdicks02", LANG="C.UTF-8")
    p = subprocess.run(["nice", "-n", "19", "taskset", "-c", "8-15", *argv], cwd="/tmp", env=env, capture_output=True, text=True)
    row.update(rc=p.returncode, stdout_bytes=len(p.stdout), stderr=p.stderr.strip()[-2000:],
               finished_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    if p.returncode == 0:
        tp = os.path.join(out, "tiers-pins.json")
        row["tiers_pins_sha256"] = sha(tp)
        row["tiers_pins_sha256_file"] = open(os.path.join(out, "tiers-pins.sha256")).read().strip()
        row["assembly_receipt_sha256"] = sha(os.path.join(out, "assembly-receipt.json"))
        rec = json.load(open(os.path.join(out, "assembly-receipt.json")))
        row["receipt"] = {k: rec[k] for k in ("assembler_sha256", "safe_input_sha256", "manifest_sha256", "files",
                                              "host", "guard_job", "repository_head", "production_pins", "status")}
        man = json.load(open(tp))
        row["runtime_files"] = len(man["runtime_files"])
        row["runtime_files_canonical_sha256"] = hashlib.sha256(json.dumps(man["runtime_files"], sort_keys=True,
                                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        row["bundle_bytes"] = sum(os.lstat(os.path.join(d, f)).st_size for d, _, fs in os.walk(out) for f in fs)
    row["status"] = "PASS" if p.returncode == 0 else "FAIL"
    for victim in (out, out + ".partial"):
        if os.path.lexists(victim):
            for d, ds, fs in os.walk(victim):
                os.chmod(d, 0o755)
            shutil.rmtree(victim)
    row["deleted"] = not os.path.lexists(out) and not os.path.lexists(out + ".partial")
    results.append(row)
    json.dump(results, open(out_json, "w"), indent=1, sort_keys=True)
    print(row["request"], row["status"], row.get("tiers_pins_sha256"), flush=True)
