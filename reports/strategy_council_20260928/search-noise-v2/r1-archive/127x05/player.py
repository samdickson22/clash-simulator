"""Same public candidates and deterministic rollout allocation for every arm."""
import bootstrap
from bootstrap import HERE
import json,copy
from collections import Counter
from types import SimpleNamespace
import numpy as np
from clasher.rl.c56_rollout_planner import C56RolloutPlanner, C56SearchConfig
from clasher.vision.l1_derived_v3 import OpponentPosterior
from derived_public_state import DerivedPublicState, PublicEvent
from elt import ELT, Candidate
from cells import CELLS
from own_state import OwnState


class Player:
    def __init__(self,resources,catalog,seed,variant):
        self.resources=resources
        self.variant=variant
        self.cell=CELLS[variant]
        self.arm=self.cell['arm']
        self.flags=set() if self.arm=='A' else {'board','hp','hud','events','latency'}
        self.rng=np.random.default_rng(seed+1)
        self.core=C56RolloutPlanner(resources.builder,resources.bots,backend='native',seed=seed,
            native=resources.native,native_config=resources.config,config=C56SearchConfig(threads=1))
        self.selection=json.loads((HERE/'runtime/support/selection.json').read_text())
        self.events_seen=0
        self.diagnostics=Counter()
        self.last_search=-100
        self.last_estimate=0
        self.own_state=OwnState()
        initial=copy.copy(resources.initial_belief) if hasattr(resources,'initial_belief') else None
        if initial is not None:initial.events=[]
        if self.arm=='B':
            self.belief=OpponentPosterior(resources.costs,particles=1024,
                missed_plays_per_second=self.selection['missed_rate'],seed=seed+2,
                calibration_residuals=self.selection['calibration_residuals'])
        elif self.arm=='A':
            self.belief=initial or DerivedPublicState(catalog,resources.costs)
        else:
            self.belief=ELT(catalog,resources.costs,missed_rate=self.selection['missed_rate'],initial=initial)
        budget_path=HERE/'budget.json'
        self.budget=json.loads(budget_path.read_text())['candidate_style_rollouts'] if budget_path.exists() else 60

    def decide(self,info,decision,deadline=None):
        fresh=info.events[self.events_seen:]
        if self.arm=='B':
            for e in fresh:
                if e.kind=='card':
                    event=SimpleNamespace(player_id=0,card=e.name,event_id=e.event_id,
                        confidence=self.selection['event_probabilities'].get(e.name,.5))
                    self.belief.observe(max(self.belief.tick,e.tick),[event])
                else:self.diagnostics['unmodelled_public_resources']+=1
            self.belief.advance(info.tick)
        elif self.arm=='A':
            self.belief.update(info.tick,[PublicEvent(e.tick,e.kind,e.name,e.amount) for e in info.events])
        else:
            for e in fresh:
                # Arrival minus a fixed validation-independent 100 ms age estimate.
                # No true event tick or true class is available here.
                estimate=max(self.last_estimate,e.tick-2,0)
                q=self.selection['event_probabilities'].get(e.name,.5)
                odds_shift=(self.cell['precision']/(1-self.cell['precision']))/2.
                q=q*odds_shift/(1-q+q*odds_shift)
                self.belief.observe(Candidate(estimate,((e.name,1.),),q,
                    sigma=0,kind=e.kind,amount=e.amount))
                self.last_estimate=estimate
            self.belief.advance(info.tick)
        self.events_seen=len(info.events)
        if self.arm.startswith('E'):info=self.own_state.packet(info,self.resources.builder)
        self.last_info=info
        candidates,_=self.core.candidates(info.packet)
        event_trigger=bool(fresh) and self.arm.startswith('E') and info.tick-self.last_search>=4
        if (info.tick%10!=0 and not event_trigger) or len(candidates)==1:
            return 2304,False
        self.last_search=info.tick
        k=4 if self.arm in ('E4','E4R') else 1
        samples=self.belief.roots(self.rng,k,self.arm=='E4R') if isinstance(self.belief,ELT) else [self.belief.sample(self.rng)]
        # Every scored candidate receives all styles at all roots. Fixed total budget.
        count=max(1,self.budget//(3*len(samples)))
        candidates=candidates[:count]
        values=np.zeros(len(candidates))
        for sample in samples:
            root=self.resources.root(info,sample,self.rng)
            self.core.score_candidates(root,info.seat,candidates)
            values+=np.array(self.core.last['scores'])/len(samples)
        best=0
        for i in range(1,len(candidates)):
            if values[i]>values[best]+1e-9:best=i
        self.core.last=dict(candidates=candidates,scores=values.tolist())
        self.diagnostics['rollouts']+=len(candidates)*3*len(samples)
        return candidates[best],True

    def diagnostic(self,true_elixir,true_hand):
        if isinstance(self.belief,DerivedPublicState):
            mean=self.belief.elixir;lo=hi=mean;hand=self.belief.derived()['hand']
        else:
            d=self.belief.distribution();mean=d['elixir_mean'];lo,hi=d['elixir_interval_90'];hand=d['hand']
        self.diagnostics['scoring_samples']+=1
        self.diagnostics['elixir_abs_error']+=abs(mean-true_elixir)
        self.diagnostics['interval_width']+=hi-lo
        self.diagnostics['covered']+=lo<=true_elixir<=hi
        self.diagnostics['hand_concentrated']+=hand is not None
        self.diagnostics['hand_correct']+=hand is not None and sorted(hand,key=lambda x:x or '')==sorted(true_hand,key=lambda x:x or '')
