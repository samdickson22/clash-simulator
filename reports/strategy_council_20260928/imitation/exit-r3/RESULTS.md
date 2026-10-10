# R3 results — evaluation pending

Updated real UTC 2026-10-10T04:55:05Z. Exploration lane; no multiplicity adjustment and no production adoption.

R3a uses teacher roots only; R3b adds a shared-encoder advantage head with Huber regression to score−WAIT. Both initialize releasedv1 step22552 at width192 and use2500×8192 root rows, T=.003, playweight1, final EMA only. R1 has6,009,681 eligible roots; all five verifiedG shards add212,542, total6,222,223. Continuation kinds1/2, pending3, unsupervised and unscored rows are excluded.

Scientific plan/seed audit were pushed in bc542da8 before either fit. Evaluation/source/native pins and coordinator04 addendum are retained in [evaluation freeze](receipts/evaluation-freeze.json). Five trainer/head tests verify exact R2 equivalence with the head off, root filtering, regression baselines and batch denominators. Five proposal/admission tests and seven unchanged X timer tests pass; the04 guard mutation test also passes.

| Arm | Final EMA step | Final checkpoint SHA |
|---|---:|---|
| R3a | pending | pending |
| R3b | pending | pending |

Stage1 uses all8088 eligible roots in the64 frozen R1 heldout games. The deterministic gate threshold is calibrated to nearest34.6% play prevalence without action labels; calibration and diagnostics reuse this slice and are exploratory. Gates: play recall≥.6375; binary agreement≥all-WAIT+.10; mean positive frozen-W score regret≤.010. Intervals are game-cluster95% bootstrap5000/80991013.

| Arm | Threshold / play rate | Play recall | Play/WAIT agreement | All-WAIT agreement | Mean positive W regret | Stage1 |
|---|---|---|---|---|---|---|
| R3a | pending | pending | pending | pending | pending | pending |
| R3b | pending | pending | pending | pending | pending | pending |

Stage2 uses frozen X S-default behavior: full student inference inside200ms/8ms reserve, one physical core, paired fresh seeds4503601907370496+[0,600), releasedv1 opponent, C-v1 control and K0 descriptive anchor. Rotated complete same-seed blocks run back-to-back on one host/core at nice10/SCHED_OTHER. Smoke191+0/1 is excluded. Kill upper paired95%CI(lossR3−lossC-v1)≥0; shared5000 bootstrap resamples80991013.

Stage2 is pending. No eligibility or adoption conclusion is drawn from incomplete phases.

| Meter category | CPU hours | Charged GPU wall hours | Completed/stopped meter receipts |
|---|---:|---:|---:|
| preparation/qualification | 0.015447 | 0.000000 | 9 |

Whole supervisor/pool/process trees are charged once, including failed/replayed attempts and helpers. Segment/game/block diagnostics are nested and never added again. Fit/GPU-offline wall charges include process initialization. Preparation read-only remote sender CPU, initial unmetered test passes, missing-dependency qualification attempts and small command-center metadata/source-copy overhead are disclosed as unmetered. Active fit/pool costs remain accruing until exit meters arrive.

No production adoption is authorized. Experiment remains pending; no completed adoption gate.
