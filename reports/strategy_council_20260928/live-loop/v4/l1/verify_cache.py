"""Exact augmented-sample parity against independent sequential H.264 decoding."""
import argparse,json,random,time
from pathlib import Path
import cv2
import torch
from data_v4 import Windows


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--split',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--samples',type=int,default=16);p.add_argument('--max-matches',type=int,default=1);a=p.parse_args()
    torch.set_num_threads(1);cv2.setNumThreads(1);a.output.mkdir(parents=True,exist_ok=False)
    data=Windows(a.source,a.split,a.output/'data',max_matches=a.max_matches,pixel_cache=a.cache)
    cache=data.pixel_cache;rng=random.Random(6112);rows=[]
    for n in range(a.samples):
        index=rng.randrange(len(data));state=data.rng.getstate();t=time.perf_counter()
        cached=data.sample(index);cached_seconds=time.perf_counter()-t
        data.rng.setstate(state);data.pixel_cache=None;data.cache.clear();t=time.perf_counter()
        decoded=data.sample(index);decode_seconds=time.perf_counter()-t;data.pixel_cache=cache
        for k,v in cached.items():
            if isinstance(v,dict):
                for name,value in v.items():assert torch.equal(value,decoded[k][name]),(n,k,name)
            else:assert torch.equal(v,decoded[k]),(n,k)
        rows.append(dict(index=index,cached_seconds=cached_seconds,decode_seconds=decode_seconds,exact=True))
    result=dict(samples=a.samples,mismatches=0,all_tensors_exact=True,rows=rows,heldout_opened=False,
                cached_windows_per_second=a.samples/sum(r['cached_seconds'] for r in rows),
                sequential_reference_windows_per_second=a.samples/sum(r['decode_seconds'] for r in rows),
                pixel_checks=sum(cache.index[r['episode']]['equality']['checked'] for r in data.receipts),
                pixel_population=sum(r['frames'] for r in data.receipts))
    (a.output/'complete.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':main()
