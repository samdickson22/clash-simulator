"""Light-only observer; no Runtime/game construction."""
import json
from pathlib import Path
from sam_common import ROOT,utc
out={'utc':utc(),'preflight_passed':(ROOT/'preflight/receipt.json').exists(),'stop':(ROOT/'STOP').exists()}
out['status']=json.loads((ROOT/'status.json').read_text()) if (ROOT/'status.json').exists() else None
out['errors']={p.name:json.loads(p.read_text()) for p in ROOT.glob('*error.json')}
out['fresh_population_exists']=Path('/mpac/sdicks02/scratch/live-lead-share/opponent-decks-20261017-1850.jsonl').exists()
out['fresh_bank_registered']=(ROOT/'battlelog1850/validation/bank.json').exists()
out['done']=(ROOT/'DONE.json').exists()
print(json.dumps(out))
