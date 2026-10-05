"""Seal one completed group and freeze its native source/binary snapshot."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

import clasher_core
from stage2 import fingerprint


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--label',required=True)
    p.add_argument('--build',required=True);p.add_argument('--extra-exit',action='append',default=[])
    p.add_argument('--cases',type=int,required=True);p.add_argument('--games',type=int,default=12)
    args=p.parse_args();folder=Path(__file__).resolve().parent;root=folder.parents[3]
    labels=[args.label,f'{args.label}-tests',f'{args.label}-focused',f'{args.label}-interactions',*args.extra_exit]
    for label in labels:assert (folder/f'{label}.exit').read_text().strip()=='0',label
    focus_path=folder/f'{args.label}-focused.json';game_path=folder/f'{args.label}-interactions.json'
    focused=json.loads(focus_path.read_text());games=json.loads(game_path.read_text())
    native=Path(clasher_core.__file__).resolve();assert native.parent==folder/'native'
    source=fingerprint();native_hash=sha(native)
    for receipt in (focused,games):
        assert receipt['pins']['source']==source and receipt['pins']['native']==native_hash
        assert all(r['ok'] for r in receipt['results'].values())
    assert len(focused['results'])==args.cases and len(games['results'])==args.games
    accepted=Counter();rows=list(games['results'].values())
    for row in rows:assert row['terminal'];accepted.update(row['accepted'])
    assert all(accepted[c]>0 for c in focused['cards'])
    entry=json.loads((folder/'entry.json').read_text())['sha256']
    for name,expected in entry.items():
        if (name.startswith('src/clasher/') and not name.startswith('src/clasher/vision/')) or name in ('gamedata.json','engine-rs/clasher_core.abi3.so'):
            assert sha(root/name)==expected,name
    archive=folder/args.build;archive.mkdir(exist_ok=False);pins={}
    for path in [*root.joinpath('engine-rs/src').glob('*.rs'),*root.joinpath('engine-rs').glob('*.py'),root/'engine-rs/Cargo.toml',root/'engine-rs/Cargo.lock']:
        relative=path.relative_to(root);dest=archive/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);pins[str(relative)]=sha(path)
    shutil.copy2(native,archive/native.name);pins['private_native']=native_hash
    (archive/'pins.json').write_text(json.dumps(pins,indent=2)+'\n')
    files=[focus_path,game_path,folder/f'{args.label}.log',Path(__file__),archive/'pins.json',*[folder/f'{label}.exit' for label in labels]]
    out=dict(status='incremental group qualified; final S122 NOT admitted',cards=focused['cards'],source=source,native=native_hash,
             focused_cases=args.cases,focused_ticks=sum(r['ticks'] for r in focused['results'].values()),
             terminal_games=args.games,game_ticks=sum(r['ticks'] for r in rows),imports=sum(len(r['imports']) for r in rows),
             accepted_placements=sum(accepted.values()),accepted_by_card=dict(accepted),
             stepping_speedup=sum(r['python_cpu'] for r in rows)/sum(r['rust_cpu'] for r in rows),
             clone_us_max=max(i['clone_us'] for r in rows for i in r['imports']),mismatches=0,reference_preserved=True,
             receipts={str(path.relative_to(folder)):sha(path) for path in files})
    output=folder/f'{args.label}-manifest.json';assert not output.exists();output.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k!='receipts'},indent=2))


if __name__=='__main__':main()
