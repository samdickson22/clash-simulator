#!/usr/bin/python3
"""b3-r7 production proof driver (05 only, offline): runs the b3-r7 S4 on the six real requests (127x03: the IR-03
rewrites in requests-ir03/, system bus admission only; 127x04: the unchanged end-staging requests), one at a time,
into a fresh directory under the scratch parent; records rc, stderr summary, tiers-pins sha, receipt sha +
assembler_sha256; then deletes the bundle. Then two IR-03 negative controls with the ORIGINAL (r6-shape) 127x03 pf00
request, both --dry-run (nothing is written): argv binding bus + idle (as in b3-r6), and argv binding the bus only.

  proof_driver_r7.py SCRATCH_PARENT OUT_JSON"""
import hashlib, json, os, shutil, subprocess, sys, time
E = "/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests"
HERE = os.path.dirname(os.path.abspath(__file__))
IR03 = os.path.join(HERE, "requests-ir03")
S4 = os.path.join(HERE, "assemble_fleet_reference.py")
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


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run(path, host, admissions, out, dry_run=False):
    req_sha = sha(path)
    argv = [PY, "-I", "-B", S4, "--request", path, "--request-sha256", req_sha, "--repository", REPO]
    for adm, asha in sorted(admissions.items()):
        argv += ["--committed-admission", adm, ADM.format(host=host, name=adm), asha]
    argv += ["--out", out] + (["--dry-run"] if dry_run else [])
    env = dict(PATH="/usr/bin:/bin", HOME="/home/sdicks02", LANG="C.UTF-8")
    p = subprocess.run(["nice", "-n", "19", "taskset", "-c", "8-15", *argv], cwd="/tmp", env=env, capture_output=True,
                       text=True)
    return req_sha, p


def remove(out):
    for victim in (out, out + ".partial"):
        if os.path.lexists(victim):
            for d, ds, fs in os.walk(victim):
                os.chmod(d, 0o755)
            shutil.rmtree(victim)
    return not os.path.lexists(out) and not os.path.lexists(out + ".partial")


source_meta = json.load(open(E + "/make_requests.out.json"))["requests"]
ir03_meta = json.load(open(IR03 + "/make_requests_ir03.out.json"))["requests"]
plan = sorted((p, r, ir03_meta) for p, r in ir03_meta.items())
plan += sorted((p, r, source_meta) for p, r in source_meta.items() if r["host"] == "127x04")
results = []
for path, r, meta in plan:
    name = os.path.basename(path)[len("request-"):-len(".json")]
    row = dict(request=os.path.relpath(path, HERE) if path.startswith(HERE) else path, host=r["host"],
               committed_admissions=r["admissions"], s4_sha256=sha(S4), started_utc=now())
    out = os.path.join(base, "end-ref-" + name)
    req_sha, p = run(path, r["host"], r["admissions"], out)
    row.update(request_sha256=req_sha, request_sha_matches_out_json=req_sha == r["sha256"], rc=p.returncode,
               stdout_bytes=len(p.stdout), stderr=p.stderr.strip()[-2000:], finished_utc=now())
    if p.returncode == 0:
        tp = os.path.join(out, "tiers-pins.json")
        row["tiers_pins_sha256"] = sha(tp)
        row["tiers_pins_sha256_file"] = open(os.path.join(out, "tiers-pins.sha256")).read().strip()
        row["assembly_receipt_sha256"] = sha(os.path.join(out, "assembly-receipt.json"))
        rec = json.load(open(os.path.join(out, "assembly-receipt.json")))
        row["receipt"] = {k: rec[k] for k in ("assembler_sha256", "safe_input_sha256", "manifest_sha256", "files",
                                              "host", "guard_job", "repository_head", "production_pins", "status",
                                              "committed_admissions")}
        man = json.load(open(tp))
        row["guard_admissions"] = man["reference_load_profile"]["guard"]["admissions"]
        row["bundle_admission_files"] = sorted(n for n in man["files"] if n.startswith("guard-admissions/"))
        row["runtime_files"] = len(man["runtime_files"])
        row["runtime_files_canonical_sha256"] = hashlib.sha256(json.dumps(man["runtime_files"], sort_keys=True,
                                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        row["bundle_bytes"] = sum(os.lstat(os.path.join(d, f)).st_size for d, _, fs in os.walk(out) for f in fs)
    row["status"] = "PASS" if p.returncode == 0 else "FAIL"
    row["deleted"] = remove(out)
    results.append(row)
    json.dump(dict(positive=results), open(out_json, "w"), indent=1, sort_keys=True)
    print(row["request"], row["status"], row.get("tiers_pins_sha256"), flush=True)

# IR-03 negative controls: the original 127x03 pf00 request (guard.admissions = bus + idle), --dry-run
orig = E + "/request-127x03-pf00.json"
negatives = []
for label, adm in (("argv bus + idle (b3-r6 shape)", source_meta[orig]["admissions"]),
                   ("argv bus only", {k: v for k, v in source_meta[orig]["admissions"].items()
                                      if k == "system-bus-admission.json"})):
    out = os.path.join(base, "end-ref-negative-127x03-pf00")
    started = now()
    req_sha, p = run(orig, "127x03", adm, out, dry_run=True)
    last = (p.stderr.strip().splitlines() or [""])[-1]
    negatives.append(dict(control=label, request=orig, request_sha256=req_sha, committed_admissions=adm,
                          started_utc=started, finished_utc=now(), rc=p.returncode, stdout_bytes=len(p.stdout),
                          stderr_last_line=last[-2000:], cites_ir03="ruling IR-03" in last,
                          status="REFUSED-IR03" if p.returncode != 0 and "ruling IR-03" in last else "UNEXPECTED",
                          nothing_written=not os.path.lexists(out) and not os.path.lexists(out + ".partial")))
    json.dump(dict(positive=results, negative=negatives), open(out_json, "w"), indent=1, sort_keys=True)
    print(label, negatives[-1]["status"], flush=True)
