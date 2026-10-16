"""Bounded public-event hypotheses for noisy screen-derived card plays.

The exact transition implementation is injected from a pinned local copy.
No opponent HUD, deck assignment, or evaluation truth enters this class.
"""
from copy import copy
from dataclasses import dataclass
import math

import numpy as np


class PublicTickClock:
    """Elapsed ticks from visible clock intervals and media-time increments."""
    def __init__(self):
        self.tick=0.;self.media=None

    def update(self,seconds_remaining,timestamp_ms):
        elapsed=0. if self.media is None else max(0.,timestamp_ms-self.media)/50
        predicted=self.tick+elapsed
        if seconds_remaining is not None:
            base=180 if seconds_remaining<=180 and predicted<=3600 else 300
            low=max(0.,(base-seconds_remaining)*20+1)
            high=low+19
            predicted=(low+high)/2 if self.media is None else float(np.clip(predicted,low,high))
        self.tick=max(self.tick,predicted);self.media=timestamp_ms
        return round(self.tick)


@dataclass
class Hypothesis:
    state: object
    log_weight: float
    skipped: int = 0
    inserted: int = 0


def clone(state):
    out=copy(state)
    out.states=state.states.copy()
    out.weights=state.weights.copy()
    out.cumulative=state.cumulative.copy()
    out.history=list(state.history)
    out._derived=None
    return out


class RobustPublicState:
    """Accept/skip beam, affordability checks, and one-missed-play recovery.

    A contradiction can admit one earlier missing play, scored below directly
    seen plays. Other surviving hypotheses remain; recovery never makes a
    certainty claim. Hands are returned only above the posterior threshold.
    Elixir is the posterior mean and its range remains available for auditing.
    """
    def __init__(self, exact_type, prior, costs, *, beam=6, certainty=.9):
        self.costs=dict(costs);self.beam=beam;self.certainty=certainty
        state=exact_type(prior,costs)
        # Opponent UI slots are hidden; merge their permutations without losing
        # any hand multiset / queue hypothesis or prior probability mass.
        state.states[:,:4]=np.sort(state.states[:,:4],axis=1)
        unique,inverse=np.unique(state.states,axis=0,return_inverse=True)
        weights=np.bincount(inverse,weights=state.weights)
        state.states=unique;state.weights=weights;state.cumulative=np.cumsum(weights)
        state._derived=None
        self.hypotheses=[Hypothesis(state,0.)]
        self.time=0;self.last_event_tick=0;self.event_ids=set()
        self.diagnostics=dict(duplicates=0,unknown_cards=0,unaffordable=0,
                              accepted_branches=0,skip_branches=0,recovery_branches=0)

    def _accept(self,hyp,tick,card,confidence,*,inserted=False):
        s=clone(hyp.state)
        if tick<s.tick:return None
        s.advance(tick)
        if s.elixir_units+500<round(self.costs[card]*10000):
            self.diagnostics['unaffordable']+=1
            return None
        if s.queue_len>=8:return None
        keep=np.any(s.states[:,:4]==s.ids[card],axis=1)
        if not keep.any():return None
        mass=float(s.weights[keep].sum()/s.weights.sum())
        s.update(tick,[*s.history,(tick,card)])
        return Hypothesis(s,hyp.log_weight+math.log(confidence)+math.log(max(mass,1e-12)),
                          hyp.skipped,hyp.inserted+int(inserted))

    def observe(self,tick,events):
        tick=int(tick)
        if tick<self.time:raise ValueError('Public clock moved backwards')
        for event in events:
            if event.player_id!=0:continue
            if event.event_id in self.event_ids:
                self.diagnostics['duplicates']+=1;continue
            self.event_ids.add(event.event_id)
            if event.card not in self.costs:
                self.diagnostics['unknown_cards']+=1;continue
            confidence=float(np.clip(event.confidence,.55,.995))
            branches=[]
            for h in self.hypotheses:
                # Ignoring an uncertain event always leaves a valid posterior.
                skipped=clone(h.state);skipped.advance(tick)
                branches.append(Hypothesis(skipped,h.log_weight+math.log((1-confidence)/len(self.costs)),h.skipped+1,h.inserted))
                self.diagnostics['skip_branches']+=1
                accepted=self._accept(h,tick,event.card,confidence)
                if accepted:
                    branches.append(accepted);self.diagnostics['accepted_branches']+=1
                else:
                    # A missing play can explain an unavailable card by cycling
                    # the queue. Try only after a full refill interval has elapsed.
                    missing_tick=max(h.state.tick,self.last_event_tick+1,tick-24)
                    if tick-missing_tick>=20:
                        for missing in self.costs:
                            repaired=self._accept(h,missing_tick,missing,.03/len(self.costs),inserted=True)
                            if repaired:
                                candidate=self._accept(repaired,tick,event.card,confidence)
                                if candidate:
                                    branches.append(candidate)
                                    self.diagnostics['recovery_branches']+=1
            branches.sort(key=lambda h:h.log_weight,reverse=True)
            self.hypotheses=branches[:self.beam]
            normalizer=self.hypotheses[0].log_weight
            for h in self.hypotheses:h.log_weight-=normalizer
            self.last_event_tick=tick
        self.time=tick
        return self.derived()

    def derived(self):
        weights=np.exp([h.log_weight for h in self.hypotheses]);weights/=weights.sum()
        current=[]
        for h in self.hypotheses:
            s=clone(h.state);s.advance(self.time);current.append(s)
        elixirs=[s.elixir_units/10000 for s in current]
        hands={}
        for s,w in zip(current,weights):
            rows=np.sort(s.states[:,:4],axis=1)
            values,inverse=np.unique(rows,axis=0,return_inverse=True)
            mass=np.bincount(inverse,weights=s.weights);mass/=mass.sum()
            for row,p in zip(values,mass):
                hand=tuple(s.names[int(n)-1] if n else None for n in row)
                hands[hand]=hands.get(hand,0.)+float(w*p)
        best=max(hands,key=hands.get);confidence=hands[best]
        return dict(elixir=float(np.dot(weights,elixirs)),elixir_range=[min(elixirs),max(elixirs)],
                    hand=best if confidence>=self.certainty else None,hand_confidence=confidence,
                    hypotheses=len(self.hypotheses),posterior_mass=weights.tolist(),
                    skipped=[h.skipped for h in self.hypotheses],inserted=[h.inserted for h in self.hypotheses])
