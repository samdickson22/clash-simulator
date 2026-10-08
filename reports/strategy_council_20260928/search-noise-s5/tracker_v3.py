"""T2 resource lattice with a train-prior-constrained, recovering cycle filter.

The cycle uses only detached public cues, compatible train decks, and elapsed
public time. All truth is external to this module. Perfect mode retains ELT.
"""
import copy,itertools,math
from collections import Counter,deque
from functools import lru_cache
import numpy as np
from tracker_v2 import TrackerV2,VALUES,N
from derived_d1 import DerivedD1,PublicEvent

class TrackerV3(TrackerV2):
    def __init__(self,*args,beam=64,hand_calibration=None,**kwargs):
        super().__init__(*args,beam=beam,**kwargs)
        decks=Counter()
        for row in self.prior['decks']:decks[tuple(sorted(row['cards']))]+=row.get('frequency',row.get('sampling_weight',1.))
        self.decks=[(frozenset(d),w) for d,w in decks.items()]
        self.hand_calibration=hand_calibration

    @lru_cache(maxsize=4096)
    def support(self,revealed):
        rs=set(revealed);ds=[(d,w) for d,w in self.decks if rs<=d];z=sum(w for _,w in ds)
        return tuple((d,w/z) for d,w in ds) if z else ()

    @lru_cache(maxsize=4096)
    def presence(self,revealed):
        out=Counter()
        for deck,w in self.support(revealed):
            for name in deck:out[name]+=w
        return out

    def availability(self,d,name):
        if name in d.queue or len(d.queue)>=8:return 0.
        if name in d.revealed:return 1.
        known_hand=len(d.revealed-set(d.queue))
        slots=max(0,8-len(d.queue)-known_hand)
        unknown=8-len(d.revealed)
        return (slots/unknown if unknown else 0.)*self.presence(tuple(sorted(d.revealed))).get(name,0.)

    def accept_cycle(self,d,name,tick):
        x=self._clone_hand(d);x.advance(max(x.tick,tick));p=self.availability(x,name)
        if not p:return None,0.
        x.elixir=10.
        try:x.accept(PublicEvent(x.tick,'card',name))
        except (ValueError,KeyError):return None,0.
        return x,p

    def _hands_event(self,hands,e):
        if e.kind!='card':return hands
        branches=[]
        # Missing plays are possible in every gap, not only contradictions.
        for rank,(d,w) in enumerate(sorted(hands,key=lambda x:-x[1])):
            gap=max(0,e.tick-d.tick)
            play_rate=(self.n_events+4)/max(20.,e.tick/20.*max(.1,self.recall))
            hazard=min(.40,play_rate*self.miss*gap/20.)
            options=[(d,1-hazard)]
            if rank<8 and hazard and gap>=2:
                latent_tick=max(d.tick,e.tick-20)
                at=self._clone_hand(d);at.advance(latent_tick)
                possibles={name:p*self.availability(at,name) for name,p in self.presence(tuple(sorted(at.revealed))).items()}
                z=sum(possibles.values())
                for name,p in possibles.items():
                    if not p:continue
                    x,_=self.accept_cycle(at,name,latent_tick)
                    if x is not None:options.append((x,hazard*p/z))
            else:options[0]=(d,1.)
            for state,prob in options:
                x=self._clone_hand(state);x.advance(max(x.tick,e.tick))
                if e.q<1:branches.append((x,w*prob*(1-e.q)))
                for name,p in e.cards:
                    y,likelihood=self.accept_cycle(x,name,e.tick)
                    if y is not None:branches.append((y,w*prob*e.q*p*likelihood))
        # Small restart component forgets old erroneous reveals. Later legal
        # sequences identify its deck and ordered suffix, permitting recovery.
        reset=DerivedD1(self.costs);reset.tick=e.tick
        branches.append((reset,.0005))
        for name,p in e.cards:
            x,likelihood=self.accept_cycle(reset,name,e.tick)
            if x is not None:branches.append((x,.001*e.q*p*likelihood))
        merged={}
        for d,w in branches:
            key=(tuple(d.queue),d.refill,tuple(sorted(d.revealed)),d.last_card)
            if key in merged:merged[key][1]+=w
            else:merged[key]=[d,w]
        ordered=sorted(merged.values(),key=lambda x:-x[1]);lost=sum(w for _,w in ordered[self.beam-1:])
        ordered=ordered[:self.beam-1];ordered.append((reset,lost+.0005));z=sum(w for _,w in ordered)
        return [(d,w/z) for d,w in ordered]

    @lru_cache(maxsize=4096)
    def resolved_options(self,queue,revealed):
        """Conservative mass: unresolved inner queue orders contribute zero."""
        masses=Counter();known=set(queue)-{None};unknown=queue.count(None)
        for deck,prob in self.support(revealed):
            remaining=deck-set(revealed)
            if unknown and len(remaining)!=unknown:continue
            hand=tuple(sorted(deck-known-(remaining if unknown else set())))+(None,)*(len(queue)-4)
            if len(hand)==4:masses[hand]+=prob
        return tuple(masses.items())

    def hand_masses(self):
        masses=Counter()
        for d,w in self._hands:
            x=self._clone_hand(d);x.advance(self.tick)
            for hand,prob in self.resolved_options(tuple(x.queue),tuple(sorted(x.revealed))):masses[hand]+=w*prob
        return masses

    def distribution(self):
        if self.perfect:return super().distribution()
        if self._distribution is not None:return self._distribution
        # Preserve T2's exact same resource output; replace only hand summaries.
        d=dict(super().distribution());masses=self.hand_masses()
        best,raw=max(masses.items(),key=lambda x:x[1],default=(None,0.))
        last=max((x.tick for x,_ in self._hands),default=0)
        rate=(self.n_events+4)/max(20.,self.tick/20.*max(.1,self.recall))
        mass=raw*math.exp(-rate*self.miss*max(0,self.tick-last)/20.)
        if self.hand_calibration:
            edges=self.hand_calibration['edges'];values=self.hand_calibration['values']
            mass=float(values[min(len(values)-1,int(np.searchsorted(edges,mass,side='right')))])
        d.update(hand=best if mass>=.9 else None,hand90=best if mass>=.9 else None,
                 best_hand=best,hand90_mass=mass,raw_hand_mass=raw,concentrated=mass>=.9)
        self._distribution=d;return d

    def sample(self,rng):
        if self.perfect:return super().sample(rng)
        weights=np.array([w for _,w in self._hands]);weights/=weights.sum()
        d=self._clone_hand(self._hands[int(rng.choice(len(weights),p=weights))][0]);d.advance(self.tick)
        support=self.support(tuple(sorted(d.revealed)))
        if not support:
            d=DerivedD1(self.costs);d.advance(self.tick);support=self.support(())
        deck,prob=support[int(rng.choice(len(support),p=[w for _,w in support]))]
        unknown=sorted(deck-d.revealed);rng.shuffle(unknown)
        queue=[n if n is not None else unknown.pop() for n in d.queue]
        hand=sorted(deck-set(queue))+[None]*(len(queue)-4)
        elixir=min(N-1,int(np.searchsorted(np.cumsum(self._p),rng.random())))/10000.
        return dict(hand=hand,cycle=queue,refill=d.refill,elixir=elixir)
