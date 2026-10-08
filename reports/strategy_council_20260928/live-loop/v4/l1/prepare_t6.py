"""Train/validation-only adapter; frozen producer/converter remain unchanged.

Receipt inventory is the only heldout access. Never open heldout payloads.
Keeps per-match converter outputs (including originals) for resumable conversion.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert_v3 import convert


def read(p): return [json.loads(x) for x in p.read_text().splitlines()]
def write(p, x): p.write_text(json.dumps(x, indent=2)+'\n')
def one(args):
    source, output = map(Path, args)
    if not (output/'roundtrip.json').exists():
        if output.exists(): raise ValueError(f'Incomplete conversion retained: {output}; use a fresh run directory')
        convert(source, output)
    return str(output)


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--split',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);a=p.parse_args()
    if not 1<=a.workers<=2: raise ValueError('At most two conversion workers')
    a.output.mkdir(parents=True,exist_ok=True)
    frozen=json.loads(a.split.read_text());members={e['seed']:e for e in frozen['matches']}
    inventory=a.output/'inventory.json'
    if inventory.exists(): rows=json.loads(inventory.read_text())
    else:
        rows=[]
        for r in sorted(a.source.glob('*/receipt.json')):
            receipt=json.loads(r.read_text())
            if receipt.get('split') not in ('train','validation'):continue
            m=members[receipt['seed']]
            if m['split']!=receipt['split'] or m['decks']!=receipt['decks']:raise ValueError('Split mismatch')
            rows.append(dict(path=str(r.parent),receipt_sha256=hashlib.sha256(r.read_bytes()).hexdigest(),**receipt))
        write(inventory, rows)
    for r in rows:
        if r['split'] not in ('train','validation'): raise ValueError('Heldout forbidden')
        if hashlib.sha256((Path(r['path'])/'receipt.json').read_bytes()).hexdigest()!=r['receipt_sha256']: raise ValueError('Receipt changed')
    with ProcessPoolExecutor(a.workers) as pool:
        list(pool.map(one, [(r['path'],str(a.output/'per-match'/r['episode'])) for r in rows]))
    for name in ('videos','audit','evaluation_only'): (a.output/name).mkdir(exist_ok=True)
    manifest=None
    for r in rows:
        ep=r['episode'];base=a.output/'per-match'/ep
        m=json.loads((base/'manifest.json').read_text())
        if manifest is None: manifest=dict(m,matches=[])
        # v4 has the same 700ms tail as v3 protocol 2. This is layout adaptation,
        # not a claim that timestamp brackets are compositor-certified.
        manifest['matches'].append(dict(m['matches'][0],capture_protocol=2))
        for name,target in [('videos',base/'videos'/f'{ep}.mp4'),('audit',base/'audit'/ep)]:
            link=a.output/name/target.name
            if not link.exists():link.symlink_to(target.resolve())
        ev=a.output/'evaluation_only'/ep;ev.mkdir(exist_ok=True)
        if not (ev/'observations.jsonl').exists():
            audit=read(base/'audit'/ep/'frames.jsonl');raw=read(Path(r['path'])/'frames.jsonl')
            origin=raw[0]['produced_mono']
            with (ev/'frames.jsonl').open('w') as f:
                for x in audit: f.write(json.dumps(dict(timestamp_ms=x['timestamp_ms'],received_mono_s=origin+x['timestamp_ms']/1000))+'\n')
            from clasher.data import CardDataLoader
            loader=CardDataLoader();names={loader.get_card(n)._raw_entry['id']:n for n in m['cards']}
            with gzip.open(Path(r['path'])/'evaluation-only.jsonl.gz','rt') as src,(ev/'observations.jsonl').open('w') as dst:
                for line in src:
                    x=json.loads(line);obs=x['observation'];players=[]
                    for pl in sorted(obs['players'],key=lambda p:p['owner']):
                        hand=[None]*4
                        for c in pl['hand']:hand[c['handIndex']]=names[c['cardId']]
                        players.append(dict(elixir=pl['elixir'],hand=hand,cycle=[names[c['cardId']] for c in pl['cycle']]))
                    dst.write(json.dumps(dict(tick=obs['tick'],start_ns=round(x['observed_at']*1e9),players=players))+'\n')
    write(a.output/'manifest.json',manifest)
    write(a.output/'complete.json',dict(matches=len(rows),splits={s:sum(r['split']==s for r in rows) for s in ('train','validation')},heldout_opened=False))

if __name__=='__main__':main()
