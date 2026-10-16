"""Read-only truth-simulator identity check; no Runtime or game construction."""
from pathlib import Path
import json,os,subprocess
from bot.levels.placement_probe import installed_identity
j=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
actual=installed_identity();expected=json.loads((j/'manifest.json').read_text())['simulator']
assert actual==expected,(actual,expected)
r=dict(passed=True,utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),host=os.uname().nodename,identity=actual)
(j/'fullpool'/f'pin-check-{os.uname().nodename}.json').write_text(json.dumps(r,indent=2))
print('TRUTH_PIN_CHECK_PASSED',r['host'],r['utc'],actual['binary_sha256'],flush=True)
