"""Stop only the owned sequential replay after its five assigned receipts exist."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time
c=Path(__file__).resolve().parent
while True:
    try:
        data=json.loads((c/'recorded_workspace.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError):
        time.sleep(1)
        continue
    if len(data['results']) >= 5:
        assert not data['mismatches']
        cmd=subprocess.check_output(['ps','-p','86157','-o','command='],text=True)
        assert 'broad_identity.py recorded record' in cmd and 'recorded_workspace.json' in cmd
        (c/'recorded_workspace_prefix.json').write_text(json.dumps(data,indent=2)+'\n')
        os.kill(86157,signal.SIGTERM)
        (c/'workspace_prefix.done').write_text('Five complete exact game receipts; owned sequential worker stopped before unassigned games.\n')
        break
    time.sleep(1)
