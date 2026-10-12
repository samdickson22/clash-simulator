"""X4S qualification on the frozen 125 states (exploration, NEVER ADOPTABLE).

1. K4 (anchor, 4 threads) and K4S (S-default, 4 threads) with no deadline both
   reproduce the frozen screen8 action/candidates/scores exactly.
2. K4S with a zero budget returns the R3a action whenever it is a play.
3. K4S with an injected clock that expires after WAIT/early scan returns the
   R3a action whenever no play completed; a completed play keeps the frozen rule.
4. The shared root is never mutated.
"""
import argparse, copy, hashlib, json, os, pickle, subprocess, threading
from pathlib import Path
import numpy as np
import run
from cached_policy import CachedPolicy


def utc(): return subprocess.check_output(['date', '-u', '+%FT%TZ'], text=True).strip()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class InjectedClock:
    """Returns 0 for the first `budget` reads, then +inf: a deterministic cutoff."""
    def __init__(self, budget):
        self.budget, self.reads, self.lock = budget, 0, threading.Lock()
    def __call__(self):
        with self.lock:
            self.reads += 1
            return 0. if self.reads <= self.budget else float('inf')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--corpus', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    native = run.initialize()
    from delay import DelayAwarePlanner
    from clasher.rl.c56_rollout_planner import C56SearchConfig
    from imitation.evaluation.standalone import StandalonePlayer
    from imitation.evaluation.d1 import model_packet
    import anchor, sdefault
    cfg = json.loads((Path(run.__file__).parent/'plan.json').read_text())
    rows = pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs = {r['id']: r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text())
            if r['variant'] == 'screen8' and r['repeat'] == 0}
    counts = dict(K4_frozen=0, K4S_frozen=0, K4S_equals_K4=0, zero_budget_student=0, zero_budget_student_play=0,
                  injected_cutoffs=0, injected_student_default=0, injected_after_complete_wait=0,
                  injected_completed_play_kept=0, root_immutable=0)
    records = []; openings = {}
    for row in rows:
        rng = np.random.default_rng(); rng.bit_generator.state = copy.deepcopy(row['root_rng_state'])
        root = run.R.root(copy.deepcopy(row['info']), row['opponent'], rng)
        assert root.digest() == row['root_digest']

        def construct(cls):
            c = cls(DelayAwarePlanner)(run.R.builder, run.R.bots, backend='native', native=run.R.native, native_config=run.R.config,
                catalog=run.CAT, config=C56SearchConfig(threads=1, wait_screen8=False), seed=row['seed']+100001, command_delay=27,
                delay_aware=True, symmetric_opponent=True, opponent_delay=27, opponent_interval=10, opponent_capacity=1,
                max_outstanding=1, arm='W', variant='screen8', search_threads=4, coarse_horizon=160)
            c.rng.bit_generator.state = copy.deepcopy(row['candidate_rng_state']); c.info = copy.deepcopy(row['info']); c.costs = run.R.costs
            return c

        info = row['info']
        if row['seed'] not in openings:
            openings[row['seed']] = list(info.own['hand'])+list(info.own['cycle'])
        player = StandalonePlayer(run.POLICY, run.R.builder, run.R.costs, info.seat, openings[row['seed']], row['seed']+271828+info.seat)
        _, mask = player.decide(info.tick, info.packet, [])
        student = CachedPolicy(run.STUDENT, cfg['student']['threshold'])
        packet = model_packet(info.packet, mask)
        sa = int(student.sample(packet, player.last_d1))
        order = tuple(p['action'] for p in student.propose(packet, player.last_d1))
        ref = refs[row['id']]
        results = {}
        for label, cls in (('K4', anchor.planner_class), ('K4S', sdefault.planner_class)):
            c = construct(cls)
            candidates, _ = c.candidates(c.info.packet, []); candidates = [x for x in candidates if x != 2305]
            if label == 'K4S':
                c.coarse_order = order
            action = c.score_candidates(root, c.info.seat, candidates, fallback=sa if label == 'K4S' else 2304); c.close()
            assert action == ref['action'] and c.last['candidates'] == ref['candidates'] and c.last['scores'] == ref['scores'], (row['id'], label)
            counts[label+'_frozen'] += 1; results[label] = (action, c.last)
        assert results['K4'] == results['K4S']; counts['K4S_equals_K4'] += 1
        plays = [x for x in candidates if x < 2304]
        # Zero budget.
        c = construct(sdefault.planner_class); c.coarse_order = order
        import time
        action = c.score_candidates(root, c.info.seat, candidates, deadline=time.monotonic()-1., fallback=sa); c.close()
        assert action == sa and c.deadline_stats['hit']
        counts['zero_budget_student'] += 1; counts['zero_budget_student_play'] += sa < 2304 and bool(plays)
        # Injected cutoffs at several clock-read budgets.
        injected = []
        for budget in (8, 16, 40, 80, 160, 400, 800):
            c = construct(sdefault.planner_class); c.coarse_order = order; c.clock = InjectedClock(budget)
            action = c.score_candidates(root, c.info.seat, candidates, deadline=1., fallback=sa); c.close()
            st = c.deadline_stats
            scored_play = any(x < 2304 and s is not None for x, s in zip(c.last['candidates'], c.last['scores']))
            if st['hit']:
                counts['injected_cutoffs'] += 1
                if scored_play:
                    assert action == st['frozen_action'] and not st['student_default']
                    counts['injected_completed_play_kept'] += 1
                elif sa < 2304 and plays:
                    assert action == sa and st['student_default']
                    counts['injected_student_default'] += 1
                    counts['injected_after_complete_wait'] += st['frozen_action'] >= 2304 and st['completed'] > 0
                else:
                    assert action == st['frozen_action']
            injected.append(dict(budget=budget, hit=st['hit'], completed=st['completed'], action=int(action),
                                 frozen=int(st['frozen_action']), student_default=st['student_default']))
        assert root.digest() == row['root_digest']; counts['root_immutable'] += 1
        records.append(dict(id=row['id'], student_action=sa, injected=injected))
        if len(records) % 25 == 0:
            print(json.dumps(counts), flush=True)
    assert len(rows) == 125
    assert all(counts[k] == 125 for k in ('K4_frozen', 'K4S_frozen', 'K4S_equals_K4', 'zero_budget_student', 'root_immutable'))
    assert counts['injected_student_default'] > 0 and counts['injected_after_complete_wait'] > 0
    result = dict(utc=utc(), host=os.uname().nodename, states=125, counts=counts, records=records,
                  native_sha256=sha(native), student_sha256=cfg['student']['checkpoint_sha256'],
                  corpus_sha256={f: sha(a.corpus/f) for f in ('states-ready.pkl', 'symmetric-screen-samples.json')},
                  label='X4S exploration, NEVER ADOPTABLE')
    a.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
