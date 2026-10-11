"""PREREG-K4S qualification on the frozen 125 states (r3 §4.1); ported from reports/explore/x4s2/qualify.py.

Per state (all 125 must pass):
 1. K4 == T1 K4 on fixed states: anchor_x (K4 kernel) with 4 threads and no deadline reproduces the frozen
    screen8 action, candidates and scores, as does T1's anchor.py; and under single-thread injected-clock
    cutoffs anchor_x == T1 anchor (action, candidates, scores, hit/fallback/completed).
 2. K4 == K4S with no deadline: K4S (sdefault + SD1 coarse order) reproduces the frozen action and scores and
    equals K4 exactly.
 3. SD1Policy == T1 CachedPolicy(SD1, threshold): same default action, same top-8 proposals, one forward;
    sd1_p_play equals the gate probability of proposals.outputs on the same features.
 4. S-default cases under injected clocks: zero budget returns the SD1 default; at a cutoff with no scored
    play an SD1 play is returned; an SD1 WAIT keeps the frozen choice; a completed play keeps the frozen rule.
 5. The shared root is never mutated.
"""
import argparse, copy, hashlib, json, os, pickle, subprocess, threading, time
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
    from imitation.model.inference import single_features
    from proposals import outputs
    from sd1_policy import SD1Policy
    import anchor, anchor_x, sdefault
    cfg = json.loads((Path(run.__file__).parent/'plan.json').read_text())
    rows = pickle.loads((a.corpus/'states-ready.pkl').read_bytes())
    refs = {r['id']: r for r in json.loads((a.corpus/'symmetric-screen-samples.json').read_text())
            if r['variant'] == 'screen8' and r['repeat'] == 0}
    counts = dict(K4_frozen=0, T1_anchor_four_frozen=0, K4S_frozen=0, K4S_equals_K4=0, anchor_x_equals_anchor_injected=0,
                  sd1_policy_equals_cached=0, sd1_p_play_exact=0, zero_budget_sd1_default=0, zero_budget_sd1_play=0,
                  injected_cutoffs=0, injected_sd1_play_default=0, injected_after_complete_wait=0,
                  injected_sd1_wait_kept=0, injected_completed_play_kept=0, root_immutable=0)
    records = []; openings = {}
    for row in rows:
        rng = np.random.default_rng(); rng.bit_generator.state = copy.deepcopy(row['root_rng_state'])
        root = run.R.root(copy.deepcopy(row['info']), row['opponent'], rng)
        assert root.digest() == row['root_digest']

        def construct(cls, threads=4):
            c = cls(DelayAwarePlanner)(run.R.builder, run.R.bots, backend='native', native=run.R.native, native_config=run.R.config,
                catalog=run.CAT, config=C56SearchConfig(threads=1, wait_screen8=False), seed=row['seed']+100001, command_delay=27,
                delay_aware=True, symmetric_opponent=True, opponent_delay=27, opponent_interval=10, opponent_capacity=1,
                max_outstanding=1, arm='W', variant='screen8', search_threads=threads, coarse_horizon=160)
            c.rng.bit_generator.state = copy.deepcopy(row['candidate_rng_state']); c.info = copy.deepcopy(row['info']); c.costs = run.R.costs
            return c

        info = row['info']
        if row['seed'] not in openings:
            openings[row['seed']] = list(info.own['hand'])+list(info.own['cycle'])
        player = StandalonePlayer(run.POLICY, run.R.builder, run.R.costs, info.seat, openings[row['seed']], row['seed']+271828+info.seat)
        _, mask = player.decide(info.tick, info.packet, [])
        packet = model_packet(info.packet, mask)
        # 3. SD1 seat poll equals T1's CachedPolicy and records the gate probability of the same forward.
        reference = CachedPolicy(run.STUDENT, cfg['student']['threshold'])
        sd1 = SD1Policy(run.STUDENT, cfg['student']['threshold'])
        ra, sa = int(reference.sample(packet, player.last_d1)), int(sd1.sample(packet, player.last_d1))
        rp, sp = reference.propose(packet, player.last_d1), sd1.propose(packet, player.last_d1)
        assert ra == sa == sd1.last_default and rp == sp and sd1.forward_calls == reference.forward_calls == 1
        counts['sd1_policy_equals_cached'] += 1
        prob, _ = outputs(run.STUDENT.model, single_features(packet, player.last_d1, run.STUDENT.costs))
        assert float(prob[0]) == sd1.last_p_play and (sa < 2304) == (sd1.last_p_play >= cfg['student']['threshold'] and len(sp) > 0)
        counts['sd1_p_play_exact'] += 1
        order = tuple(p['action'] for p in sp)
        ref = refs[row['id']]
        results = {}
        for label, cls in (('K4', anchor_x.planner_class), ('T1_anchor_four', anchor.planner_class), ('K4S', sdefault.planner_class)):
            c = construct(cls)
            candidates, _ = c.candidates(c.info.packet, []); candidates = [x for x in candidates if x != 2305]
            if label == 'K4S':
                c.coarse_order = order
            action = c.score_candidates(root, c.info.seat, candidates, fallback=sa if label == 'K4S' else 2304); c.close()
            assert action == ref['action'] and c.last['candidates'] == ref['candidates'] and c.last['scores'] == ref['scores'], (row['id'], label)
            counts[label+'_frozen'] += 1; results[label] = (action, c.last)
        assert results['K4'] == results['K4S'] == results['T1_anchor_four']; counts['K4S_equals_K4'] += 1
        plays = [x for x in candidates if x < 2304]
        # 4a. Zero budget: the deadline has already passed.
        c = construct(sdefault.planner_class); c.coarse_order = order
        action = c.score_candidates(root, c.info.seat, candidates, deadline=time.monotonic()-1., fallback=sa); c.close()
        assert action == sa and c.deadline_stats['hit']
        counts['zero_budget_sd1_default'] += 1; counts['zero_budget_sd1_play'] += sa < 2304 and bool(plays)
        # 1b. anchor_x == T1 anchor under the same injected clocks (single thread: deterministic).
        for budget in (8, 40, 160, 800):
            out = []
            for cls in (anchor.planner_class, anchor_x.planner_class):
                c = construct(cls); c.search_threads = 1; c.clock = InjectedClock(budget)
                action = c.score_candidates(root, c.info.seat, candidates, deadline=1., fallback=2304); c.close()
                st = {k: c.deadline_stats[k] for k in ('hit', 'fallback', 'completed', 'candidates')}
                out.append((action, c.last['candidates'], c.last['scores'], st))
            assert out[0] == out[1], (row['id'], budget)
        counts['anchor_x_equals_anchor_injected'] += 1
        # 4b-d. S-default rule under injected cutoffs (4-thread collector, real K4S configuration).
        injected = []
        # Count this state's clock reads with no cutoff, then also cut inside the final refinement phase.
        c = construct(sdefault.planner_class); c.coarse_order = order; c.clock = InjectedClock(10**12)
        c.score_candidates(root, c.info.seat, candidates, deadline=1., fallback=sa); c.close(); total_reads = c.clock.reads
        late = tuple(sorted({max(1, total_reads-k) for k in (3, 8, 16, 32, 48)}))
        for budget in (8, 16, 40, 80, 160, 400, 800)+late:
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
                    assert action == sa and st['student_default'] and c.selected_wait_ticks == 0
                    counts['injected_sd1_play_default'] += 1
                    counts['injected_after_complete_wait'] += st['frozen_action'] >= 2304 and st['completed'] > 0
                else:
                    assert action == st['frozen_action'] and not st['student_default']
                    counts['injected_sd1_wait_kept'] += sa >= 2304
            injected.append(dict(budget=budget, hit=st['hit'], completed=st['completed'], action=int(action),
                                 frozen=int(st['frozen_action']), student_default=st['student_default'],
                                 coarse_complete=st['coarse_complete']))
        assert root.digest() == row['root_digest']; counts['root_immutable'] += 1
        records.append(dict(id=row['id'], sd1_action=sa, sd1_p_play=sd1.last_p_play, injected=injected))
        if len(records) % 25 == 0:
            print(json.dumps(counts), flush=True)
    assert len(rows) == 125
    assert all(counts[k] == 125 for k in ('K4_frozen', 'T1_anchor_four_frozen', 'K4S_frozen', 'K4S_equals_K4', 'zero_budget_sd1_default',
                                          'root_immutable', 'anchor_x_equals_anchor_injected', 'sd1_policy_equals_cached', 'sd1_p_play_exact'))
    assert counts['injected_sd1_play_default'] > 0 and counts['injected_after_complete_wait'] > 0
    assert counts['injected_completed_play_kept'] > 0 and counts['injected_sd1_wait_kept'] > 0
    result = dict(utc=utc(), host=os.uname().nodename, states=125, counts=counts, records=records,
                  native_sha256=sha(native), sd1_checkpoint_sha256=cfg['student']['checkpoint_sha256'],
                  sd1_manifest_sha256=run.SD1_MANIFEST_SHA256,
                  corpus_sha256={f: sha(a.corpus/f) for f in ('states-ready.pkl', 'symmetric-screen-samples.json')},
                  label='PREREG-K4S qualification (excluded; no outcome)')
    a.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
