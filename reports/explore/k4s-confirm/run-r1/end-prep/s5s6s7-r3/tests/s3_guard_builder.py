"""Test-only builder (END-FULL-F2 integration): REAL S3 guard jobs from the Part A candidate, unmodified.

  python -B s3_guard_builder.py PARTA_DIR WORK OUT_JSON

Verifies PARTA_DIR/SHA256SUMS, copies the Part A package into WORK/parta (Part A is never written), imports its own
test world (tests/conftest.py: a synthetic origin, S9 prepare-clone full clone, file:// only), runs S1b against its
namespaced fake hosts, then s3_guard_job.build for 127x03 -pf00 and -rd00-a00 and 127x04 -pf00 exactly as Part A's own
fixtures do, re-verifies each with s3_guard_job.verify, and writes OUT_JSON: {parta, jobs: {name: {out, job, path,
manifest_sha256, host}}, q3_commits, bindings}. WORK (under /tmp: S3 refuses /dev/shm output roots) is left for the
caller, who removes it. Nothing here reads a real repository, host or outcome.
"""
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile


def verify_sums(parta):
    with open(os.path.join(parta, "SHA256SUMS")) as stream:
        rows = [line.split(None, 1) for line in stream if line.strip()]
    for digest, name in rows:
        name = name.strip().lstrip("*")
        with open(os.path.join(parta, name), "rb") as stream:
            if hashlib.sha256(stream.read()).hexdigest() != digest:
                raise SystemExit("Part A SHA256SUMS mismatch: " + name)
    return len(rows)


def main(parta, work, out_json):
    sums = verify_sums(parta)
    pkg = os.path.join(work, "parta")
    shutil.copytree(parta, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    sys.path[:0] = [pkg, os.path.join(pkg, "tests")]
    spec = importlib.util.spec_from_file_location("parta_conftest", os.path.join(pkg, "tests", "conftest.py"))
    PC = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(PC)
    world_dir = os.path.realpath(tempfile.mkdtemp(prefix="world-", dir=work))
    world = PC._world(world_dir)
    base = tempfile.mkdtemp(prefix="s1b-", dir=world.work)
    fake = PC.FakeHosts(base)
    for host in PC.HOSTS:
        job = fake.path(host, "%s/%s" % (PC.S1B.JOB_ROOTS[host], PC.S1B.NAMESPACE))
        for name, data in PC.admissions(host).items():
            PC.make_file(os.path.join(job, name), data)
    PC.S1B.SSH_BINARY = fake.ssh
    dest = os.path.join(base, "dest")
    PC.S1B.run(PC.s1b_args(world, dest), log=lambda *a: None)
    manifest = os.path.join(dest, "s1b-admissions-manifest.json")
    s1b = dict(dest=dest, manifest=manifest, sha=PC.sha(PC.read(manifest)))
    jobs = {}
    for key, host, kw in (("03-pf00", "127x03", dict(preflight="00")), ("03-rd00-a00", "127x03", dict()),
                          ("04-pf00", "127x04", dict(preflight="00"))):
        out = os.path.join(tempfile.mkdtemp(prefix="g-", dir=world.work), "guard")
        built = PC.S3.build(PC.s3_args(world, s1b, out, host=host, **kw), log=lambda *a: None)
        policy = PC.si.Policy(PC.C.local_host(), PC.S3.verify_roles("s3", out, built["job_name"]))
        PC.S3.verify(policy, "s3", out, built["job_name"], built["_sha256"], log=lambda *a: None)
        jobs[key] = dict(out=out, job=built["job_name"], path=os.path.join(out, built["job_name"]), host=host,
                         manifest_sha256=built["_sha256"], commit_proofs=built["commit_proofs"])
    doc = dict(parta=parta, parta_sums=sums, s3_sha256=hashlib.sha256(open(os.path.join(parta, "s3_guard_job.py"),
                                                                           "rb").read()).hexdigest(),
               jobs=jobs, q3_commits=list(PC.S3.Q3_COMMITS), bindings=[b["commit"] for b in PC.S3.BINDINGS],
               python=sys.version.split()[0])
    with open(out_json, "x") as stream:
        json.dump(doc, stream, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
