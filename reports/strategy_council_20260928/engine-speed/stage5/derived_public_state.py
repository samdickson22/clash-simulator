"""C56 posterior and exact resource ledger from timestamped public events.

Champion cards use this engine's ordinary cycle. Ability and Collector events
change resources only. Heal Spirit has no resource effect. Opponent hand slots
are unobservable, so quotient out the 4! slot permutations exactly.
"""
from __future__ import annotations
from dataclasses import dataclass
import itertools
import numpy as np


@dataclass(frozen=True)
class PublicEvent:
    tick: int
    kind: str
    name: str = ''
    amount: float = 0.0


class DerivedPublicState:
    def __init__(self, prior, costs):
        self.names = tuple(sorted(costs))
        self.ids = {n:i+1 for i,n in enumerate(self.names)}
        self.costs = costs
        if len(self.names)>255:
            raise ValueError('C56 posterior supports at most255 cards')
        orders=[]
        for hand in itertools.combinations(range(8),4):
            for queue in itertools.permutations(i for i in range(8) if i not in hand):
                orders.append((*hand,*queue))
        orders=np.asarray(orders,dtype=np.uint8)
        states=[]; weights=[]
        for deck in prior['decks']:
            cards=np.asarray(sorted(self.ids[n] for n in deck['cards']),dtype=np.uint8)
            if len(cards)!=8 or len(set(cards))!=8:
                raise ValueError('prior must contain eight distinct cards')
            a=np.zeros((len(orders),12),dtype=np.uint8)
            a[:,:8]=cards[orders]
            states.append(a)
            weights.append(np.full(len(orders),deck.get('frequency',deck.get('sampling_weight',1.)),dtype=np.float64))
        self.states=np.concatenate(states);self.weights=np.concatenate(weights)
        self.cumulative=np.cumsum(self.weights)
        self.tick=0; self.refill=0; self.queue_len=4; self.elixir=6.0
        self.events=[];self._derived=None
        self.derived()

    def advance(self,tick):
        if tick<self.tick:
            raise ValueError('public time moved backwards')
        while self.tick<tick:
            self.tick+=1
            rate=.93 if self.tick>4800 else 1.4 if self.tick>2400 else 2.8
            self.elixir=min(10.,(round(self.elixir*10000)+int(500/rate))/10000) if self.elixir<10. else self.elixir
            self.refill=max(0,self.refill-50)
            if self.refill==0 and self.queue_len>4:
                # Hands stay sorted; zero is the first empty slot. Queue order
                # is retained and is never sorted.
                self.states[:,0]=self.states[:,4]
                self.states[:,:4].sort(axis=1)
                self.states[:,4:-1]=self.states[:,5:]
                self.states[:,-1]=0
                self.queue_len-=1
                self.refill=1000 if self.tick<2400 else 500 if self.tick<4800 else 350
                self._derived=None

    def update(self,tick,events):
        if list(events[:len(self.events)])!=self.events:
            raise ValueError('public events changed')
        for event in events[len(self.events):]:
            self.advance(event.tick)
            if event.kind=='card':
                card=self.ids[event.name]
                keep=np.any(self.states[:,:4]==card,axis=1)
                self.states=self.states[keep];self.weights=self.weights[keep]
                if not len(self.states):
                    raise ValueError('no train deck/order is consistent with public plays')
                self.cumulative=np.cumsum(self.weights)
                slot=(self.states[:,:4]==card).argmax(axis=1)
                self.states[np.arange(len(self.states)),slot]=0
                self.states[:,:4].sort(axis=1)
                self.states[:,4+self.queue_len]=card;self.queue_len+=1
                self.elixir=max(0.,self.elixir-self.costs[event.name])
                self._derived=None
            elif event.kind=='ability':
                self.elixir-=event.amount
                if self.elixir<0:
                    raise ValueError('public ability was unaffordable')
            elif event.kind=='collector':
                self.elixir=min(10.,self.elixir+event.amount)
            else:
                raise ValueError(f'unknown public event {event.kind}')
            self.events.append(event)
        self.advance(tick)

    def derived(self):
        if self._derived is None:
            first=self.states[0]
            same=np.all(self.states==first,axis=0)
            names=lambda a:tuple(self.names[int(x)-1] if x else None for x in a)
            queue=names(first[4:4+self.queue_len])
            self._derived=dict(hand=names(first[:4]) if all(same[:4]) else None,
                cycle=queue if all(same[4:4+self.queue_len]) else None,
                next_card=queue[0] if same[4] else None,
                cycle_positions=queue,cycle_positions_known=tuple(map(bool,same[4:4+self.queue_len])))
        return self._derived

    def sample(self,rng):
        known=self.derived()
        i=0 if known['hand'] is not None and known['cycle'] is not None else int(np.searchsorted(self.cumulative,rng.random()*self.cumulative[-1],side='right'))
        row=self.states[i]
        names=lambda a:[self.names[int(x)-1] if x else None for x in a]
        return dict(elixir=self.elixir,hand=names(row[:4]),cycle=names(row[4:4+self.queue_len]),refill=self.refill)
