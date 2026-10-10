# R3 results — evaluation pending

Updated real UTC 2026-10-10T05:23:36Z. Exploration lane; no multiplicity adjustment and no production adoption.

R3a uses teacher roots only; R3b adds a shared-encoder advantage head with Huber regression to score−WAIT. Both initialize releasedv1 step22552 at width192 and use2500×8192 root rows, T=.003, playweight1, final EMA only. R1 has6,009,681 eligible roots; all five verifiedG shards add212,542, total6,222,223. Continuation kinds1/2, pending3, unsupervised and unscored rows are excluded.

Scientific plan/seed audit were pushed in bc542da8 before either fit. Evaluation/source/native pins and coordinator04 addendum are retained in [evaluation freeze](receipts/evaluation-freeze.json). Five trainer/head tests verify exact R2 equivalence with the head off, root filtering, regression baselines and batch denominators. Five proposal/admission tests and seven unchanged X timer tests pass; the04 guard mutation test also passes.

| Arm | Final EMA step | Final checkpoint SHA |
|---|---:|---|
| R3a | pending | pending |
| R3b | pending | pending |

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
| Frozen W scorer native | 06d8e5397908b2addc5e0a8b2db0d837da79d56b8dd56aaa3491307da5fc0e10 |

All source/scorer file pins remain in [source manifests](receipts/source-manifests.json); adapter, runner, and evaluation pins remain in [evaluation freeze](receipts/evaluation-freeze.json).

Stage1 uses all8088 eligible roots in the64 frozen R1 heldout games. The deterministic gate threshold is calibrated to nearest34.6% play prevalence without action labels; calibration and diagnostics reuse this slice and are exploratory. Gates: play recall≥.6375; binary agreement≥all-WAIT+.10; mean positive frozen-W score regret≤.010. Intervals are game-cluster95% bootstrap5000/80991013.

| Arm | Threshold / play rate | Play recall | Play/WAIT agreement | All-WAIT agreement | Mean positive W regret | Stage1 |
|---|---|---|---|---|---|---|
| R3a | pending | pending | pending | pending | pending | pending |
| R3b | pending | pending | pending | pending | pending | pending |

Stage2 uses frozen X S-default behavior: full student inference inside200ms/8ms reserve, one physical core, paired fresh seeds4503601907370496+[0,600), releasedv1 opponent, C-v1 control and K0 descriptive anchor. Rotated complete same-seed blocks run back-to-back on one host/core at nice10/SCHED_OTHER. Smoke191+0/1 is excluded. Kill upper paired95%CI(lossR3−lossC-v1)≥0; shared5000 bootstrap resamples80991013.

Stage2 is pending. No eligibility or adoption conclusion is drawn from incomplete phases.

| Meter category | CPU hours | Charged GPU wall hours | Completed/stopped meter receipts |
|---|---:|---:|---:|
| CPU staging | 0.004574 | 0.000000 | 1 |
| preparation/qualification | 0.010924 | 0.000000 | 10 |

| Arm | Completed effective rows | Charged fit wall seconds | Effective rows / second |
|---|---:|---:|---:|
| R3a | pending | pending | pending |
| R3b | pending | pending | pending |

Throughput divides final effective rows by the summed wall time of every retained fit attempt, including initialization, failed work, and exact-checkpoint resumes. Active fits have no final throughput estimate.

Whole supervisor/pool/process trees are charged once, including failed/replayed attempts and helpers. Segment/game/block diagnostics are nested and never added again. Fit/GPU-offline wall charges include process initialization. Preparation read-only remote sender CPU, initial unmetered test passes, missing-dependency qualification attempts and small command-center metadata/source-copy overhead are disclosed as unmetered. Active fit/pool costs remain accruing until exit meters arrive.

No production adoption is authorized. Experiment remains pending; no completed adoption gate.
