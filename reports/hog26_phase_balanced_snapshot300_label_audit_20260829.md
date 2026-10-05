# Hog 2.6 phase-balanced 300-game label audit

This is an immutable mid-run audit of the repaired final-contract collection,
not a training or promotion result. The snapshot contains exactly 300 completed
NPZ/JSON shard pairs copied while the production collector continued.

- Combined NPZ SHA-256: `e9a7498b30b748522169e804b531300d5651ac96e1f202c52a98c9477ed815a6`
- Combined report SHA-256: `5cc9891dcac041449d4459a9a84cbfa0ccc1c7202fe02526d784fec45932cbdb`
- Games: 300; decision roots: 2,713
- Exact recomputed terminal interventions: 1,723 (63.509%)
- Parent terminal wins: 903 (33.284%)
- Candidate seats: 151 player 0 / 149 player 1
- Tick coverage: 900 early, 869 mid, 844 late regulation, 100 overtime
- Tick range: 256–5,632
- All six frozen opponent strategies are represented.

The parent chose no-op on 2,591/2,713 roots (95.5%). The exact terminal label
chooses no-op on 962/2,713 roots (35.5%). Hog Rider is the terminal-optimal card
on 174 roots, compared with 25 parent Hog plays; 161 roots explicitly change a
non-Hog parent action into Hog Rider. Those Hog labels span early (69), mid (40),
late regulation (55), and overtime (10), and occur against every frozen strategy.

The strict verifier passed action legality, exact outcome/crown/tower-damage
ordering, decisive-count consistency, report/array alignment, recurrent-state
alignment, strategy and seat authority, and per-shard input hashes. This proves
the snapshot is internally valid supervision. It does not prove the fitted
ranker will generalize, improve gameplay, defend competently, or place Hog well;
the three-seed offline gate, paired gameplay screen/quarantine, and independent
win-condition utilization/placement audit remain mandatory.
