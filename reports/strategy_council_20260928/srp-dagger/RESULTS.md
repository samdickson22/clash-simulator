# SRP DAgger pilot result

One iteration from s2902 at 1M: 40 complete games, 9,565 privileged SRP labels, beta 0.5, public-v4 student inputs, 32/8 game split. Three epochs of recurrent CE plus 0.1 KL(student || initial), learning rate 1e-5. Full-prefix BC was used because the TBPTT report leaves learning-quality acceptance unproven.

Held-out CE: 5.9921 → 3.5129. Exact top-1 agreement: 42.76% → 42.70% on 1,967 labels. Final play agreement is 0.00%; wait agreement is 99.88%. Lower CE alone does not establish successful action imitation.

Fresh paired evaluation (seed base 770031): initial 88/192 wins; fine-tuned 16/192. Mean match-score change -37.50%, 95% paired bootstrap interval [-45.83%, -29.69%]. Exact two-sided sign-flip p=1.37668e-14, clustered over 96 deck/seat pairs. These are matched games against public scripts, not student head-to-head games.

| Cell | Initial wins | Fine-tuned wins | Games |
|---|---:|---:|---:|
| holdout-nominal-balanced | 17 | 6 | 32 |
| holdout-nominal-pressure | 10 | 4 | 32 |
| holdout-nominal-defense | 15 | 5 | 32 |
| hog26-nominal-balanced | 18 | 0 | 32 |
| hog26-nominal-pressure | 14 | 0 | 32 |
| hog26-nominal-defense | 14 | 1 | 32 |

Completed-label planner cost was 267.7 core-seconds across 40 native games. The native sample contains 9565 calls at 0.02799 core-seconds/call. A 300-game iteration projects to 0.56 planner core-hours, 1.61 total collection core-hours, and 4.74 core-hours including linearly scaled BC and one 192-game evaluation (5.36 with a newly evaluated baseline). These are CPU estimates, not wall-time guarantees. QA replay and all archived noncanonical work are excluded from pilot timing.

Game 032 initially stopped at the strict source-hash guard after the native backend was added. The unchanged Python methods were audited and the retry completed. The coordinator later found two noncanonical P16 data values. The entire previous cohort, fit and evaluations were archived and excluded. This replacement pilot uses canonical data and native collection throughout; both initial and final evaluations were regenerated.

The canonical complete-game backend check matched 192 teacher labels, 721 mixed-policy actions, public observations and masks. Root score differences: 6, maximum absolute difference 1.6075872e-05. Only hard labels were used; any score mismatch remains open for future soft targets. SRP remains privileged, and this one-seed, 40-game pilot is limited evidence.

![Fit curves](fit-curves.png)

Receipts: results.json, fit.json, fit-curves.json, fit-batches.jsonl, verification.json, native-parity.json, native-runtime.json and completion.json. Exact commands and owned PIDs are in PROGRESS.md.
