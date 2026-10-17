"""Fixed locations and light I/O for Sam's requested follow-up."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2-levelgain-20261017')
OLD=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')
REPO=Path('/mpac/sdicks02/repos/clasher-bot-deckopt2-fullpool')
PY='/mpac/sdicks02/repos/clasher-bot/.venv/bin/python'
DECKS={
 'baseline':['Valkyrie','Archers','Minions','Cannon','Fireball','Giant','MiniPekka','Musketeer'],
 'sam':['Valkyrie','Archers','Bats','Cannon','Fireball','Zap','MiniPekka','Giant'],
 'inferno':['Valkyrie','Archers','Goblins','InfernoTower','Fireball','Giant','MiniPekka','Skeletons']}
POLICIES=('R3a','LIVE-K4CW-r16')
def utc():return subprocess.check_output(['date','-u','+%FT%TZ'],text=True).strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,data,exclusive=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if exclusive:
  with p.open('x') as stream:json.dump(data,stream,indent=2,sort_keys=True)
 else:
  import os
  temp=p.with_name(p.name+'.tmp-'+str(os.getpid()));temp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');temp.replace(p)
def record(text):
 with (ROOT/'PROGRESS.md').open('a') as stream:stream.write('\n'+utc()+' '+text+'\n')
