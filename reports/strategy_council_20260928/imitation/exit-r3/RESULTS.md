# R3 original arms — complete

Updated real UTC 2026-10-10T06:23:00Z. Exploration lane; no multiplicity adjustment and no production adoption.

R3a uses teacher roots only; R3b adds a shared-encoder advantage head with Huber regression to score−WAIT. Both initialize releasedv1 step22552 at width192 and use2500×8192 root rows, T=.003, playweight1, final EMA only. R1 has6,009,681 eligible roots; all five verifiedG shards add212,542, total6,222,223. Continuation kinds1/2, pending3, unsupervised and unscored rows are excluded.

Scientific plan/seed audit were pushed in bc542da8 before either fit. Evaluation/source/native pins and coordinator04 addendum are retained in [evaluation freeze](receipts/evaluation-freeze.json). Five trainer/head tests verify exact R2 equivalence with the head off, root filtering, regression baselines and batch denominators. Five proposal/admission tests and seven unchanged X timer tests pass; the04 guard mutation test also passes.

| Arm | Final EMA step | Final checkpoint SHA |
|---|---:|---|
| R3a | 2500 | 37509a4331bd02ae110b76e1825a2adb23fa78e0e70188e199b6ef90d19ade85 |
| R3b | 2500 | c07f8bdd04d6da153582c20c734de4cbce19321926d6a135495023d66dbc25d9 |

| Input | SHA-256 |
|---|---|
| Released v1 initialization | d77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed |
| Assets | 3954af44678a5f397c22d1eaa4c6be9b3c7517b3c5fe0d0e3151f4ab9937c737 |
| R1 training manifest | 1c8e1f4969bab3d2416fb5b19d50b105ed5f35bb05df7b33caaa4c9edf5c737b |
| R1 heldout manifest | 0ecce0f0f410ff7f1093994cdb62b44c4c141c3a4bddb237cf1427b0a512818f |
| G pause manifest | 4e8faf7edc7164a6676f76e4f7a7d6ea237d4eba88d19252a0921c40cf409ef8 |
| G shard 0 manifest | 9b5ef9bea86fe8eb7ab53d4dfef500325a7bfae6c1f487b3132298259c652c81 |
| G shard 1 manifest | 7e2840b81e5ae0e614874b5f947822ae18069f114c7e81bbe2093e90d93091fe |
| G shard 2 manifest | e83ea95261be29fdf07235cdc91cb33645af4eef2a21118f27129ac36bdf85bc |
| G shard 3 manifest | f721bd6bcdfd0440e4d7c779c47cfc9992eb09907f58532e63b8a738f46e030d |
| G shard 4 manifest | 8192b7e7e8e2fa4ce395349896057b4564ab16a27c5b4efa27a50e98b9bc0661 |
| Frozen S-default native | 44874fd6047aa53f8f5c46fd3a77e4e2c8672f98dbcf6d758fbf90ee043a5be2 |
| Human runtime manifest (zero sampled rows) | 0546cfddcf79be12509953358fb499ac3be29493ba4a87893bfbfbbe0f179e68 |
| Frozen W scorer native | 06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10 |

All source/scorer file pins remain in [source manifests](receipts/source-manifests.json); adapter, runner, and evaluation pins remain in [evaluation freeze](receipts/evaluation-freeze.json).

Stage1 uses all8088 eligible roots in the64 frozen R1 heldout games. The deterministic gate threshold is calibrated to nearest34.6% play prevalence without action labels; calibration and diagnostics reuse this slice and are exploratory. Gates: play recall≥.6375; binary agreement≥all-WAIT+.10; mean positive frozen-W score regret≤.010. Intervals are game-cluster95% bootstrap5000/80991013.

Eligibility uses the predeclared point estimates; descriptive intervals do not override a failed gate.

| Arm | Threshold / play rate | Play recall | Play/WAIT agreement | All-WAIT agreement | Mean positive W regret | Stage1 |
|---|---|---|---|---|---|---|
| R3a | 0.5005528 / 0.3459 | 0.6297 [0.6043, 0.6543] | 0.7438 [0.7289, 0.7595] | 0.6541 [0.6403, 0.6685] | 0.0088 [0.0069, 0.0109] | KILL |
| R3b | 0.5006071 / 0.3459 | 0.6297 [0.6041, 0.6542] | 0.7438 [0.7293, 0.7592] | 0.6541 [0.6403, 0.6685] | 0.0132 [0.0106, 0.0161] | KILL |

W regret fully scores the recorded W candidate set and both students’ legal top8 plus WAIT/WAIT10 on each same fresh reconstructed frozen-W root. Comparator is the best completed recorded-candidate score; proposal best includes always-available WAIT fallbacks. All64 command streams replay to terminal, with8088 unique roots and per-game SHA proofs.

R3a: signed regret 0.0050 [0.0026, 0.0075]; positive regret on teacher-play roots 0.0108 [0.0066, 0.0160]; exact top8 action recall 0.3074 [0.2901, 0.3258]. Positive-regret percentiles: {"0.5": 0.003740210356340058, "0.9": 0.011000297051891842, "0.95": 0.01645092845396294, "0.99": 0.03427056112581771, "1.0": 4.0}. Kill reasons: calibrated play recall <.6375, binary play/WAIT agreement <allWAIT+.10.

R3b: signed regret 0.0127 [0.0102, 0.0157]; positive regret on teacher-play roots 0.0219 [0.0158, 0.0291]; exact top8 action recall 0.0182 [0.0137, 0.0232]. Positive-regret percentiles: {"0.5": 0.005495650622563117, "0.9": 0.01702016805630865, "0.95": 0.024710001533727568, "0.99": 0.050600041548419857, "1.0": 4.0}. Kill reasons: calibrated play recall <.6375, binary play/WAIT agreement <allWAIT+.10, mean positive W-score regret >.010.

Stage2 uses frozen X S-default behavior: full student inference inside200ms/8ms reserve, one physical core, paired fresh seeds4503601907370496+[0,600), releasedv1 opponent, C-v1 control and K0 descriptive anchor. Rotated complete same-seed blocks run back-to-back on one host/core at nice10/SCHED_OTHER. Smoke191+0/1 is excluded. Kill upper paired95%CI(lossR3−lossC-v1)≥0; shared5000 bootstrap resamples80991013.

Both arms failed Stage1. Stage2 was skipped; zero smoke/reporting games.

| Meter category | CPU hours | Charged GPU wall hours | Completed/stopped meter receipts |
|---|---:|---:|---:|
| final metadata audits | 0.000943 | 0.000000 | 2 |
| reduction | 0.000327 | 0.000000 | 1 |
| CPU replay/games | 2.070954 | 0.000000 | 1 |
| CPU staging | 0.005157 | 0.000000 | 2 |
| fits | 8.638007 | 2.959405 | 2 |
| GPU offline | 0.009509 | 0.008973 | 2 |
| preparation/qualification | 0.010924 | 0.000000 | 10 |
| Total | 10.735822 | 2.968378 | 20 |

| Arm | Completed effective rows | Charged fit wall seconds | Effective rows / second |
|---|---:|---:|---:|
| R3a | 20480000 | 5336.313 | 3837.86 |
| R3b | 20480000 | 5317.546 | 3851.40 |

Throughput divides final effective rows by the summed wall time of every retained fit attempt, including initialization, failed work, and exact-checkpoint resumes. Active fits have no final throughput estimate.

Whole supervisor/pool/process trees are charged once, including failed/replayed attempts and helpers. Segment/game/block diagnostics are nested and never added again. Fit wall includes supervisor launch and initialization; GPU-offline wall starts after module imports and includes CUDA initialization and evaluation. Offline CPU includes import startup. Preparation read-only remote sender CPU, initial unmetered test passes, missing-dependency qualification attempts and small command-center metadata/source-copy overhead are disclosed as unmetered. Active fit/pool costs remain accruing until exit meters arrive.

Compute vacated: GPU hosts09/16 at 2026-10-10T05:42:38Z; regret host04 at 2026-10-10T06:23:00Z, all71 recorded process groups independently absent. [GPU vacancy](receipts/gpu-vacated.json) and [04 vacancy](receipts/process-snapshots/127x04/REGRET04-INDEPENDENT-VACATED.json) retain the audits.

No Stage2 CPU host was admitted.

R3a resource receipt: exit0, reason None; peak PSS32.869GB, max processes10, minimum GPU free45.090GiB. All retained attempt statuses/reasons remain in [cost receipts](receipts/cost-summary.json).

R3b resource receipt: exit0, reason None; peak PSS30.090GB, max processes9, minimum GPU free44.982GiB. All retained attempt statuses/reasons remain in [cost receipts](receipts/cost-summary.json).

No production adoption is authorized. Both arms killed at Stage1.

Coordinator-authorized round2 and never-adoptable R3a study are pending under [the new addendum](round2/PLAN.md). The completed metrics and costs above cover original R3a/b only.
