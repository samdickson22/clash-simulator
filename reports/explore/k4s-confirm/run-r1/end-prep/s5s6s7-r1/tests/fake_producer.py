"""Stand-in for end_reference.py in wrapper tests: FAKE_MODE = complete | failed | preclaim | claim-only |
claim-in-preflight | sleep. Claims and seals use the frozen formats (end_evidence.claim_attempt; K4SStore)."""
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
if mode == "sleep":
    time.sleep(float(os.environ.get("FAKE_SLEEP", "3")))
    sys.exit(0)
if mode == "preclaim":
    print("PreconditionRefusal: before the claim", file=sys.stderr)
    sys.exit(1)
repository = Path(opt["--repository"])
if mode == "claim-in-preflight":
    reg = repository / "reports/explore/k4s-confirm/end/registry/round-00" / host
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "attempt-00.json").write_text("{}\n")
    out = Store(opt["--out"], "K4S-END-PREFLIGHT")
    out.write("preflight-result.json", dict(passed=True))
    out.seal("passed")
    sys.exit(0)
out = Path(opt["--out"])
reg = repository / "reports/explore/k4s-confirm/end/registry" / ("round-%02d" % int(opt["--round"])) / host
reg.mkdir(parents=True, exist_ok=True)
index = len(list(reg.iterdir()))
claim = dict(schema="clasher.k4s.end-attempt-claim.v2", job_sha256="a" * 64, end_evidence_sha256="b" * 64,
             round=int(opt["--round"]), host=host, attempt=index, receipt_directory=out.name,
             launched_utc=time.time(), pid=os.getpid(), nonce="c" * 32)
data = (canonical(claim) + "\n").encode()
with (reg / ("attempt-%02d.json" % index)).open("xb") as stream:
    stream.write(data)
if mode == "claim-only":
    sys.exit(1)
import hashlib  # noqa: E402
store = Store(out, "K4S-END-REFERENCE")
store.write("attempt-claim.json", dict(claim=claim, claim_sha256=hashlib.sha256(data).hexdigest()))
store.write("guard-admission.json", dict(utc=time.time(), event="admit"))
if mode == "complete":
    store.write("end-complete.json", dict(completed=True, cleanup_succeeded=True))
    store.seal("complete")
    sys.exit(0)
store.write("failure.json", dict(error="x", fail_closed=True))
store.seal("failed")
sys.exit(1)
