#!/bin/bash
# Unit tests on 05 (nice 19, one core) under Python 3.8 and the e4v3 venv; writes receipts/unit-tests*.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
: "${CLASHER_E4V3:?set CLASHER_E4V3 to the reviewed Amendment 3 e4v3 directory}"
export CLASHER_E4V3 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$HERE/receipts"
cd "$HERE"
nice -n 19 taskset -c 63 python3 -B -m unittest discover -s tests -v > receipts/unit-tests-py38.log 2>&1; A=$?
nice -n 19 taskset -c 63 /mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python -B -m unittest discover -s tests -v > receipts/unit-tests-py312.log 2>&1; B=$?
python3 - "$A" "$B" <<'PY'
import json, re, sys, subprocess, hashlib
from pathlib import Path
out = {}
for name, code, py in (("py38", sys.argv[1], "python3"), ("py312", sys.argv[2], "/mpac/sdicks02/jobs/clasher/e4v3-venv/bin/python")):
    log = Path("receipts/unit-tests-%s.log" % name).read_text()
    ran = int(re.search(r"Ran (\d+) tests", log).group(1))
    skipped = len(re.findall(r"\.\.\. skipped", log))
    version = subprocess.check_output([py, "-c", "import platform;print(platform.python_version())"], text=True).strip()
    out[name] = dict(python=version, ran=ran, skipped=skipped, passed=code == "0" and (log.rstrip().endswith("OK") or "OK (skipped" in log),
                     log="reports/explore/mac-registration/receipts/unit-tests-%s.log" % name,
                     log_sha256=hashlib.sha256(log.encode()).hexdigest())
import os
e4v3 = os.environ["CLASHER_E4V3"]
pins = {n: hashlib.sha256(Path(e4v3, n).read_bytes()).hexdigest() for n in ("convert_states.py", "corpus_contract.py", "receipts.py", "tier_backend.py", "state_rows.py", "measure_tiers.py", "prepare_bundle.py")}
Path("receipts/unit-tests.json").write_text(json.dumps(out, sort_keys=True, indent=1) + "\n")
Path("receipts/e4v3-pins.json").write_text(json.dumps(pins, sort_keys=True, indent=1) + "\n")
print(json.dumps(out))
PY
