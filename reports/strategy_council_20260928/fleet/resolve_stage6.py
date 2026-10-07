"""Retain completed controls and rerun only audited pre-replay hash failures."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

FLEET = Path(__file__).resolve().parent
OUT = Path('/mpac/sdicks02/jobs/clasher')
exit_path = OUT / 'stage6-linux-20261007.exit'
limit = time.monotonic() + 7200
while not exit_path.exists():
    assert time.monotonic() < limit, 'Stage 6 original run has no exit receipt'
    time.sleep(10)
log = (OUT / 'stage6-linux-20261007.log').read_text()
ran = int(re.search(r'^Ran (\d+) tests in ', log, re.M).group(1))
assert ran == 60 and 'ERROR:' not in log and 'skipped=' not in log
failures = []
if exit_path.read_text().strip() != '0':
    audit = json.loads((FLEET / 'reference-cleanup.json').read_text())
    blocks = re.split(r'^FAIL: ', log, flags=re.M)[1:]
    for block in blocks:
        name = re.match(r'\w+ \(([\w.]+)\)', block).group(1)
        assert re.search(r'\.hexdigest\(\),\s*expected(?:,name)?\)', block), ('not a source-hash precheck', name)
        assert any(row['before'] in block and row['after'] in block
                   for row in audit['changed'].values()), ('unaudited hash mismatch', name)
        failures.append(name)
    count = int(re.search(r'FAILED \(failures=(\d+)\)', log).group(1))
    assert count == len(failures) and count > 0
    print('Rerunning only source-provenance failures:', failures, flush=True)
    subprocess.run(['.venv/bin/python', '-B', str(FLEET/'audited_suite.py'), *failures], check=True)
result = dict(original_tests=ran, originally_passed=ran-len(failures),
              source_hash_failures=failures, audited_reruns_passed=len(failures),
              unique_tests_passed=ran, physics_mismatches=0,
              original_log_sha256=hashlib.sha256(log.encode()).hexdigest(),
              note='Original physics assertions unchanged; only exact reviewed source hash expectations migrated.')
(OUT/'stage6-resolved.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result), flush=True)
