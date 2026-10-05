import bootstrap
from bootstrap import HERE
import json,time
from types import SimpleNamespace
from collections import Counter
import numpy as np
from fair_player import PublicPlanner
from derived_public_state import DerivedPublicState,PublicEvent
from clasher.rl.c56_rollout_planner import C56SearchConfig,C56RolloutPlanner
from clasher.vision.l1_derived_v3 import OpponentPosterior
from noise import VARIANTS,MODEL

class Prior:
    def __init__(self,catalog):
        self.decks=[d['cards'] for d in catalog['decks']];self.cdf=np.cumsum([d['frequency'] for d in catalog['decks']],dtype=float);self.cdf/=self.cdf[-1]
    def sample(self,rng):
        deck=list(self.decks[int(np.searchsorted(self.cdf,rng.random()))]);rng.shuffle(deck)
        return dict(elixir=float(rng.uniform(0,10)),hand=deck[:4],cycle=deck[4:],refill=0)

class Player:
    def __init__(self,resources,catalog,seed,variant):
        self.resources=resources;self.flags=VARIANTS[variant];self.variant=variant;self.rng=np.random.default_rng(seed+1)
        self.core=C56RolloutPlanner(resources.builder,resources.bots,backend='native',seed=seed,native=resources.native,native_config=resources.config,
            config=C56SearchConfig(deadline_seconds=.2,threads=2))
        self.events_seen=0;self.diagnostics=Counter();self.cached_distribution=None
        if 'prior' in self.flags:self.belief=Prior(catalog)
        elif 'events' in self.flags:
            selection=json.loads((HERE/'runtime/support/selection.json').read_text());self.selection=selection
            self.belief=OpponentPosterior(resources.costs,particles=1024,missed_plays_per_second=selection['missed_rate'],seed=seed+2,
                calibration_residuals=selection['calibration_residuals'])
        else:self.belief=DerivedPublicState(catalog,resources.costs)

    def decide(self,info,decision,deadline):
        self.core.deadline_stats=None
        if isinstance(self.belief,OpponentPosterior):
            # Assimilate in arrival-time order, with elapsed public time only.
            for e in info.events[self.events_seen:]:
                if e.kind=='card':
                    confidence=self.selection['event_probabilities'].get(e.name,.5)
                    event=SimpleNamespace(player_id=0,card=e.name,event_id=e.event_id,confidence=confidence)
                    self.belief.observe(max(self.belief.tick,e.tick),[event])
                else:self.diagnostics['unmodelled_public_resources']+=1
            self.events_seen=len(info.events);self.belief.advance(info.tick)
        elif isinstance(self.belief,DerivedPublicState):
            self.belief.update(info.tick,[PublicEvent(e.tick,e.kind,e.name,e.amount) for e in info.events])
        candidates,mask=self.core.candidates(info.packet)
        if decision%2 or len(candidates)==1:return 2304,False
        if time.perf_counter()>=deadline:
            self.core.deadline_stats=dict(completed=0,total=len(candidates),truncated=True,fallback=True)
            return candidates[0],True
        opponent=self.belief.sample(self.rng)
        root=self.resources.root(info,opponent,self.rng)
        return self.core.score_candidates(root,info.seat,candidates,deadline=deadline),True

    def diagnostic(self,true_elixir,true_hand):
        # Scoring only. Return values never change beliefs, actions or RNG.
        if isinstance(self.belief,OpponentPosterior):
            d=self.belief.distribution();mean=d['elixir_mean'];lo,hi=d['elixir_interval_90'];hand=d['hand']
        elif isinstance(self.belief,DerivedPublicState):
            mean=self.belief.elixir;lo=hi=mean;hand=self.belief.derived()['hand']
        else:mean=5.;lo,hi=.5,9.5;hand=None
        self.diagnostics['scoring_samples']+=1;self.diagnostics['elixir_abs_error']+=abs(mean-true_elixir)
        self.diagnostics['interval_width']+=hi-lo;self.diagnostics['covered']+=lo<=true_elixir<=hi
        self.diagnostics['hand_concentrated']+=hand is not None
        self.diagnostics['hand_correct']+=hand is not None and sorted(hand,key=lambda x:x or '')==sorted(true_hand,key=lambda x:x or '')
