"""Opt-in exploration changes to S6; no live-player defaults are changed.

Reserve uses only native.public_view (own HUD and visible bodies), never a
native snapshot, opponent hand, cycle order or random-generator state.
"""
from collections import Counter, defaultdict
import json
import math
import time
import numpy as np
from .metrics import WIN_CONDITIONS

WAIT = 2304


def cover_candidates(candidates, mask, ranked):
    """Replace lowest-prior redundant extras, preserving the original count."""
    scores = {int(r.action_id): float(r.score) for r in ranked}
    required = [WAIT]
    for slot in range(4):
        legal = np.flatnonzero(mask[slot*576:(slot+1)*576]) + slot*576
        if len(legal):
            existing = [a for a in candidates if a < WAIT and a//576 == slot]
            required.append(max(existing or list(map(int, legal)), key=lambda a: (scores.get(a, -1e6), -a)))
    result = list(candidates)
    protected = set(required)
    if len(result) < len(required):
        raise ValueError('original candidate budget cannot cover all legal hand cards and WAIT')
    for action in required:
        if action in result:
            continue
        extras = [a for a in result if a not in protected]
        drop = min(extras, key=lambda a: (scores.get(a, -1e6), -a))
        result[result.index(drop)] = action
    assert len(result) == len(candidates) and len(set(result)) == len(result)
    return result


def reserve_shortfall(view, target):
    incoming = any(b['enemy'] and not b['building'] and not b['crown']
                   and b['hp'] > 0 and b['y'] <= 18 for b in view['bodies'])
    return max(0., target-view['elixir']) if incoming else 0.


def planner_class(base):
    class SearchABPlanner(base):
        def __init__(self, *args, coverage=False, reserve_weight=0., catalog=None, **kwargs):
            super().__init__(*args, **kwargs)
            if not math.isfinite(reserve_weight) or reserve_weight < 0:
                raise ValueError('reserve weight must be finite and nonnegative')
            self.coverage = coverage
            self.reserve_weight = reserve_weight
            self.catalog = catalog
            self.attrition = defaultdict(Counter)
            self.candidate_counts = Counter()
            self.reserve_target = 0.
            self._deadline = None
            self._deadline_clock = time.perf_counter
            self.budget_counts = Counter()

        def candidates(self, packet, policy_proposals=()):
            # Exactly one original RNG draw; instrumentation never samples.
            candidates, mask = super().candidates(packet, policy_proposals)
            ranked = self.bots['balanced']._ranked_actions(packet, all_plays=True)
            original = list(candidates)
            if self.coverage:
                candidates = cover_candidates(candidates, mask, ranked)
            obs = packet.observation
            balance = float(obs.global_features[5])*10
            defender_costs = []
            for slot, token in enumerate(obs.hand_ids[:4]):
                name = self.builder.token_names[int(token)]
                card = self.catalog['cards'].get(name)
                if card is None:
                    continue
                if not card['spell'] and name not in WIN_CONDITIONS:
                    defender_costs.append(card['cost'])
                row = self.attrition[name]
                row['in_hand'] += 1
                if card['cost'] > balance+1e-6:
                    row['unaffordable'] += 1
                    continue
                row['affordable'] += 1
                legal = bool(np.any(mask[slot*576:(slot+1)*576]))
                generated = any(int(r.action_id)//576 == slot for r in ranked if r.action_id < WAIT)
                before = any(a//576 == slot for a in original if a < WAIT)
                after = any(a//576 == slot for a in candidates if a < WAIT)
                row['masked_all'] += not legal
                row['generation_dropped'] += legal and not generated
                row['reduction_dropped'] += legal and generated and not before
                row['baseline_absent'] += legal and not before
                row['final_absent'] += legal and not after
            affordable = [c for c in defender_costs if c <= balance+1e-6]
            self.reserve_target = min(affordable or defender_costs, default=0.)
            self.candidate_counts[len(candidates)] += 1
            return candidates, mask

        def delayed_rollout(self, root, seat, other, style, trace=False):
            if self._deadline is None:
                value, events, sim = super().delayed_rollout(root, seat, other, style, trace)
            else:
                # S6's identical command schedule, with cancellation between
                # native calls/chunks. Eight ms is reserved for return overhead.
                from delay import PendingCommand
                sim=root.physical.clone();pending=root.pending;origin=self.info.tick
                events=[];tick=0
                self.native.apply_discrete(sim,1-seat,other)
                while tick < self.config.horizon:
                    self._check_budget()
                    if tick and tick%self.config.interval == 0:
                        if pending is None:
                            action=self.native.select_action(sim,seat,'balanced')
                            if action != WAIT:
                                pending=PendingCommand(origin+tick,origin+tick+self.command_delay,action)
                                if trace:events.append(('submit',origin+tick,seat,action))
                        self._check_budget()
                        action=self.native.select_action(sim,1-seat,style)
                        self.native.apply_discrete(sim,1-seat,action)
                    if pending is not None and pending.due <= origin+tick:
                        accepted=self.native.apply_discrete(sim,seat,pending.action)
                        if trace:events.append(('execute',origin+tick,seat,pending.action,bool(accepted)))
                        pending=None
                    self._check_budget()
                    end=min(self.config.horizon,((tick//self.config.interval)+1)*self.config.interval)
                    if pending is not None:end=min(end,pending.due-origin)
                    sim.step(end-tick);tick=end
                value=self.native.evaluate(sim,seat,self.config.elixir_weight)
            if self.reserve_weight and abs(value) < 2:
                view = json.loads(self.native.public_view(sim, seat))
                value -= self.reserve_weight * .005 * reserve_shortfall(view, self.reserve_target)
            return value, events, sim

        def _check_budget(self):
            if self._deadline_clock() >= self._deadline-.008:
                raise TimeoutError('exploration decision budget')

        def score_candidates(self,root,seat,candidates,*,trace=False,deadline=None,deadline_clock=None):
            if deadline is None:
                return super().score_candidates(root,seat,candidates,trace=trace)
            if self.command_delay != 27 or not self.delay_aware:
                raise ValueError('budget experiment is d27-only')
            self._deadline=deadline
            self._deadline_clock=deadline_clock or time.perf_counter
            scores=[None]*len(candidates);best=None;traces=[]
            try:
                others=[]
                for style in ('balanced','pressure','defense'):
                    self._check_budget()
                    others.append((style,self.native.select_action(root,1-seat,style)))
                # Complete all three opponent styles before admitting a score.
                for i,action in enumerate(candidates):
                    self._check_budget();pending_root=self.candidate_root(root,action)
                    value=0.;candidate_traces=[]
                    for style,other in others:
                        self._check_budget()
                        result=self.delayed_rollout(pending_root,seat,other,style,trace)
                        value+=result[0]/3
                        if trace:candidate_traces.append((style,action,result[1]))
                    scores[i]=value;traces+=candidate_traces
                    if best is None or value > scores[best]+1e-9:best=i
            except TimeoutError:
                self.budget_counts['truncated']+=1
            finally:
                self._deadline=None
                self._deadline_clock=time.perf_counter
            self.budget_counts['decisions']+=1
            self.budget_counts['completed_candidates']+=sum(s is not None for s in scores)
            self.budget_counts['fallback_wait']+=best is None
            self.last=dict(candidates=candidates,scores=scores,traces=traces)
            return WAIT if best is None else candidates[best]
    return SearchABPlanner
