"""Default/disabled-tempo baseline parity on the same two public smoke seeds."""
import gzip,hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];r=root/'reports/explore/tempo';folder=r/'parity';folder.mkdir(exist_ok=True)
cmd=[sys.executable,'-B','-m','clasher.analysis.loss_review.simulate','--out',str(folder),'--workers','2','--pairs','2','--seed-base',str(2**48+87000),'--exclusions',str(r/'exclusions.json'),'--delays','27','--arms','0','--full-decision-latency','--trace','--resume']
subprocess.run(cmd,check=True)
results=[]
for f in (folder/'traces').glob('*.json.gz'):
 with gzip.open(f,'rt') as s:raw=json.load(s)
 with gzip.open(r/'smoke/traces'/f.name,'rt') as s:tempo=json.load(s)
 assert raw['actions']==tempo['actions'] and raw['metadata']['winner']==tempo['metadata']['winner']
 results.append(dict(game=f.stem,actions=len(raw['actions']),winner=raw['metadata']['winner'],sha256=hashlib.sha256(json.dumps(raw['actions']).encode()).hexdigest()))
assert len(results)==2
(r/'receipts/parity.json').write_text(json.dumps(dict(matched=True,games=results,scope='same seed, disabled tempo wrapper vs original SearchAB/S6; actions and winners'),indent=2)+'\n')
