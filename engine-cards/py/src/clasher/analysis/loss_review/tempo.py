"""Opt-in tempo exploration: own public elixir and timed WAIT roots only."""
from collections import Counter
from dataclasses import replace
import json
import math

WAIT = 2304
TIMED_WAITS = {2400: 10, 2401: 20, 2402: 40}


def option_value(elixir):
    """Concave nonnegative tent: diminishing slope, zero at empty and full cap."""
    e = min(10., max(0., float(elixir)))
    # Marginal value 1 below 4, .5 to 7, then -5.5/3 to cap.
    return min(e, 4.) + .5 * max(0., min(e, 7.) - 4.) - (5.5/3) * max(0., e - 7.)


def configuration(arm, elixir_weight=.02, wait_prior=.01, combo_horizon=240):
    result = dict(elixir_option_weight=0., wait_prior=0., timed_waits=False, horizon=160)
    if arm == '0': return result
    if arm in ('E', 'Elo', 'Ehi', 'BEST', 'EH', 'EW', 'EHW'):
        result['elixir_option_weight'] = .005 if arm == 'Elo' else .02 if arm == 'Ehi' else elixir_weight
    if arm in ('W', 'Wlo', 'Whi', 'BEST', 'EW', 'HW', 'EHW'):
        result.update(timed_waits=True, wait_prior=.0025 if arm == 'Wlo' else .01 if arm == 'Whi' else wait_prior)
    if arm in ('H12', 'H16'): result['horizon'] = 240 if arm == 'H12' else 320
    elif arm in ('BEST', 'EH', 'HW', 'EHW'): result['horizon'] = combo_horizon
    elif arm not in ('E', 'Elo', 'Ehi', 'W', 'Wlo', 'Whi', 'EW'): raise ValueError('unknown tempo arm')
    return result


def planner_class(base):
    class TempoPlanner(base):
        def __init__(self, *args, elixir_option_weight=0., wait_prior=0., timed_waits=False, **kwargs):
            super().__init__(*args, **kwargs)
            if any(not math.isfinite(w) or w < 0 for w in (elixir_option_weight, wait_prior)):
                raise ValueError('tempo weights must be finite and nonnegative')
            self.elixir_option_weight = elixir_option_weight
            self.wait_prior = wait_prior
            self.timed_waits = timed_waits
            self.wait_counts = Counter()
            self.selected_wait_ticks = 0

        def candidates(self, packet, policy_proposals=()):
            candidates, mask = super().candidates(packet, policy_proposals)
            # No extra RNG calls or changes to immediate-play coverage.
            if self.timed_waits: candidates = candidates + list(TIMED_WAITS)
            return candidates, mask

        def candidate_root(self, root, action):
            pending = super().candidate_root(root, WAIT if action in TIMED_WAITS else action)
            if action in TIMED_WAITS:
                pending = replace(pending, own={**pending.own, '_tempo_wait_ticks': TIMED_WAITS[action]})
            return pending

        def delayed_rollout(self, root, seat, other, style, trace=False):
            wait_ticks = root.own.get('_tempo_wait_ticks', 0)
            if not wait_ticks:
                value, events, sim = super().delayed_rollout(root, seat, other, style, trace)
            else:
                from delay import PendingCommand
                sim = root.physical.clone(); pending = root.pending; origin = self.info.tick
                events = []; tick = 0
                self.native.apply_discrete(sim, 1-seat, other)
                while tick < self.config.horizon:
                    if tick and tick % self.config.interval == 0:
                        if pending is None and tick >= wait_ticks:
                            action = self.native.select_action(sim, seat, 'balanced')
                            if action != WAIT:
                                pending = PendingCommand(origin+tick, origin+tick+self.command_delay, action)
                                if trace: events.append(('submit', origin+tick, seat, action))
                        action = self.native.select_action(sim, 1-seat, style)
                        self.native.apply_discrete(sim, 1-seat, action)
                    if pending is not None and pending.due <= origin+tick:
                        accepted = self.native.apply_discrete(sim, seat, pending.action)
                        if trace: events.append(('execute', origin+tick, seat, pending.action, bool(accepted)))
                        pending = None
                    end = min(self.config.horizon, ((tick//self.config.interval)+1)*self.config.interval)
                    if pending is not None: end = min(end, pending.due-origin)
                    sim.step(end-tick); tick = end
                value = self.native.evaluate(sim, seat, self.config.elixir_weight)
            if self.elixir_option_weight and abs(value) < 2:
                # Only the simulated own HUD crosses the leaf instrumentation boundary.
                view = json.loads(self.native.public_view(sim, seat))
                value += self.elixir_option_weight * option_value(view['elixir'])
            return value, events, sim

        def score_candidates(self, root, seat, candidates, *, trace=False, deadline=None, **kwargs):
            if deadline is not None: raise ValueError('tempo experiment preserves fixed-work S6')
            action = super().score_candidates(root, seat, candidates, trace=trace, **kwargs)
            if self.wait_prior:
                scores = list(self.last['scores'])
                balance = float(self.info.packet.observation.global_features[5])*10
                for i, candidate in enumerate(candidates):
                    ticks = TIMED_WAITS.get(candidate, 10 if candidate == WAIT else 0)
                    if ticks and abs(scores[i]) < 2:
                        scores[i] += self.wait_prior * math.sqrt(ticks/20) * max(0., 1-balance/10)
                best = 0
                for i in range(1, len(scores)):
                    if scores[i] > scores[best]+1e-9: best = i
                self.last['unadjusted_scores'] = self.last['scores']
                self.last['scores'] = scores; action = candidates[best]
            self.selected_wait_ticks = TIMED_WAITS.get(action, 0)
            self.wait_counts[str(self.selected_wait_ticks if self.selected_wait_ticks else 10 if action == WAIT else 0)] += 1
            return action
    return TempoPlanner
