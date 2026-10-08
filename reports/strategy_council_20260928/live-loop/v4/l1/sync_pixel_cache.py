"""Checksum-only cache fan-in/fan-out; source manifest restricts copied files."""
import argparse,datetime,fcntl,json,subprocess,uuid
from pathlib import Path
from pixel_cache import PixelCache,sha
from cache_budget import validate_root,require_growth,used_bytes,MAX_BYTES,MIN_FREE_BYTES


def main():
    p=argparse.ArgumentParser();p.add_argument('--from-host',choices=('127x01','127x03','127x04','127x08','127x09','127x11','127x13','127x14','127x15','127x16','127x18'),required=True)
    p.add_argument('--remote-cache',required=True);p.add_argument('--cache',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True);p.add_argument('--episodes',nargs='+');a=p.parse_args()
    validate_root(a.cache)
    lock=(a.cache/'.writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    remote=Path(a.remote_cache)
    if not remote.is_absolute() or not str(remote).startswith('/mpac/sdicks02/repos/clasher'):raise ValueError('Outside owned footprint')
    if sha(a.split)!='3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258':raise ValueError('Frozen split changed')
    members={r['seed']:r for r in json.loads(a.split.read_text())['matches']}
    script='import pathlib,json; print(json.dumps([json.loads(p.read_text()) for p in sorted(pathlib.Path('+repr(str(remote))+').glob("*/index.json"))]))'
    result=subprocess.run(['ssh','-o','BatchMode=yes',a.from_host,'python3 -'],input=script,text=True,capture_output=True,check=True)
    indices=json.loads(result.stdout);rows=[];files=[]
    if a.episodes and (len(a.episodes)!=len(set(a.episodes)) or
            set(a.episodes)-{i['episode'] for i in indices}):
        raise ValueError('Requested cache episodes missing or duplicated')
    for index in indices:
        ep=index['episode']
        if a.episodes and ep not in a.episodes:continue
        if '/' in ep or not ep.startswith('v4-phase-a-') or index['split'] not in ('train','validation'):raise ValueError('Cache split/episode rejected')
        path=a.source/ep/'receipt.json';r=json.loads(path.read_text());m=members[r['seed']]
        if (r['split'],r['decks'])!=(m['split'],m['decks']) or r['split']!=index['split']:raise ValueError('Membership mismatch')
        r['receipt_sha256']=sha(path);rows.append(r)
        if r['receipt_sha256']!=index['receipt_sha256']:raise ValueError('Source receipt mismatch')
        for name in ('index.json','raw.zst','pixels.zst'):files.append(ep+'/'+name)
    selected={i['episode']:i for i in indices if not a.episodes or i['episode'] in a.episodes}
    for r in rows:
        ep=r['episode'];destination=a.cache/ep
        if destination.exists():
            PixelCache(a.cache,[r]);continue
        expected=selected[ep]['bytes']+len(json.dumps(selected[ep]))*2+65536
        require_growth(a.cache,expected)
        # No published index is visible until all payload hashes pass. Partial
        # transfers are retained in unique directories and counted in the budget.
        incoming=a.cache/('.incoming-'+uuid.uuid4().hex);incoming.mkdir()
        subprocess.run(['rsync','-a','--checksum','--rsync-path=nice -n 10 rsync',
                        '--files-from=-',a.from_host+':'+str(remote)+'/',str(incoming)+'/'],
                       input='\n'.join(ep+'/'+n for n in ('raw.zst','pixels.zst','index.json'))+'\n',text=True,check=True)
        PixelCache(incoming,[r])
        (incoming/ep).rename(destination)
    # Every imported or reused match was verified above while holding the lock.
    result=dict(matches=len(rows),frames=sum(r['frames'] for r in rows),files_verified=len(rows)*2,
                bytes=sum(i['bytes'] for i in selected.values()),equality_checked=sum(i['equality']['checked'] for i in selected.values()),
                index_sha256={r['episode']:sha(a.cache/r['episode']/'index.json') for r in rows},
                cache=str(a.cache),source_host=a.from_host,heldout_opened=False,
                completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    result.update(bytes_on_host=used_bytes(a.cache),maximum_bytes=MAX_BYTES,minimum_free_bytes=MIN_FREE_BYTES)
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
