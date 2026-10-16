"""Read-only source archive receipt; no runtime, models or games loaded."""
import hashlib,json,os,subprocess
from pathlib import Path
repo=Path('/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool')
d=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2/fullpool')
files={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest()
       for directory in ('bot','reports/explore/x4s') for p in sorted((repo/directory).rglob('*.py'))}
r=dict(utc=subprocess.check_output(['date','-u','+%Y-%m-%dT%H:%M:%SZ'],text=True).strip(),host=os.uname().nodename,files=files)
(d/f'source-pins-{r["host"]}.json').write_text(json.dumps(r,indent=2))
print(r['host'],len(files),'source files hashed')
