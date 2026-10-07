"""Ship closed matches; only delete local files after remote SHA256 verification."""
import argparse
import fcntl
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import time
from common import HERE, append, sha, write

DEST = '/mpac/sdicks02/repos/clasher-v4-data'
HOST = '127x02'
BUFFER = Path.home()/'.cache/clasher-live-v4/buffer'
CAP = 6_000_000_000
FLOOR = 15*1024**3

# No writes outside DEST. The finalized directory is immutable on retries.
VERIFY = r'''
import hashlib,json,os,pathlib,sys
root=pathlib.Path('/mpac/sdicks02/repos/clasher-v4-data')
episode=sys.argv[1]
assert episode.replace('-','').isalnum()
incoming=root/'.incoming'/episode
final=root/('registration' if episode.startswith('v4-registration-') else 'matches')/episode
folder=final if final.exists() else incoming
manifest=json.loads((folder/'sha256.json').read_text())
for name,expected in manifest.items():
 p=folder/name
 assert p.resolve().parent==folder.resolve() and p.is_file() and not p.is_symlink()
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  os.fsync(f.fileno())
 assert h.hexdigest()==expected,(name,'checksum mismatch')
receipt=dict(episode=episode,verified_files=len(manifest),hashes=manifest,bytes=sum((folder/n).stat().st_size for n in manifest))
if not final.exists():
 final.parent.mkdir(parents=True,exist_ok=True)
 (folder/'hub-verification.json').write_text(json.dumps(receipt)+'\n')
 os.rename(folder,final)
elif incoming.exists() and json.loads((incoming/'sha256.json').read_text())==manifest:
 for p in incoming.iterdir():
  assert p.is_file() and not p.is_symlink()
  p.unlink()
 incoming.rmdir()
print(json.dumps(receipt))
'''


def run(args, **kw):
    args=[shutil.which(args[0]) or args[0],*args[1:]]
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=600, close_fds=False, **kw)


def ship(folder, receipts=HERE/'data'):
    folder = Path(folder)
    if folder.name.startswith('v4-registration-') and receipts==HERE/'data':receipts=HERE/'data/registration'
    if (folder/'sha256.json').exists():
        hashes=json.loads((folder/'sha256.json').read_text())
    else:
        if not (folder/'receipt.json').exists(): raise ValueError('Incomplete match cannot ship')
        hashes = {p.name:sha(p) for p in sorted(folder.iterdir()) if p.is_file() and p.name!='sha256.json'}
        write(folder/'sha256.json', hashes)
    if any(Path(n).name!=n for n in hashes):raise ValueError('Invalid manifest path')
    name=folder.name
    if not name.replace('-','').isalnum(): raise ValueError('Invalid episode name')
    remote=f'{DEST}/.incoming/{name}'
    run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',HOST,'nice -n 10 mkdir -p '+shlex.quote(remote)])
    run(['rsync','-a','--checksum','--partial','--bwlimit=8000','--rsync-path=nice -n 10 rsync',str(folder)+'/',f'{HOST}:{remote}/'])
    reply=run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',HOST,
               'nice -n 10 python3 -B -c '+shlex.quote(VERIFY)+' '+shlex.quote(name)])
    ack=json.loads(reply.stdout)
    if ack.get('hashes') != hashes or ack.get('episode') != name or ack.get('verified_files') != len(hashes):
        raise ValueError('Hub acknowledgement does not match the local manifest')
    # Recheck local immutability before deletion, including retries after a crash.
    if any((folder/n).exists() and sha(folder/n)!=h for n,h in hashes.items()): raise ValueError('Local file changed during transfer')
    receipts.mkdir(parents=True,exist_ok=True)
    local_receipt=receipts/(name+'.json')
    original=json.loads((folder/'receipt.json').read_text()) if (folder/'receipt.json').exists() else json.loads(local_receipt.read_text())['receipt']
    write(local_receipt,dict(receipt=original,hub=ack))
    append(receipts/'transfers.jsonl',dict(time=time.time(),episode=name,bytes=ack['bytes'],hashes=hashes))
    # Keep compact labels locally under the same capped buffer, plus the manifest.
    # Only media and redundant evaluator observations are removed.
    keep=folder.parent/'verified-labels'/name
    keep.mkdir(parents=True,exist_ok=True)
    for p in folder.iterdir():
        if p.name in ('video.mp4','objects.jsonl.gz','rich-objects.jsonl.gz','evaluation-only.jsonl.gz'): p.unlink()
        else: p.replace(keep/p.name)
    folder.rmdir()
    return ack


def main():
    p=argparse.ArgumentParser();p.add_argument('--buffer',type=Path,default=BUFFER);a=p.parse_args()
    a.buffer.mkdir(parents=True,exist_ok=True)
    with (a.buffer/'ship.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for folder in sorted(a.buffer.glob('v4-*')):
            if (folder/'receipt.json').exists() or (folder/'sha256.json').exists(): print(ship(folder),flush=True)
if __name__=='__main__':main()
