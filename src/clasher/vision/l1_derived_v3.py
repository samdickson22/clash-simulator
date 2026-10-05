"""Sampleable opponent posterior from noisy public events and visible time.

Unrevealed deck slots are latent tokens. No episode deck assignment or native
state is accepted. Missed-play rate and event probabilities require validation
calibration; this module never calls its particle spread a calibrated interval.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np


class StreamPublicClock:
    """Read the visible overtime background as well as the clock digits."""
    def __init__(self):
        self.tick=0.;self.media=None;self.overtime=False

    def update(self,seconds,timestamp_ms,phase):
        elapsed=0. if self.media is None else max(0.,timestamp_ms-self.media)/50
        predicted=self.tick+elapsed
        if phase=='overtime':self.overtime=True
        if seconds is not None:
            base=300 if self.overtime else 180
            low=max(0.,(base-seconds)*20+1);high=low+19
            predicted=(low+high)/2 if self.media is None else float(np.clip(predicted,low,high))
        self.tick=max(self.tick,predicted);self.media=timestamp_ms
        return round(self.tick)


class OpponentPosterior:
    def __init__(self, costs, *, particles=2048, missed_plays_per_second=.015,
                 concentration=.9, seed=0, calibration_residuals=None):
        if len(costs)<8 or any(not 0<float(c)<=10 for c in costs.values()):
            raise ValueError('Need a public roster with valid card costs')
        if particles<32 or not 0<=missed_plays_per_second<=2 or not .5<concentration<=1:
            raise ValueError('Invalid posterior configuration')
        self.names=tuple(sorted(costs));self.ids={n:i for i,n in enumerate(self.names)}
        self.costs=np.array([costs[n] for n in self.names])
        self.n=particles;self.rng=np.random.default_rng(seed)
        self.missed_rate=missed_plays_per_second;self.concentration=concentration
        self.cards=np.full((particles,8),-1,dtype=np.int16)
        self.hand=np.tile(np.arange(4,dtype=np.int16),(particles,1))
        self.queue=np.tile(np.array([4,5,6,7,-1,-1,-1,-1],dtype=np.int16),(particles,1))
        self.qlen=np.full(particles,4,dtype=np.int16)
        self.refill=np.zeros(particles,dtype=np.int16)
        self.elixir=np.full(particles,60000,dtype=np.int64)
        self.weights=np.full(particles,1/particles)
        self.tick=0;self.seen=set();self.diagnostics=defaultdict(int)
        self._late_entry=False
        self.calibration_residuals=np.asarray([0.] if calibration_residuals is None else calibration_residuals,dtype=float)
        if (not self.calibration_residuals.size or self.calibration_residuals.ndim!=1 or
                not np.isfinite(self.calibration_residuals).all() or np.any(abs(self.calibration_residuals)>10)):
            raise ValueError('Invalid validation residual distribution')
        self.calibrated=calibration_residuals is not None
        self.calibration_residuals.sort()

    def start_at(self,tick,*,elixir_bounds=(0.,10.)):
        """Enter a mid-match public stream without inventing its unseen history."""
        if self.tick!=0 or self.seen or self._late_entry:
            raise ValueError('Late entry is only valid before the first observation')
        lo,hi=map(float,elixir_bounds)
        if type(tick) is not int or tick<0 or not 0<=lo<=hi<=10:
            raise ValueError('Invalid public entry prior')
        self.tick=tick;self._late_entry=True
        self.elixir=np.rint(np.linspace(lo*10000,hi*10000,self.n)).astype(np.int64)

    def _play(self, i, slot, card):
        if self.hand[i,slot]<0 or self.qlen[i]>=8 or self.elixir[i]<round(self.costs[card]*10000):
            return False
        token=self.hand[i,slot]
        self.cards[i,token]=card
        self.hand[i,slot]=-1
        self.queue[i,self.qlen[i]]=token;self.qlen[i]+=1
        self.elixir[i]-=round(self.costs[card]*10000)
        return True

    def _refill(self):
        rows=np.flatnonzero((self.refill==0)&(self.qlen>4))
        if not len(rows):return
        slots=(self.hand[rows]<0).argmax(axis=1)
        self.hand[rows,slots]=self.queue[rows,0]
        self.queue[rows,:-1]=self.queue[rows,1:]
        self.queue[rows,-1]=-1;self.qlen[rows]-=1
        self.refill[rows]=20 if self.tick<2400 else 10 if self.tick<4800 else 7

    def advance(self,tick):
        if type(tick) is not int or tick<self.tick:
            raise ValueError('Public tick must be a monotone integer')
        while self.tick<tick:
            self.tick+=1
            rate=.93 if self.tick>4800 else 1.4 if self.tick>2400 else 2.8
            self.elixir=np.minimum(100000,self.elixir+int(500/rate))
            self.refill=np.maximum(0,self.refill-1);self._refill()
            # Branch for genuinely unobserved plays, even without a later contradiction.
            rows=np.flatnonzero(self.rng.random(self.n)<self.missed_rate/20)
            for i in rows:
                slots=np.flatnonzero(self.hand[i]>=0)
                if not len(slots):continue
                slot=int(self.rng.choice(slots));token=self.hand[i,slot];card=int(self.cards[i,token])
                if card<0:
                    available=np.setdiff1d(np.arange(len(self.names)),self.cards[i],assume_unique=False)
                    card=int(self.rng.choice(available))
                if self._play(i,slot,card):self.diagnostics['latent_plays']+=1

    def observe(self,tick,events):
        self.advance(tick)
        for event in events:
            if event.player_id!=0 or event.event_id in self.seen:continue
            self.seen.add(event.event_id)
            if event.card not in self.ids:
                self.diagnostics['unknown_events']+=1;continue
            card=self.ids[event.card];confidence=float(np.clip(event.confidence,0.,1.))
            likelihood=np.zeros(self.n);slots=np.full(self.n,-1,dtype=int)
            for i in range(self.n):
                hand_slots=np.flatnonzero(self.hand[i]>=0)
                known=np.flatnonzero(self.cards[i]==card)
                if len(known):
                    matches=hand_slots[self.hand[i,hand_slots]==known[0]]
                    if len(matches):slots[i]=int(matches[0]);likelihood[i]=1.
                else:
                    unknown=hand_slots[self.cards[i,self.hand[i,hand_slots]]<0]
                    if len(unknown):
                        slots[i]=int(self.rng.choice(unknown))
                        remaining_roster=len(self.names)-np.count_nonzero(self.cards[i]>=0)
                        remaining_tokens=np.count_nonzero(self.cards[i]<0)
                        likelihood[i]=len(unknown)/remaining_tokens*remaining_tokens/remaining_roster
                if self.elixir[i]<round(self.costs[card]*10000) or self.qlen[i]>=8:
                    likelihood[i]=0.
                else:
                    likelihood[i]/=max(1,len(hand_slots))
            # Separate false-positive and accepted-event branches. Sample the
            # branch only after computing its complete marginal weight.
            accept=confidence*likelihood
            skip=np.full(self.n,(1-confidence)/len(self.names))
            evidence=accept+skip
            if not np.any(evidence>0):
                # An impossible confidence-one observation is a detector/model
                # contradiction. Preserve the prior and expose it to callers.
                self.diagnostics['contradictions']+=1;continue
            self.weights*=evidence
            total=self.weights.sum()
            if not np.isfinite(total) or total<=0:raise ValueError('Invalid posterior mass')
            self.weights/=total
            chosen=self.rng.random(self.n)<np.divide(accept,evidence,out=np.zeros_like(accept),where=evidence>0)
            for i in np.flatnonzero(chosen):
                if slots[i]>=0:self._play(i,slots[i],card)
            self.diagnostics['observed_events']+=1
            self.diagnostics['accepted_particle_branches']+=int(chosen.sum())
            if 1/np.square(self.weights).sum()<self.n*.6:
                positions=(np.arange(self.n)+self.rng.random())/self.n
                indices=np.searchsorted(np.cumsum(self.weights),positions,side='right').clip(max=self.n-1)
                for attr in ('cards','hand','queue','qlen','refill','elixir'):
                    setattr(self,attr,getattr(self,attr)[indices].copy())
                self.weights.fill(1/self.n)
        return self.distribution()

    def _hand(self,i):
        values=[]
        for token in self.hand[i]:
            values.append(None if token<0 else '?' if self.cards[i,token]<0 else self.names[self.cards[i,token]])
        return tuple(sorted(values,key=lambda x:'' if x is None else x))

    def distribution(self):
        if self.calibrated:
            values=np.clip(float(self.weights@(self.elixir/10000))+self.calibration_residuals,0,10)
            weights=np.full(len(values),1/len(values))
        else:
            values=self.elixir/10000;weights=self.weights
        order=np.argsort(values);cdf=np.cumsum(weights[order])
        quantile=lambda p:float(values[order[min(np.searchsorted(cdf,p),len(values)-1)]])
        hands=defaultdict(float)
        for i,w in enumerate(self.weights):hands[self._hand(i)]+=float(w)
        best=max(hands,key=hands.get);mass=hands[best]
        known='?' not in best
        mean=float(weights@values)
        return dict(elixir_mean=mean,elixir_sd=float(np.sqrt(weights@np.square(values-mean))),
            elixir_interval_90=[quantile(.05),quantile(.95)],elixir_bounds=[float(values.min()),float(values.max())],
            hand=best if known and mass>=self.concentration else None,
            hand_probability=mass if known else 0.,effective_particles=float(1/np.square(self.weights).sum()),
            concentration_threshold=self.concentration,calibrated=self.calibrated)

    def sample(self,rng):
        """Use either NumPy or random.Random; refill follows the reference's ms key."""
        i=min(self.n-1,int(np.searchsorted(np.cumsum(self.weights),rng.random(),side='right')))
        mapping=self.cards[i].copy()
        unknown=np.flatnonzero(mapping<0)
        available=np.setdiff1d(np.arange(len(self.names)),mapping).tolist()
        for token in unknown:
            mapping[token]=available.pop(min(len(available)-1,int(rng.random()*len(available))))
        name=lambda token:None if token<0 else self.names[mapping[token]]
        if self.calibrated:
            # Preserve the particle's elixir/hand rank dependence while mapping
            # its marginal uncertainty to validation's observed prediction errors.
            lower=float(self.weights[self.elixir<self.elixir[i]].sum())
            equal=float(self.weights[self.elixir==self.elixir[i]].sum())
            u=lower+rng.random()*equal
            residual=self.calibration_residuals[min(len(self.calibration_residuals)-1,int(u*len(self.calibration_residuals)))]
            elixir=float(np.clip(self.weights@(self.elixir/10000)+residual,0,10))
        else:elixir=float(self.elixir[i]/10000)
        return dict(elixir=elixir,hand=[name(t) for t in self.hand[i]],
            cycle=[name(t) for t in self.queue[i,:self.qlen[i]]],refill=int(self.refill[i])*50)
