"""Recompute metrics from saved sim telemetry without re-running a player."""
import argparse,gzip,json,multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
from .metrics import Game,extract,archetype
from .human import write
CAT=None;OUT=None


def reduce(path):
    with gzip.open(path,'rt') as f:r=json.load(f)
    meta=r['metadata'];name=path.name.removesuffix('.json.gz')
    pair=name.rsplit('-d',1)[0];delay=meta['delay_ticks']
    game=Game(name,pair,f'search_d{delay}','exploration',
        archetype(meta['own_deck'])+' vs '+archetype(meta['opponent_deck']),meta['own_deck'],
        float(meta['winner'] is not None and meta['winner']!=meta['seat']) if meta['terminal'] else None,
        np.asarray(r['ticks']),np.asarray(r['globals']),np.asarray(r['hands']),np.asarray(r['offsets']),
        np.asarray(r['entities']),np.asarray(r['entity_ids']),r['plays'],meta,
        np.asarray(r['queues']) if 'queues' in r else None)
    result=extract(game,CAT);write(OUT/f'{name}.json',result)
    return name


def main():
    global CAT,OUT
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--workers',type=int,default=32)
    a=ap.parse_args();CAT=json.loads((a.source/'catalog.json').read_text());OUT=a.out
    with ProcessPoolExecutor(a.workers,mp_context=multiprocessing.get_context('fork')) as pool:
        names=list(pool.map(reduce,sorted((a.source/'traces').glob('*.json.gz'))))
    write(a.out.parent/'reduction-receipt.json',dict(games=len(names),source=str(a.source),names=names))

if __name__=='__main__':main()
