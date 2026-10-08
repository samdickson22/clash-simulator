"""Checksum-only cache fan-in/fan-out; source manifest restricts copied files."""
import argparse,datetime,json,subprocess
from pathlib import Path
from pixel_cache import PixelCache,sha


def main():
    p=argparse.ArgumentParser();p.add_argument('--from-host',choices=('127x16','127x18','127x01'),required=True)
    p.add_argument('--remote-cache',required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    remote=Path(a.remote_cache)
    if not remote.is_absolute() or not str(remote).startswith('/mpac/sdicks02/repos/clasher'):raise ValueError('Outside owned footprint')
    if sha(a.split)!='3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258':raise ValueError('Frozen split changed')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    script='import pathlib,json; print(json.dumps([json.loads(p.read_text()) for p in sorted(pathlib.Path('+repr(str(remote))+').glob("*/index.json"))]))'
    result=subprocess.run(['ssh','-o','BatchMode=yes',a.from_host,'python3 -'],input=script,text=True,capture_output=True,check=True)
    indices=json.loads(result.stdout);rows=[];files=[]
    for index in indices:
        ep=index['episode']
        if '/' in ep or not ep.startswith('v4-phase-a-') or index['split'] not in ('train','validation'):raise ValueError('Cache split/episode rejected')
        path=a.source/ep/'receipt.json';r=json.loads(path.read_text());m=members[r['seed']]
        if (r['split'],r['decks'])!=(m['split'],m['decks']) or r['split']!=index['split']:raise ValueError('Membership mismatch')
        r['receipt_sha256']=sha(path);rows.append(r)
        if r['receipt_sha256']!=index['receipt_sha256']:raise ValueError('Source receipt mismatch')
        for name in ('index.json','raw.zst','pixels.zst'):files.append(ep+'/'+name)
    a.cache.mkdir(parents=True,exist_ok=True)
    subprocess.run(['rsync','-a','--checksum','--ignore-existing','--rsync-path=nice -n 10 rsync',
                    '--files-from=-',a.from_host+':'+str(remote)+'/',str(a.cache)+'/'],
                   input='\n'.join(files)+'\n',text=True,check=True)
    verified=PixelCache(a.cache,rows)
    result=dict(matches=len(rows),frames=sum(r['frames'] for r in rows),files_verified=len(rows)*2,
                bytes=sum(i['bytes'] for i in indices),equality_checked=sum(i['equality']['checked'] for i in indices),
                index_sha256={r['episode']:sha(a.cache/r['episode']/'index.json') for r in rows},
                cache=str(a.cache),source_host=a.from_host,heldout_opened=False,
                completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
