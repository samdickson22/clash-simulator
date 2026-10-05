# ExIt results

Scores count wins as 1 and draws as 0.5. Intervals resample complete seat pairs. The historical 88/192 is not reused as a fresh control.

| Iteration | Policy initial / student, 192 games | Policy Hog26 initial / student, 96 games | Paired drop p | Search H2H, 64 games | Accepted |
|---|---|---|---:|---|---|
| 1 | 83 / 64 | 32 / 18 | 0.015639 | 39/64 | False |

## Iteration 1

Tau 0.0018702645; raw-gap normalizer 0.016394889. Training median entropy 1 nat. No hard margin filter.
Weight quantiles at 0, 25, 50, 75, 90, 99, 100 percent: [0.0, 0.29063464387663845, 0.5618360709923917, 0.984385724448491, 1.5157354169896216, 5.530811095433556, 221.79861360082603]. Zero-weight fraction 5.6905%; effective sample size 787.6.

| Role | Initial search vs scripts | New search vs scripts | New vs initial search H2H |
|---|---|---|---|
| holdout | 28/32 = 0.875 [0.750, 0.969] | 23/32 = 0.719 [0.531, 0.875] | 19/32 = 0.594 [0.469, 0.719] |
| hog26 | 18/32 = 0.562 [0.344, 0.781] | 17/32 = 0.531 [0.344, 0.719] | 20/32 = 0.625 [0.469, 0.781] |

Held-out candidate CE 5.73862 -> 3.80657; weighted CE 5.24631 -> 3.53107; final KL 0.221326. Full-prefix BC, one epoch.

Hog26 held-out CE 5.71702 -> 3.87524; final KL 0.200804.

Engine-rejected search-player plays: 1. All games remain in the reported outcomes.

| Collection deck | Games | Search-player score | Searched decisions | Rejected plays |
|---|---:|---:|---:|---:|
| training | 100 | 80/100 | 12446 | 0 |
| hog26 | 50 | 23/50 | 6375 | 0 |

Checkpoint provenance: checkpoint-provenance.json binds the complete corpus and actual soft-target objective to the evaluated checkpoint hash. The generic serializer fields imitation.corpus_samples and imitation.objective retain a last-game count and its default exact label. The sidecar states the actual fit; checkpoint bytes and policy tensors remain as evaluated.

Accepted iterations: [].
Recommendation: retain the initial s2902 policy; this ExIt run did not meet acceptance.

Implementation and artifacts are confined to exit/. Public planner/support/derived-state files are copies of srp-public; training reuses the repository full-prefix BC helpers and DAgger soft-target formula. No engine or source experiment was edited.

## Completion audit

Iteration 1 is rejected solely by the policy-alone gate, p_drop = 0.0156393. Search head-to-head passes the requested threshold: 39/64 = 0.609375, 95% paired-bootstrap interval [0.500, 0.71875]. Search versus scripts totals 46/64 for the initial proposal policy and 40/64 for the student. No iteration 2 or 3 was run.

The weight quantiles above cover all 18,821 searched rows. The 14,809 training rows have mean weight 1, median 0.575027, p99 5.535034, zero-weight fraction 5.5574%, and effective sample size 710.89. Weight normalization is fitted only on training games.

The one rejection was a simultaneous placement conflict in Hog26 head-to-head game 26 at tick 3280. Both Cannon actions were public-mask legal and engine-legal before application. Seat 1 applied first at (8.5, 13.5); seat 0 at (8.5, 11.5) then failed the building-occupancy check. The read-only replay reproduced the original loss, terminal tick 3601, 721 decisions, 99 search calls and one rejected play. The original game remains included. Evidence: it1/rejected-play-diagnosis.json. No planner or engine change was made.

Final audit verified all 150 collection parts, 384 policy evaluation games, 192 search comparison games, checkpoint hashes, canonical data, source pins and paired matchups. Copied public helper files are byte-identical to srp-public. Artifacts total about 40 MB, with one student checkpoint. The generic checkpoint metadata caveat is recorded in it1/checkpoint-provenance.json.

Reporting was amended only after all games finished to count, rather than reject, an engine-rejected command. Original analysis and manifest are preserved. See REPORTING_AMENDMENT.md and final-audit.json.
