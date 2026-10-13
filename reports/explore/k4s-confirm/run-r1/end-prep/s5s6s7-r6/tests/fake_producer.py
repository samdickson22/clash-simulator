"""Stand-in for end_reference.py / k4s_end_preflight.py in wrapper tests. FAKE_MODE = complete | failed | preclaim |
claim-only | preflight | claim-in-preflight | sleep. Claims and seals use the frozen formats (end_evidence.claim_attempt;
K4SStore). FAKE_ENV_DUMP: write the GIT_* environment it received. FAKE_PLANT=<name>: before exiting, hard-link
$FAKE_CANARY as <job>/<name> (a foreign inode the wrapper must never write through). FAKE_CLAIM_LINK: make the
claim a hard link to $FAKE_CANARY. Writes only under the test's tmp paths."""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import Store, canonical  # noqa: E402

args = sys.argv[1:]
opt = {args[i]: args[i + 1] for i in range(len(args) - 1) if args[i].startswith("--")}
mode = os.environ.get("FAKE_MODE", "complete")
host = os.environ["FAKE_HOST"]
if os.environ.get("FAKE_ENV_DUMP"):
    with open(os.environ["FAKE_ENV_DUMP"], "x") as stream:
        json.dump({k: v for k, v in os.environ.items() if k.startswith("GIT_")}, stream, sort_keys=True)
out = Path(opt["--out"])


def plant():
    if os.environ.get("FAKE_PLANT"):
        os.link(os.environ["FAKE_CANARY"], out.parent / os.environ["FAKE_PLANT"])


if mode == "sleep":
    time.sleep(float(os.environ.get("FAKE_SLEEP", "3")))
    sys.exit(0)
if mode == "preclaim":
    print("PreconditionRefusal: before the claim", file=sys.stderr)
    plant()
    sys.exit(1)
repository = Path(opt["--repository"])
if mode in ("preflight", "claim-in-preflight"):
    if mode == "claim-in-preflight":
        reg = repository / "reports/explore/k4s-confirm/end/registry/round-00" / host
        reg.mkdir(parents=True, exist_ok=True)
        (reg / "attempt-00.json").write_text("{}\n")
    store = Store(out, "K4S-END-PREFLIGHT")
    store.write("preflight-result.json", dict(passed=True))
    store.seal("passed")
    plant()
    sys.exit(0)
reg = repository / "reports/explore/k4s-confirm/end/registry" / ("round-%02d" % int(opt["--round"])) / host
reg.mkdir(parents=True, exist_ok=True)
index = len(list(reg.iterdir()))
claim = dict(schema="clasher.k4s.end-attempt-claim.v2", job_sha256="a" * 64, end_evidence_sha256="b" * 64,
             round=int(opt["--round"]), host=host, attempt=index, receipt_directory=out.name,
             launched_utc=time.time(), pid=os.getpid(), nonce="c" * 32)
data = (canonical(claim) + "\n").encode()
target = reg / ("attempt-%02d.json" % index)
if os.environ.get("FAKE_CLAIM_LINK"):
    os.link(os.environ["FAKE_CANARY"], target)
else:
    with target.open("xb") as stream:
        stream.write(data)
if mode == "claim-only":
    plant()
    sys.exit(1)
store = Store(out, "K4S-END-REFERENCE")
store.write("attempt-claim.json", dict(claim=claim, claim_sha256=hashlib.sha256(data).hexdigest()))
store.write("guard-admission.json", dict(utc=time.time(), event="admit"))
store.write("end-raw.json", dict(synthetic_raw=True))
for extra in filter(None, os.environ.get("FAKE_EXTRA", "").split(",")):
    store.write(extra, dict(synthetic=True))
plant()
if mode == "complete":
    store.write("end-complete.json", dict(completed=True, cleanup_succeeded=True))
    store.seal("complete")
    sys.exit(0)
store.write("failure.json", dict(error="x", fail_closed=True))
store.seal("failed")
sys.exit(1)
