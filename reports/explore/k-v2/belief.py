"""Exact frozen posterior with resumable private, bounded preparation blocks.

Timed calls commit only a complete event-history update. At cutoff the private
transaction stays suspended; the next decision resumes it before newer events.
No-deadline calls use the frozen implementation verbatim. Scoring is unchanged.
"""
import copy
import time
import numpy as np
from derived_public_state import DerivedPublicState as FrozenBelief

class Belief(FrozenBelief):
    block_rows=4096
    def check(self):
        if self._deadline is not None and self._clock()>=self._deadline:
            raise TimeoutError('K-v2 belief cutoff')

    def _advance_work(self,tick):
        if tick<self.tick:raise ValueError('public time moved backwards')
        while self.tick<tick:
            yield
            self.tick+=1
            rate=.93 if self.tick>4800 else 1.4 if self.tick>2400 else 2.8
            self.elixir=min(10.,(round(self.elixir*10000)+int(500/rate))/10000) if self.elixir<10. else self.elixir
            self.refill=max(0,self.refill-50)
            if self.refill==0 and self.queue_len>4:
                dest=np.empty_like(self.states)
                for start in range(0,len(self.states),self.block_rows):
                    yield
                    part=self.states[start:start+self.block_rows].copy()
                    part[:,0]=part[:,4];part[:,:4].sort(axis=1)
                    part[:,4:-1]=part[:,5:];part[:,-1]=0
                    dest[start:start+len(part)]=part
                self.states=dest;self.queue_len-=1
                self.refill=1000 if self.tick<2400 else 500 if self.tick<4800 else 350
                self._derived=None

    def _update_work(self,tick,events):
        if list(events[:len(self.events)])!=self.events:raise ValueError('public events changed')
        for event in events[len(self.events):]:
            yield from self._advance_work(event.tick)
            if event.kind=='card':
                card=self.ids[event.name];chunks=[];weights=[]
                for start in range(0,len(self.states),self.block_rows):
                    yield
                    source=self.states[start:start+self.block_rows]
                    keep=np.any(source[:,:4]==card,axis=1)
                    part=source[keep];weight=self.weights[start:start+self.block_rows][keep]
                    if not len(part):continue
                    slot=(part[:,:4]==card).argmax(axis=1)
                    part[np.arange(len(part)),slot]=0;part[:,:4].sort(axis=1)
                    part[:,4+self.queue_len]=card
                    chunks.append(part);weights.append(weight)
                yield
                if not chunks:raise ValueError('no train deck/order is consistent with public plays')
                self.states=np.concatenate(chunks);self.weights=np.concatenate(weights)
                self.cumulative=np.cumsum(self.weights);self.queue_len+=1
                self.elixir=max(0.,self.elixir-self.costs[event.name]);self._derived=None
            elif event.kind=='ability':
                self.elixir-=event.amount
                if self.elixir<0:raise ValueError('public ability was unaffordable')
            elif event.kind=='collector':self.elixir=min(10.,self.elixir+event.amount)
            else:raise ValueError(f'unknown public event {event.kind}')
            self.events.append(event)
        yield from self._advance_work(tick)

    def update(self,tick,events,*,deadline=None,clock=time.monotonic):
        if deadline is None:
            self._pending=None
            return super().update(tick,events)
        while True:
            pending=getattr(self,'_pending',None)
            if pending is None:
                tx=copy.copy(self);tx.events=list(self.events);tx._pending=None
                history=tuple(events);work=tx._update_work(tick,history)
                pending=self._pending=(tick,history,tx,work)
            oldtick,history,tx,work=pending
            if tuple(events[:len(history)])!=history:raise ValueError('public events changed')
            while True:
                if clock()>=deadline:raise TimeoutError('K-v2 belief cutoff')
                try:next(work)
                except StopIteration:
                    if clock()>=deadline:raise TimeoutError('K-v2 belief cutoff')
                    self.__dict__.update(tx.__dict__);self._pending=None
                    break
            if oldtick==tick and len(history)==len(events):return

    def derived(self):
        if not hasattr(self,'_deadline') or self._deadline is None:return super().derived()
        if self._derived is None:
            first=self.states[0];same=np.ones(self.states.shape[1],dtype=bool)
            for start in range(0,len(self.states),self.block_rows):
                self.check();same &= np.all(self.states[start:start+self.block_rows]==first,axis=0)
            self.check()
            names=lambda a:tuple(self.names[int(x)-1] if x else None for x in a)
            queue=names(first[4:4+self.queue_len])
            self._derived=dict(hand=names(first[:4]) if all(same[:4]) else None,
                cycle=queue if all(same[4:4+self.queue_len]) else None,
                next_card=queue[0] if same[4] else None,
                cycle_positions=queue,cycle_positions_known=tuple(map(bool,same[4:4+self.queue_len])))
        return self._derived

    def sample(self,rng,*,deadline=None,clock=time.monotonic):
        self._deadline,self._clock=deadline,clock
        try:
            self.check()
            return super().sample(rng)
        finally:self._deadline=None
