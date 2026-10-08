"""Player-side command reservation and native rollout orchestration.

The engine stays authoritative for execution. A reservation is a shadow own
state, never an edit to the physical engine balance/hand. Consequently execution
uses apply_discrete once and never tries to refund/re-debit the reservation.
"""
import copy
from dataclasses import dataclass
import numpy as np
from clasher.rl.c56_rollout_planner import C56RolloutPlanner
from own_state import OwnState

WAIT=2304

@dataclass(frozen=True)
class PendingCommand:
    submitted: int
    due: int
    action: int


class CommandChannel:
    def __init__(self, delay=22):
        if not isinstance(delay,int) or isinstance(delay,bool) or delay<0:
            raise ValueError('delay must be a nonnegative integer tick count')
        self.delay=delay
        self.pending=None
        self.ledger=OwnState()
        self.submitted=self.executed=self.rejected=self.blocked=0

    def submit(self, info, action, costs, builder):
        if self.pending is not None:
            raise ValueError('one outstanding command')
        if action==WAIT:
            return
        if not 0<=action<=2305:
            raise ValueError('invalid action')
        self.ledger.submit(info,action,costs,builder)
        self.pending=PendingCommand(info.tick,info.tick+self.delay,int(action))
        self.submitted+=1

    def own_packet(self, info, builder):
        # The legacy ledger has a 16-tick freshness cutoff, shorter than this
        # backend's 22-tick delay. Pending reservations must never age out.
        if self.pending is None:
            return info
        return self.ledger.packet(info,builder)

    def ready(self, tick):
        return self.pending is not None and tick>=self.pending.due

    def finish(self, accepted):
        if self.pending is None:
            raise ValueError('no outstanding command')
        self.executed+=1
        self.rejected+=not accepted
        self.pending=None
        self.ledger.pending=None

    def diagnostics(self):
        assert self.submitted==self.executed+int(self.pending is not None)
        return dict(submitted=self.submitted,executed=self.executed,
                    rejected=self.rejected,blocked_polls=self.blocked,
                    pending_at_end=int(self.pending is not None))


@dataclass(frozen=True)
class DelayedRoot:
    """Physical public model plus its own reserved belief and pending command."""
    physical: object
    own: dict
    pending: PendingCommand | None


class DelayAwarePlanner(C56RolloutPlanner):
    def __init__(self,*args,command_delay=22,delay_aware=False,**kwargs):
        super().__init__(*args,**kwargs)
        CommandChannel(command_delay)  # validate even when disabled
        self.command_delay=command_delay
        self.delay_aware=delay_aware
        self.info=None
        self.costs=None

    def candidate_root(self,root,action):
        channel=CommandChannel(self.command_delay)
        channel.submit(self.info,action,self.costs,self.builder)
        own=channel.own_packet(self.info,self.builder).own
        return DelayedRoot(root,own,channel.pending)

    def delayed_rollout(self,root,seat,other,style,trace=False):
        sim=root.physical.clone()
        pending=root.pending
        origin=self.info.tick
        calls=0
        events=[]
        # Root candidate is already pending, including its reserved own state.
        # Native state deliberately remains unspent until its due tick.
        self.native.apply_discrete(sim,1-seat,other)
        tick=0
        while tick<self.config.horizon:
            if tick and tick%self.config.interval==0:
                if pending is None:
                    action=self.native.select_action(sim,seat,'balanced');calls+=1
                    if action!=WAIT:
                        pending=PendingCommand(origin+tick,origin+tick+self.command_delay,action)
                        if trace:events.append(('submit',origin+tick,seat,action))
                action=self.native.select_action(sim,1-seat,style);calls+=1
                self.native.apply_discrete(sim,1-seat,action)
            if pending is not None and pending.due<=origin+tick:
                accepted=self.native.apply_discrete(sim,seat,pending.action)
                if trace:events.append(('execute',origin+tick,seat,pending.action,bool(accepted)))
                pending=None
            # Stop on the original horizon; a due-at-horizon action has no
            # opportunity to affect this leaf. Native step is a no-op at terminal.
            end=min(self.config.horizon,((tick//self.config.interval)+1)*self.config.interval)
            if pending is not None:end=min(end,pending.due-origin)
            assert end>tick
            sim.step(end-tick);tick=end
        return self.native.evaluate(sim,seat,self.config.elixir_weight),events,sim

    def score_candidates(self,root,seat,candidates,*,trace=False,deadline=None):
        if not self.delay_aware or self.command_delay==0:
            return super().score_candidates(root,seat,candidates,trace=trace,deadline=deadline)
        if deadline is not None or self.config.deadline_seconds is not None or self.config.threads!=1:
            raise ValueError('S6 delay path requires fixed-budget single-thread search')
        if self.backend!='native' or self.info is None:
            raise ValueError('delay search requires a native public model and own information')
        self.deadline_stats=None
        scores=np.zeros(len(candidates));traces=[]
        roots=[self.candidate_root(root,a) for a in candidates]
        for style in ('balanced','pressure','defense'):
            other=self.native.select_action(root,1-seat,style)
            for i,(action,pending_root) in enumerate(zip(candidates,roots)):
                value,events,_=self.delayed_rollout(pending_root,seat,other,style,trace)
                scores[i]+=value/3
                if trace:traces.append((style,action,events))
        best=0
        for i in range(1,len(candidates)):
            if scores[i]>scores[best]+1e-9:best=i
        self.last=dict(candidates=candidates,scores=scores.tolist(),traces=traces)
        return candidates[best]
