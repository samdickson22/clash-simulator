# X4S-3 results: does more teacher data make a better student, judged in deployment? (exploration, NEVER ADOPTABLE)

Reduced 2026-10-12T17:09:41Z from 1167 paired seeds (fixed N; [PLAN](PLAN.md), [results.json](results.json)). Paired-seed bootstrap, 5,000 reps, seed 2026101201, percentile 95% CIs, unadjusted (about 4 contrasts). Loss is the rate at which the student-tier agent loses to the exact v1 policy (draws count as non-losses). **NEVER ADOPTABLE:** nothing here enters a frozen manifest (SD1 stays R3a), and it is never cited in K4S/TIERS reporting.

## Pre-declared readout

| Contrast (loss pp; negative = fewer losses) | Pooled | K4S-120 | S-200 |
|---|---:|---:|---:|
| **R4-D minus R3a** (primary) | +0.7 [-1.5, +2.8] | +0.1 [-2.7, +2.9] | +1.3 [-1.8, +4.3] |
| **R3a-rep minus R3a** | +1.4 [-0.7, +3.5] | +0.5 [-2.4, +3.3] | +2.3 [-0.8, +5.3] |
| **R4-D minus R3a-rep** | -0.7 [-2.8, +1.3] | -0.4 [-3.3, +2.3] | -1.0 [-4.0, +1.9] |

**"Data helps" (upper 95% CI of pooled R4-D − R3a < 0 AND pooled R4-D − R3a-rep point < 0): NO.**
Fit-seed noise |R3a-rep − R3a| ≥ 4 pp: K4S-120 no, S-200 no, pooled no.
**R4-DC: not run (pre-declared stop rule).** Pooled R4-D − R3a point +0.69 pp ≥ 0 (the driver's independent gate computed +0.6855 pp on the same 1,167 seeds, [receipts/R4DC-gate.json](receipts/R4DC-gate.json)). Its fit was stopped cleanly at step 2,385/5,000 at 17:10Z, never calibrated, and played no games.

## Per student and arm

| Student | Arm | Loss % [95% CI] | Cutoff % | Student-default % | Play % | Wall p50 / p99 ms | Overrun % |
|---|---|---:|---:|---:|---:|---:|---:|
| R3a | K4S-120 | 22.1 [19.7, 24.6] | 64.2 | 22.3 | 31.7 | 113 / 113 | 0.16 |
| R3a | S-200 | 26.6 [24.2, 29.1] | 75.3 | 0.0 | 22.7 | 193 / 193 | 0.14 |
| R4-D | K4S-120 | 22.2 [19.9, 24.5] | 63.3 | 22.1 | 31.9 | 113 / 113 | 0.16 |
| R4-D | S-200 | 27.9 [25.4, 30.5] | 74.6 | 0.0 | 23.1 | 193 / 193 | 0.08 |
| R3a-rep | K4S-120 | 22.6 [20.2, 25.1] | 63.5 | 22.2 | 31.8 | 113 / 113 | 0.17 |
| R3a-rep | S-200 | 29.0 [26.4, 31.5] | 73.8 | 0.0 | 23.5 | 193 / 193 | 0.09 |

## Pre-declared S-200 sensitivity (thrash window excluded)

Window 2026-10-12T13:10:02Z to 2026-10-12T13:33:05Z; exclusion receipt SHA-256 5782b6c1…; 374 kept paired seeds (the same set for every student).

| S-200 | Loss % [95% CI], kept seeds |
|---|---:|
| R3a S-200 | 25.4 [21.1, 29.7] |
| R4-D S-200 | 25.4 [21.1, 29.7] |
| R3a-rep S-200 | 29.4 [24.9, 34.2] |

R3a and R4-D lose the same number of kept S-200 games (95/374), but disagree on 92 of the 374 seeds. Because the bootstrap resamples are shared and both loss vectors have equal counts, the two percentile CIs coincide at one decimal; this is not an aliasing error.

| S-200 contrast, kept seeds | pp [95% CI] |
|---|---:|
| R4-D minus R3a [S-200, kept seeds] | +0.0 [-5.1, +4.8] |
| R3a-rep minus R3a [S-200, kept seeds] | +4.0 [-1.3, +9.1] |
| R4-D minus R3a-rep [S-200, kept seeds] | -4.0 [-9.1, +1.3] |

## Disclosures

- **Pre-declared mapping (PLAN "What the result changes"):** the **null** row applies, since the CI includes 0. Off-policy W roots look saturated for this student at this scale: stop G-style generation; the next student lever is on-policy labels at the student's own cutoff states, or capacity/value targets; Mac tiers stay on SD1 as frozen. The fit-seed noise row (|R3a-rep − R3a| ≥ 4 pp) does not apply on all seeds (pooled +1.41 pp). The R4-DC row is not evaluable.
- **Pre-outcome deviation (coordinator-accepted, in PLAN):** the supervisor's memory-PSI kill guard became dispatch-only after it stopped three startup attempts. The declared rule retired seeds 0–32 for every student, leaving **1,167 paired seeds** (cells 0–32 have 23 seeds; the rest 24).
- **Page-cache thrash, 13:10–13:34Z:** during R3a's S-200 phase, R4-D's 14-shard loaders beside the 50 S-200 lanes drove memory PSI to 91.6%. In-timer S-200 metrics stayed flat (5-min windows: cutoff 71–74%, overrun ≤ 0.3%, p99 193 ms). The pre-declared sensitivity above (793 of the 1,167 S-200 seeds excluded, 374 kept; frozen before reduction) is reported alongside. After 13:42Z no fit ran beside an S-200 phase. K4S-120 phases ran beside a fit (R3a with R3a-rep, R3a-rep with R4-D, R4-D with R4-DC) at PSI ≈ 0.
- **Data:** R3a-rep is r1 only. R3a also had 212,542 G-04 rows that are not reachable from 01, and 03/04 were off limits, so R4-D (r1 + G-01 + G-08 = 8,804,755 roots) is not a strict superset of R3a's data. G-08 was pulled once (reviewed r3, attended), then SHA-verified and sealed against concat 7e21f90a.
- **Fits:** R3a recipe, frozen R3 trainer (24/24 source pins matched). Operational events, none changing the recipe:
  - R4-D attempt 1 hit EMFILE (soft nofile 1,024; raised to 65,536).
  - R4-D was paused at step 280 and resumed from its step-250 checkpoint (train.jsonl steps 251–280 are duplicated).
  - R3a-rep received a spurious post-completion SIGTERM, after complete.json had been written (a driver guard bug, fixed).
- **Calibration:** label-free R3 rule on the reused R1 held-out64 slice. Every student's play count is pinned to the 34.6% target (rate 0.345944609297725). Thresholds: R3a 0.50055 (frozen; the recheck reproduced the played set, with the threshold within 3e-8), R3a-rep 0.49953, R4-D 0.50023.
- **Harness:** S-200 ran as 50 concurrent one-core lanes, unlike S1's 13 three-core slots, so absolute S-200 cutoff rates are not comparable to S1. The lanes were identical across students. Qualification passed before reporting (commit 12db49a1).
- **Ops (scheduling only):** a driver zombie-reap delay of 3.8 min, and a cosmetic exception in the R4-DC gate event log. No game code changed after the freeze; the supervisor guard change is the only harness change.
- **Validity limits:** one opponent (v1) and five X decks; budget equivalence, not a real slow Mac; about 4 unadjusted contrasts; this is a descriptive exploration.
