# Hog 2.6 phase-balanced final 500-game training audit

The production training split completed with exactly 500 contiguous games and
passed the independent strict verifier.

- Combined NPZ SHA-256: `1043a5b79889468bf00a9935a4cf2c33640d819210a802214b52d627f91bf82e`
- Combined report SHA-256: `1eb41daf6460a67339b47d774f45c1f795875af4227baf95235c63ab1494b01f`
- Games: 500; roots: 4,561
- Decisive interventions: 3,002 (65.819%)
- Parent terminal wins: 1,459 (31.989%)
- Seats: 252 player 0 / 248 player 1
- Strategies: 83–84 games each
- Phase roots: 1,499 early, 1,449 mid, 1,419 late regulation, 194 overtime
- Tick range: 256–5,632

The parent chooses no-op on 4,340 roots (95.155%); exact terminal supervision
chooses no-op on 1,512 (33.151%). Hog Rider is terminal-optimal on 304 roots
(6.665%), including 281 explicit corrections into Hog. Those labels cover early
(114), mid (71), late regulation (98), overtime (21), every strategy, and eleven
tiles. The dominant Hog tile accounts for 52.961%.

Interventions comprise 722 outcome changes, 793 crown changes after outcome
ties, and 1,487 tower-damage changes after outcome/crown ties. Hog corrections
comprise 72 outcome, 67 crown, and 142 damage improvements. Damage-only margins
have a 948 HP median and 2 HP minimum.

Relative to the 400-game snapshot, decisive rate changes by +0.74 percentage
points, parent win rate by -0.32, parent no-op by -0.03, terminal-label no-op by
-0.50, Hog-optimal frequency by +0.07, and dominant Hog-tile share by +1.71.
The distributions remain stable. This is approved training supervision, not a
promotion result; validation, overtime, ranker, gameplay, and utilization gates
remain mandatory.
