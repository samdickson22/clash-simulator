"""Use the second compute lane after recorded game 7 to replay game 3.

The original lane subsequently validates the saved row through the unchanged
authority. A per-game lock prevents two evaluations of game 3 from overlapping.
"""
from pathlib import Path
import json
import subprocess
import sys
import time
from post_checks_retry import OUT, run

for _ in range(360):
    result=OUT/'recorded-r2-7.exit.json'
    if result.exists():
        assert json.loads(result.read_text())['exit_code']==0
        break
    time.sleep(5)
else:
    raise TimeoutError('Recorded game 7 did not finish within 30 minutes')
run('recorded-balanced-3', [sys.executable, '-B', str(OUT/'verify_gate.py'), 'recorded-3'])
