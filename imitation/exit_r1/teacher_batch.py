"""Join mmap teacher shards while preserving sparse candidate vectors."""
import numpy as np
import torch


def combined_batch(shards,ends,indices):
    which=np.searchsorted(ends,indices,side='right')
    starts=np.r_[0,ends[:-1]]
    batches=[shards[j].batch(indices[which==j]-starts[j]) for j in np.unique(which)]
    bw=max(b['ids'].shape[1] for b,y in batches)
    rw=max(y['root_actions'].shape[1] for b,y in batches)
    def pad(v,width,fill=0):
        if v.shape[1]==width:return v
        dest=torch.full((v.shape[0],width,*v.shape[2:]),fill,dtype=v.dtype)
        dest[:,:v.shape[1]]=v
        return dest
    b={k:torch.cat([pad(bb[k],bw) if k in ('ids','types','numeric','valid') else bb[k]
                    for bb,yy in batches]) for k in batches[0][0]}
    y={k:torch.cat([pad(yy[k],rw,2304 if k=='root_actions' else 0) if k.startswith('root_') else yy[k]
                    for bb,yy in batches]) for k in batches[0][1]}
    return b,y
