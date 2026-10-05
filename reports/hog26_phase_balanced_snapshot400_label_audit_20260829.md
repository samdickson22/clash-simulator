# Hog 2.6 phase-balanced 400-game label audit

This immutable mid-run audit extends the 300-game diagnostic without becoming a
training authority. It contains exactly 400 completed shard pairs; games that
published during copying were excluded.

- Combined NPZ SHA-256: `ecc1ee40beb8d57b8a1f5aedb1b72ac81a3469922aa9559df0f6b7fe340536a8`
- Combined report SHA-256: `0de239bda0407b5e8ae123bdc0efdb67bdce3b5ec581e1899a9af0cdadb2a5d4`
- Games: 400; decision roots: 3,637
- Exact terminal interventions: 2,367 (65.081%)
- Parent terminal wins: 1,175 (32.307%)
- Candidate seats: 203 player 0 / 197 player 1
- Tick coverage: 1,199 early, 1,156 mid, 1,128 late regulation, 154 overtime
- Tick range: 256–5,632; all six frozen strategies represented

The parent chooses no-op on 3,462 roots (95.188%); the exact terminal label does
so on 1,224 (33.654%). Hog Rider is terminal-optimal on 240 roots (6.599%), with
219 explicit non-Hog-to-Hog corrections. Hog labels span early (88), mid (57),
late regulation (79), overtime (16), and every strategy. They use ten distinct
tiles; the most common tile accounts for 51.25%.

The 2,367 interventions are not dominated by numerical tie noise: 575 change
the terminal outcome, 649 change crown differential after outcome ties, and
1,143 improve tower damage after outcome/crown ties. Damage-only improvements
have a 952 HP median, a 225.2 HP tenth percentile, and a 3 HP minimum; none are
at or below `1e-6`. The 219 non-Hog-to-Hog corrections comprise 55 outcome,
56 crown, and 108 meaningful damage improvements.

Compared with the 300-game snapshot, decisive rate changes by +1.57 percentage
points, parent win rate by -0.98 points, parent no-op by -0.31 points, terminal
no-op by -1.81 points, and Hog-optimal frequency by +0.19 points. Phase shares,
Hog phase/strategy coverage, and tile concentration remain stable. There is no
evidence of expanding-corpus label drift that warrants stopping collection.

The strict verifier again passed exact terminal ordering, action legality,
decisive-count consistency, array/report/recurrent alignment, strategy/seat
authority, and per-shard input hashes. This remains supervision evidence only;
fitting and promotion still require the frozen held-out and gameplay gates.
