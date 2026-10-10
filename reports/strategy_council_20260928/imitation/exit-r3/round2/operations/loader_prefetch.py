"""Ordered complete-step batches from six bounded CPU loader workers.

The frozen trainer retains its loop, deterministic per-step sampler and optimizer.
Workers construct the same complete human/teacher batches; they never split,
sort, reorder or alter scientific rows. A private DataLoader generator keeps
parent training RNG untouched. No mmap random advice is used.
"""
import os
from pathlib import Path
import threading
import time
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

class StepBatches(Dataset):
    def __init__(self, owner, start):
        self.owner, self.start = owner, start
    def __len__(self):
        return self.owner.steps-self.start
    def __getitem__(self, index):
        s=self.start+index; o=self.owner
        hi,ti=o.original_indices(o.human_size,o.teacher_size,o.batch,o.ratio,o.seed,s)
        hb=o.original_human(o.human_store,o.human_ix[hi]) if len(hi) else None
        tb=o.original_teacher(o.shards,o.ends,ti) if len(ti) else None
        return dict(step=s,hi=hi,ti=ti,human=hb,teacher=tb)

def worker_init(worker):
    os.sched_setaffinity(0,{120+worker})
    torch.set_num_threads(1)
    assert os.getpriority(os.PRIO_PROCESS,0)>=10

class Prefetch:
    def __init__(self, train, teacher_batch, steps, workers=6, prefetch=4):
        assert workers==6 and prefetch==4
        self.train,self.steps,self.workers,self.prefetch=train,steps,workers,prefetch
        self.original_indices=train.mixed_indices
        self.original_eligible=train.eligible
        self.original_human=train.human_batch
        self.original_teacher=teacher_batch.combined_batch
        self.original_step=train.step
        self.iterator=None;self.cached=None;self.shards=[];self.ends=np.array([],dtype=np.int64)
        self.human_store=None;self.human_ix=None;self.current=-1
        self.stop=threading.Event();self.watch=None
        self.peak_pss=0;self.minimum_available=1<<62;self.resource_stop=None
        train.eligible=self.eligible
        train.mixed_indices=self.indices
        train.human_batch=self.human
        teacher_batch.combined_batch=self.teacher
        train.step=self.step
    def eligible(self,store,*args):
        self.human_store=store
        self.human_ix=self.original_eligible(store,*args)
        return self.human_ix
    def indices(self,human_size,teacher_size,batch,ratio,seed,step):
        hi,ti=self.original_indices(human_size,teacher_size,batch,ratio,seed,step)
        self.human_size,self.teacher_size,self.batch,self.ratio,self.seed=human_size,teacher_size,batch,ratio,seed
        self.current=step
        if self.iterator is not None:
            self.cached=next(self.iterator)
            assert self.cached['step']==step
            assert np.array_equal(self.cached['hi'],hi) and np.array_equal(self.cached['ti'],ti)
        return hi,ti
    def human(self,store,ix):
        if self.cached is None:return self.original_human(store,ix)
        assert store is self.human_store
        assert np.array_equal(ix,self.human_ix[self.cached['hi']])
        return self.cached['human']
    def teacher(self,shards,ends,ix):
        if self.cached is None:
            self.shards,self.ends=shards,ends
            return self.original_teacher(shards,ends,ix)
        assert np.array_equal(ix,self.cached['ti'])
        return self.cached['teacher']
    def start(self):
        if self.current+1>=self.steps:return
        # Deliberately start after the first synchronous batch captures the stores.
        # CUDA computations remain exclusively in the parent, as in qualified T11.
        generator=torch.Generator().manual_seed(self.seed)
        before=torch.get_rng_state().clone()
        self.loader=DataLoader(StepBatches(self,self.current+1),batch_size=None,
            num_workers=self.workers,prefetch_factor=self.prefetch,pin_memory=True,
            multiprocessing_context='fork',worker_init_fn=worker_init,generator=generator)
        self.iterator=iter(self.loader)
        assert torch.equal(before,torch.get_rng_state())
        self.watch=threading.Thread(target=self.monitor,daemon=True)
        self.watch.start()
    def usage(self):
        pids=[os.getpid()]
        if self.iterator is not None:pids += [p.pid for p in self.iterator._workers]
        total=0
        for pid in pids:
            try:
                total += int(next(s.split()[1] for s in Path(f'/proc/{pid}/smaps_rollup').read_text().splitlines()
                                  if s.startswith('Pss:')))*1024
            except (FileNotFoundError,ProcessLookupError):pass
        available=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines()
                           if s.startswith('MemAvailable:')))*1024
        return total,available
    def monitor(self):
        import signal
        leased=os.uname().nodename.split('.')[0] in ('127x09','127x13','127x14','127x15','127x16')
        while not self.stop.wait(.5):
            pss,available=self.usage()
            self.peak_pss=max(self.peak_pss,pss);self.minimum_available=min(self.minimum_available,available)
            if leased and pss>46_000_000_000 or available<24*2**30:
                self.resource_stop='leased aggregate PSS exceeds46GB' if leased and pss>46_000_000_000 else 'MemAvailable below24GiB'
                os.kill(os.getpid(),signal.SIGTERM)
                return
    def step(self,*args,**kwargs):
        def cpu_only(value):
            if isinstance(value,torch.Tensor):assert value.device.type=='cpu','loader retained a GPU tensor'
            elif isinstance(value,dict):
                for v in value.values():cpu_only(v)
            elif isinstance(value,(list,tuple)):
                for v in value:cpu_only(v)
        cpu_only(args[2]);cpu_only(args[3])
        if self.iterator is None:self.start()
        return self.original_step(*args,**kwargs)
    def close(self):
        self.stop.set()
        if self.watch is not None:self.watch.join(timeout=2)
        if self.iterator is not None:self.iterator._shutdown_workers()
