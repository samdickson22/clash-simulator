"""Stream sealed game shards into a bounded-FD mmap teacher corpus.

Run on a data/training host, with all source games staged under /mpac. Source
game seals remain authoritative; the packed seal pins every source manifest.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from .rows import sha, write_json


def check_memory(floor=24 << 30):
    available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                       if s.startswith('MemAvailable:')))*1024
    if available<floor: raise RuntimeError('MemAvailable below 24 GiB; packing stopped')


def pack(roots, output, stop=None, memory_guard=check_memory):
    output=Path(output)
    if output.exists(): raise ValueError('packing requires a fresh output')
    entries=[]; totals=dict(rows=0,entities=0,roots=0,masks=0)
    schema=None
    for root in roots:
        for f in sorted(Path(root).glob('game-*/manifest.json')):
            seal=json.loads(f.read_text())
            if seal.get('schema')!='clasher.exit-r1.teacher-v6.v1' or not seal.get('complete'):
                raise ValueError('unsealed source game: '+str(f))
            m=json.loads((f.parent/'train/manifest.json').read_text())
            current={k:(v['dtype'],v['shape'][1:]) for k,v in m['arrays'].items()}
            if schema is not None and current!=schema: raise ValueError('source schemas differ')
            schema=current
            mask=np.load(f.parent/'mask_table.npy',mmap_mode='r',allow_pickle=False)
            nr=int(m['rows']); ne=int(m['entities'])
            nc=int(m['arrays']['root_actions']['shape'][0]); nm=len(mask)
            entries.append(dict(path=str(f.parent.resolve()),manifest_sha256=sha(f),
                                rows=nr,entities=ne,roots=nc,masks=nm))
            for k,v in zip(totals,(nr,ne,nc,nm)): totals[k]+=v
    if not entries: raise ValueError('no sealed games')
    output.mkdir(parents=True); role=output/'train';role.mkdir()
    arrays={}
    for k,(dtype,tail) in schema.items():
        length=(totals['entities'] if k.startswith('flat_entity_') else
                totals['roots'] if k in ('root_actions','root_scores','root_valid') else
                totals['rows']+1 if k in ('entity_offsets','root_offsets') else totals['rows'])
        arrays[k]=np.lib.format.open_memmap(role/(k+'.npy'),mode='w+',dtype=dtype,shape=(length,*tail))
    masks=np.lib.format.open_memmap(output/'mask_table.npy',mode='w+',dtype=np.uint8,
                                   shape=(totals['masks'],289))
    offsets=dict(rows=0,entities=0,roots=0,masks=0)
    for episode,entry in enumerate(entries):
        if stop and Path(stop).exists(): raise InterruptedError('packing STOP; output remains unsealed')
        memory_guard(); source=Path(entry['path'])
        if sha(source/'manifest.json')!=entry['manifest_sha256']: raise ValueError('source seal changed')
        seal=json.loads((source/'manifest.json').read_text())
        for relative,digest in seal['files'].items():
            f=(source/relative).resolve()
            if not f.is_relative_to(source) or sha(f)!=digest: raise ValueError('source SHA mismatch: '+relative)
        row=offsets['rows']; n=entry['rows']
        for k,dest in arrays.items():
            value=np.load(source/'train'/(k+'.npy'),mmap_mode='r',allow_pickle=False)
            if k in ('entity_offsets','root_offsets'):
                base=offsets['entities' if k=='entity_offsets' else 'roots']
                dest[row:row+n+1]=value+base
            elif k.startswith('flat_entity_'):
                start=offsets['entities'];dest[start:start+entry['entities']]=value
            elif k in ('root_actions','root_scores','root_valid'):
                start=offsets['roots'];dest[start:start+entry['roots']]=value
            elif k=='mask_index':dest[row:row+n]=value+offsets['masks']
            elif k=='episode_ids':dest[row:row+n]=episode
            elif k=='row_ids':dest[row:row+n]=np.arange(row,row+n,dtype=np.int64)
            else:dest[row:row+n]=value
            del value
        start=offsets['masks']
        masks[start:start+entry['masks']]=np.load(source/'mask_table.npy',mmap_mode='r',allow_pickle=False)
        for k in offsets: offsets[k]+=entry[k]
    for a in arrays.values():a.flush()
    masks.flush()
    write_json(output/'sources.json',dict(schema='clasher.exit-r1.source-index.v1',games=entries,totals=totals))
    write_json(role/'manifest.json',dict(role='train',rows=totals['rows'],entities=totals['entities'],
        arrays={k:dict(dtype=str(v.dtype),shape=list(v.shape),sha256=sha(role/(k+'.npy'))) for k,v in arrays.items()}))
    files=[p for p in output.rglob('*') if p.is_file() and not p.name.endswith('.partial')]
    seal=dict(schema='clasher.exit-r1.teacher-v6.v1',complete=True,packed=True,rows=totals['rows'],
              totals=totals,files={str(p.relative_to(output)):sha(p) for p in files})
    write_json(output/'manifest.json',seal)
    return seal


def main():
    p=argparse.ArgumentParser();p.add_argument('--roots',nargs='+',required=True)
    p.add_argument('--output',required=True);p.add_argument('--stop')
    a=p.parse_args(); print(json.dumps(pack(a.roots,a.output,a.stop)))


if __name__=='__main__':main()
