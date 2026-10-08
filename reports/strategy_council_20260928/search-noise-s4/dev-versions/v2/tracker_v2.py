"""Fair S3 resource lattice + deck-free cycle mixture.

Only public candidates and detached body sightings enter this module. Resources
use the engine's 1/10000-elixir lattice (100001 states), never a truncated beam.
A fixed-lag replay fuses detections and board births before committing evidence.
"""
import copy
import json
import math
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from derived_d1 import DerivedD1, PublicEvent
from elt import ELT, Candidate

HERE = Path(__file__).resolve().parent
MODEL = json.loads((HERE / 'noise-model.json').read_text())
N = 100001
VALUES = np.arange(N) / 10000.

def regen(a, b):
    return sum(max(0, min(b, end)-max(a, start))*rate
               for start, end, rate in ((0,2400,178),(2400,4800,357),(4800,10**9,537)))

def shift(p, units):
    """Exact capped lattice transition, including negative resource evidence."""
    out = np.zeros_like(p)
    if units >= N-1: out[-1] = p.sum()
    elif units <= -N+1: out[0] = p.sum()
    elif units > 0:
        out[units:] = p[:-units]; out[-1] += p[-units:].sum()
    elif units < 0:
        k = -units; out[:-k] = p[k:]; out[0] += p[:k].sum()
    else: out[:] = p
    return out

@dataclass
class Evidence:
    tick: int
    cards: tuple
    q: float
    source: str
    kind: str = 'card'
    amount: float = 0.
    board: bool = False
    detected: bool = False

class TrackerV2:
    def __init__(self, prior, costs, *, recall=1., precision=1., initial=None,
                 body_cards=None, beam=48, calibration=0., **unused):
        self.costs = dict(costs); self.prior = prior
        self.recall = recall; self.precision = precision
        self.perfect = recall == precision == 1.
        self.exact = ELT(prior, costs, initial=initial) if self.perfect else None
        self.tick = 0; self.base_tick = 0; self.beam = beam
        self.calibration = calibration; self.body_cards = body_cards or {}
        self.p = np.zeros(N); self.p[60000] = 1.
        self.hands = [(DerivedD1(costs), 1.)]
        self.pending = []; self.seen_events = set(); self.tracks = []
        self.births = []; self.serial = 0; self.metrics = Counter()
        self._p = self.p; self._hands = self.hands; self._distribution = None
        # Prior source is measured rates, scaled to the registered event level.
        self.confusion = MODEL['confusion_rate']*(1-recall)/(1-MODEL['recall'])
        self.miss = max(0., 1-recall-self.confusion)
        self.spurious = max(0., recall*(1-precision)/precision-self.confusion)
        self.n_events = 0
        self.recent = []
        card_weight = Counter()
        for deck in prior['decks']:
            for name in deck['cards']: card_weight[name] += deck.get('frequency',deck.get('sampling_weight',1.))
        self.card_weight = card_weight
        total = sum(card_weight.values())
        self.cost_prior = Counter()
        for name, w in card_weight.items(): self.cost_prior[round(costs[name]*10000)] += w/total

    def observe(self, candidate):
        """Exact public-event API; noisy adapters should use update_public."""
        if self.perfect:
            self.exact.observe(candidate); self.tick = max(self.tick,candidate.tick); return
        self.pending.append(Evidence(candidate.tick,candidate.cards,candidate.q,'candidate',candidate.kind,candidate.amount))
        self.n_events += 1

    def _clone_hand(self, d):
        x = copy.copy(d); x.queue = deque(d.queue); x.revealed = set(d.revealed)
        x.events = []; x.plays = deque(d.plays,maxlen=8); x.abilities = deque(d.abilities,maxlen=8)
        return x

    def _hands_event(self, hands, e):
        branches = []
        for d, w in hands:
            d = self._clone_hand(d); d.advance(max(d.tick,e.tick))
            if e.q < 1: branches.append((d,w*(1-e.q)))
            for name, prob in e.cards:
                x = self._clone_hand(d)
                # Resource probability lives on the independent full lattice.
                x.elixir = 10.
                try: x.accept(PublicEvent(x.tick,e.kind,name,e.amount))
                except (ValueError,KeyError): continue
                branches.append((x,w*e.q*prob))
        merged = {}
        for d,w in branches:
            key = (tuple(d.queue),d.refill,tuple(sorted(d.revealed)),d.last_card)
            if key in merged: merged[key][1] += w
            else: merged[key] = [d,w]
        ordered = sorted(merged.values(),key=lambda x:-x[1])
        discarded = sum(w for _,w in ordered[self.beam-1:])
        ordered = ordered[:self.beam-1]
        # Reserved abstract state represents ALL unrevealed queues/decks. Pruned
        # mass is transferred here, not silently renormalized out of existence.
        broad = DerivedD1(self.costs); broad.tick = e.tick
        ordered.append([broad,max(.002,discarded)])
        z = sum(w for _,w in ordered)
        return [(d,w/z) for d,w in ordered]

    def _transition(self,p,a,b):
        if b <= a: return p
        out = shift(p,regen(a,b))
        # Unseen spells and unseen bodies remain possible during every gap.
        # Body evidence repairs most misses; keep 25% of the measured hazard.
        play_rate = (self.n_events+4)/max(20.,b/20.*max(.1,self.recall))
        hazard = min(.25,play_rate*self.miss*.25*(b-a)/20.)
        if hazard:
            latent = np.zeros(N)
            for cost,prob in self.cost_prior.items(): latent += prob*shift(out,-cost)
            out = (1-hazard)*out+hazard*latent
        # Continuous broad contamination; constant total mass per second.
        reset = 1-math.exp(-.0005*(b-a)/20.)
        out = (1-reset)*out+reset/N
        return out

    def _resource_event(self,p,e):
        # Uniform component can explain apparent resource excess OR deficit.
        p = .998*p + .002/N
        accepted = np.zeros(N)
        for name,prob in e.cards:
            cost = round((self.costs.get(name,0.) if e.kind=='card' else e.amount)*10000)
            if e.kind == 'collector': accepted += prob*shift(p,cost)
            elif 0 <= cost < N:
                # Three-point execution-time quadrature. A slightly early time
                # must not rule out the true affordable spend near zero elixir.
                jitter=regen(e.tick,e.tick+4)
                for delta,weight in ((-jitter,.25),(0,.5),(jitter,.25)):
                    effective=max(0,cost-delta)
                    if effective>=N:continue
                    # An observed affordable play also diagnoses an underspent
                    # ledger: lift insufficient branches to the public minimum
                    # cost, then spend. This explicit upward resync avoids
                    # rejecting a good cue solely because the ledger is stale.
                    accepted+=prob*weight*shift(p,-effective)
        out = (1-e.q)*p+e.q*accepted
        if out.sum() <= 0: return np.full(N,1/N)
        return out/out.sum()

    def _run(self,p,hands,start,end,events):
        for e in sorted(events,key=lambda e:e.tick):
            t = max(start,min(end,e.tick))
            p = self._transition(p,start,t)
            p = self._resource_event(p,e)
            hands = self._hands_event(hands,e)
            start = t
        return self._transition(p,start,end),hands

    def advance(self,tick):
        if tick < self.tick: raise ValueError('public time moved backwards')
        self.tick = tick; self._distribution = None
        if self.perfect: self.exact.advance(tick); return
        cutoff = max(self.base_tick,tick-32)
        ready = [e for e in self.pending if e.tick<=cutoff]
        self.p,self.hands = self._run(self.p,self.hands,self.base_tick,cutoff,ready)
        self.pending = [e for e in self.pending if e.tick>cutoff]
        self.base_tick = cutoff
        self._p,self._hands = self._run(self.p,self.hands,cutoff,tick,self.pending)

    def _birth(self,tick,cards):
        # Group multi-body spawns into one play; do not count each skeleton.
        names = {n for n,_ in cards}
        if any(tick-t<40 and names & ns for t,ns in self.births): return
        self.births.append((tick,names)); self.births = [(t,ns) for t,ns in self.births if tick-t<80]
        historical=[e for e in self.recent if e.kind=='card' and 0<=tick-e.tick<=80 and names & {n for n,_ in e.cards}]
        choices = [e for e in self.pending if not e.board and e.kind=='card'
                   and abs(e.tick-tick)<=24 and names & {n for n,_ in e.cards}]
        if choices:
            e = min(choices,key=lambda e:abs(e.tick-tick)); e.board = True
            e.q = 1-(1-e.q)*(1-MODEL['entity_precision'])
            self.metrics['board_event_matches'] += 1
        elif historical:
            self.metrics['historical_board_matches']+=1
            return
        else:
            q=self.miss*MODEL['entity_precision']/(self.miss*MODEL['entity_precision']+1-MODEL['entity_precision'])
            self.pending.append(Evidence(max(self.base_tick,tick),cards,q,'board',board=True))
            self.metrics['unmatched_board_births'] += 1

    def update_public(self,tick,events,bodies=()):
        """bodies=(public token,x,y); no engine IDs, RNG, deck or HP required."""
        if self.perfect:
            for e in events:
                key=e.event_id
                if key in self.seen_events: continue
                self.seen_events.add(key)
                self.observe(Candidate(e.tick,((e.name,1.),),1.,kind=e.kind,amount=e.amount))
            self.advance(tick); return
        for e in events:
            if e.event_id in self.seen_events: continue
            self.seen_events.add(e.event_id); self.n_events += e.kind=='card'
            t = max(self.base_tick,e.tick-6)
            matched = next((x for x in self.pending if x.board and not x.detected and abs(x.tick-t)<=24
                            and e.name in dict(x.cards)),None)
            if matched:
                matched.detected = True; matched.cards = ((e.name,1.),)
                matched.q = 1-(1-self.precision)*(1-MODEL['entity_precision'])
                self.metrics['event_board_matches'] += 1
                continue
            # Alternative card labels use ONLY the measured confusion pairs.
            alternatives = [p['truth'] for p in MODEL['confusion_pairs'] if p['predicted']==e.name and p['truth'] in self.costs]
            c = self.confusion/max(.001,self.recall+self.confusion)
            cards = [(e.name,1-c if alternatives else 1.)]
            if alternatives: cards += [(n,c/len(alternatives)) for n in alternatives]
            cue=Evidence(t,tuple(cards),self.precision,'event',e.kind,e.amount,detected=True)
            self.pending.append(cue)
            self.recent.append(cue)
            self.recent=[x for x in self.recent if tick-x.tick<=120]
        # Spatial tracks survive short detection gaps. The match uses only public
        # token/position; row indices and simulator entity IDs are never read.
        remaining = [dict(t) for t in self.tracks if tick-t['last']<=20]
        current = []
        for token,x,y in bodies:
            if token not in self.body_cards: continue
            matches = [(i,(tr['x']-x)**2+(tr['y']-y)**2) for i,tr in enumerate(remaining) if tr['token']==token]
            found = min(matches,key=lambda a:a[1],default=None)
            if found and found[1]<2.25:
                tr = remaining.pop(found[0]); tr.update(x=x,y=y,last=tick,hits=tr['hits']+1)
            else: tr = dict(token=token,x=x,y=y,last=tick,first=tick,hits=1,emitted=False)
            if tr['hits']>=3 and not tr['emitted']:
                tr['emitted']=True
                self._birth(max(self.base_tick,tr['first']-5),self.body_cards[token])
            current.append(tr)
        self.tracks = current+remaining
        self.advance(tick)

    def distribution(self):
        if self.perfect: return self.exact.distribution()
        if self._distribution is not None: return self._distribution
        p = self._p; cdf = np.cumsum(p)
        q = lambda x: min(N-1,int(np.searchsorted(cdf,x)))/10000.
        lo,hi = max(0.,q(.05)-self.calibration),min(10.,q(.95)+self.calibration)
        masses = Counter(); all_known = True; all_hands = []
        for d,w in self._hands:
            x = self._clone_hand(d); x.advance(self.tick)
            known = sorted(x.revealed-set(x.queue))
            hand = tuple(known+[None]*(4-len(known)))
            full = len(known)==8-len(x.queue)
            all_known &= full
            all_hands.append(hand if full else None)
            if full: masses[hand] += w
        best,mass = max(masses.items(),key=lambda x:x[1],default=(None,0.))
        unanimous = all_hands[0] if all_known and all(h==all_hands[0] for h in all_hands) else None
        # Probability mass of a resolved hand, not unanimity of tiny branches.
        self._distribution = dict(elixir_mean=float(np.dot(p,VALUES)),elixir_interval_90=[lo,hi],
            elixir_q90=q(.9),hand=unanimous,hand90=best if mass>=.9 else None,
            hand90_mass=mass,concentrated=bool(mass>=.9),hypotheses=len(self._hands),
            fallback_mass=float(self._hands[-1][1]),resource_support=int(np.count_nonzero(p)))
        return self._distribution

    def sample(self,rng):
        if self.perfect: return self.exact.sample(rng)
        weights=np.array([w for _,w in self._hands]); weights/=weights.sum()
        d=self._clone_hand(self._hands[int(rng.choice(len(weights),p=weights))][0]);d.advance(self.tick)
        revealed=d.revealed
        decks=[x for x in self.prior['decks'] if revealed<=set(x['cards'])]
        if not decks:
            decks=self.prior['decks']; d=DerivedD1(self.costs);d.advance(self.tick)
        w=np.array([x.get('frequency',x.get('sampling_weight',1.)) for x in decks],float);w/=w.sum()
        deck=list(decks[int(rng.choice(len(decks),p=w))]['cards'])
        known=set(n for n in d.queue if n)|d.revealed
        unknown=[n for n in deck if n not in known];rng.shuffle(unknown)
        cycle=[n if n is not None else unknown.pop() for n in d.queue]
        hand=sorted((d.revealed-set(d.queue))|set(unknown))
        hand += [None]*(4-len(hand))
        elixir=min(N-1,int(np.searchsorted(np.cumsum(self._p),rng.random())))/10000.
        return dict(elixir=elixir,hand=hand,cycle=cycle,refill=d.refill)
