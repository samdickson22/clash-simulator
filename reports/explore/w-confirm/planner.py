"""WAIT candidate adapter; all command timing uses the delay-fixes queue."""
import math
from concurrent.futures import ThreadPoolExecutor
from clasher.analysis.loss_review.delay_fixes import planner_class as delay_class
from clasher.analysis.loss_review.search_ab import planner_class as audit_class
from clasher.analysis.loss_review.tempo import TIMED_WAITS, WAIT
from clasher.analysis.loss_review.tempo import planner_class as tempo_class

STYLES = ('balanced', 'pressure', 'defense')


def planner_class(base):
    class Planner(audit_class(delay_class(base))):
        def __init__(self, *args, arm='0', variant='full', **kw):
            super().__init__(*args, **kw)
            self.arm, self.variant = arm, variant
            self.selected_wait_ticks = 0
            self.wait_counts = {}

        def candidates(self, packet, policy_proposals=()):
            actions, mask = super().candidates(packet, policy_proposals)
            if self.arm == 'W':
                actions += list(TIMED_WAITS)
            return actions, mask

        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None):
            assert deadline is None
            work = list(candidates)
            elixir = float(self.info.packet.observation.global_features[5]) * 10
            variant = self.variant.removeprefix('native-')
            if variant.startswith('screen'):
                k=int(variant[6:])
                plays=[a for a in work if a < WAIT]
                waits=[a for a in work if a >= WAIT]
                def value(a,s):return self.simulate_commands(root,seat,a,s,self.config.horizon,trace=trace)[0]
                first={a:value(a,STYLES[0]) for a in plays}
                chosen=set(sorted(plays,key=lambda a:(-first[a],work.index(a)))[:k])
                work=[a for a in work if a >= WAIT or a in chosen]
                scores={a:first[a]/3 for a in plays if a in chosen}
                for a in work:
                    if a >= WAIT:
                        if a == 2400:continue
                        scores[a]=sum(value(a,s)/3 for s in STYLES)
                    else:
                        for s in STYLES[1:]:scores[a]+=value(a,s)/3
                if 2400 in work:scores[2400]=scores[WAIT]
                if self.arm=='W':
                    for a in waits:
                        ticks=TIMED_WAITS.get(a,10 if a==WAIT else 0)
                        if ticks and abs(scores[a])<2:
                            scores[a]+=.01*math.sqrt(ticks/20)*max(0.,1-elixir/10)
                best=work[0]
                for a in work[1:]:
                    if scores[a]>scores[best]+1e-9:best=a
                self.last=dict(candidates=work,scores=[scores[a] for a in work],traces=[])
                self.selected_wait_ticks=TIMED_WAITS.get(best,0)
                return best
            if variant.startswith('gate') and elixir >= float(variant[4:]):
                work = [a for a in work if a not in TIMED_WAITS]
            pairs = [(style, a) for style in STYLES for a in work]
            if variant in ('wait1', 'wait2'):
                count = int(variant[-1])
                pairs = [(s, a) for s, a in pairs if a not in TIMED_WAITS or s in STYLES[:count]]
            if variant in ('plays1','plays2','all1','all2','plays2wait1'):
                pairs = [(s,a) for s,a in pairs if s in STYLES[:(
                    1 if variant == 'all1' or (a < WAIT and variant == 'plays1') or
                         (a in TIMED_WAITS and variant == 'plays2wait1') else
                    2 if variant == 'all2' or (a < WAIT and variant in ('plays2','plays2wait1')) else 3)]]
            # The original WAIT and 10-tick WAIT have identical continuations.
            # Reuse their exact score without changing original score addition order.
            dedup = variant in ('dedup', 'threads4')
            if dedup:
                pairs = [(s, a) for s, a in pairs if a != 2400]
            def evaluate(pair):
                style, action = pair
                horizon = int(variant[7:]) if variant.startswith('horizon') else self.config.horizon
                value, events, sim = self.simulate_commands(root, seat, action, style,
                                                           horizon, trace=trace)
                return style, action, value, events
            if variant == 'threads4':
                with ThreadPoolExecutor(max_workers=4) as pool:
                    values = list(pool.map(evaluate, pairs))
            else:
                values = list(map(evaluate, pairs))
            scores = {a: 0. for a in work}
            counts = {a: sum(a == aa for _, aa in pairs) for a in work}
            for style, action, value, events in values:
                scores[action] += value / counts[action]
            if dedup and 2400 in work:
                scores[2400] = scores[WAIT]
            if self.arm == 'W':
                for action in work:
                    ticks = TIMED_WAITS.get(action, 10 if action == WAIT else 0)
                    if ticks and abs(scores[action]) < 2:
                        scores[action] += .01 * math.sqrt(ticks / 20) * max(0., 1 - elixir / 10)
            best = work[0]
            for action in work[1:]:
                if scores[action] > scores[best] + 1e-9:
                    best = action
            self.last = dict(candidates=work, scores=[scores[a] for a in work],
                             traces=[(s, a, ev) for s, a, v, ev in values] if trace else [])
            self.selected_wait_ticks = TIMED_WAITS.get(best, 0)
            key = str(self.selected_wait_ticks or (10 if best == WAIT else 0))
            self.wait_counts[key] = self.wait_counts.get(key, 0) + 1
            return best
    return Planner


def legacy_class(base):
    """Same reduction experiments applied to the original tempo W reference."""
    scorer = planner_class(base).score_candidates
    class Legacy(tempo_class(audit_class(base))):
        def __init__(self, *args, variant='full', **kw):
            super().__init__(*args, timed_waits=True, wait_prior=.01, **kw)
            self.arm, self.variant = 'W', variant
            self.wait_counts = {}

        def simulate_commands(self, root, seat, action, style, horizon, trace=False):
            if self.variant.startswith('native-'):
                return self.native.rollout_commands(root,seat,action,[],style,
                    self.command_delay,0,1,1,horizon,self.config.interval,
                    self.config.interval,self.config.elixir_weight,True,False,trace)
            pending = self.candidate_root(root, action)
            # select_action takes a mutable PyO3 borrow for public champion HUD
            # maintenance. Give each concurrent call a private root.
            other = self.native.select_action(root.clone() if self.variant == 'threads4' else root, 1-seat, style)
            return self.delayed_rollout(pending, seat, other, style, trace)

        score_candidates = scorer
    return Legacy
