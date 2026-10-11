# X4S: does an R3a cutoff default rescue K4 on slower cores? (exploration, NEVER ADOPTABLE)

Written 2026-10-11T01:37Z by the X4S worker on 127x05 (assigned by coordinator thread 0523ae6f, ~01:30Z).

**Status: exploration only, NEVER ADOPTABLE.** R3a stays killed under its original R3 Stage 1 gates. Nothing
here admits R3a, K4 or any arm to live play.

## Question
REVIEW-K §4 projects K4's cutoff rate at 13.7% / 27% / 49% for 0.8× / 0.7× / 0.6× fleet core speed, and K1
showed that with a WAIT default, loss is non-linear in the cutoff rate. S1 showed that one core plus the R3a
student holds 28.2% loss (32.2% at 160 ms). X4S asks: what are K4 and K4 + S-default losses vs v1 at
200 / 160 / 140 / 120 ms (≈1.0 / 0.8 / 0.7 / 0.6× speed)? This decides whether the Mac needs ≥0.8× speed for
4-core search or whether a student default makes slower Macs viable.

## Arms (9; [plan.json](plan.json))
| Arm | Kernel | Seat policy / default |
|---|---|---|
| K0c-200 | S1 one-core coarse-first W (byte-identical to S1's K0c-200) | cached v1 |
| K4-b, b ∈ {200,160,140,120} | S1 `anchor.py` K-anytime (WAIT-first, non-draining), **4 threads**, 5 physical cores | unmodified v1; frozen best complete score, v1 sample only if nothing completed |
| K4S-b | same kernel + [sdefault.py](sdefault.py) | cached R3a, polled inside the timer; **if the deadline hit and no legal play has a complete score, return the R3a play**; R3a WAIT keeps the frozen wait choice; R3a ranking reorders the coarse scan only |

Decisions recorded: S-default follows REVIEW-K §5 "S-n" with `refine_proposals` empty and **no candidate
augmentation**, so K4S's candidate set and no-deadline result equal K4 exactly (the qualification requirement).
Student inference runs on CPU (as in S1, one torch thread) because the Mac has no A6000; the 08 GPU is unused.
Budget emulation charges student inference at fleet speed, so it slightly flatters K4S at low budgets.

## Harness
S1's `run.py`, unchanged in observation, belief (exact resumable, cancellable), GC deferral, honest lateness
(each positive overrun delays the command, waits and availability by ceil(overrun×20) ticks), 8 ms return
reserve (scoring cutoff = budget − 8 ms), the exact K2/S1 v1-policy opponent, d=27/capacity 1, five decks,
25 matchups, alternating seats, 12 seeds per (matchup, seat) cell per 600. Every game JSON records `threads`,
`coarse_horizon`, `budget_ms`, `default_source`, `s_default`, `kernel`, and per-decision `student_default`.
The runtime is the K-anytime repo snapshot on 127x03 plus git `reports/explore/{s1,x4s}`; it matches all
1,557 files and the native SHA of S1's runtime-pin-r2.

## Seeds
Fresh bank, reserved 2^52 + [5.18e9, 5.28e9): reporting **4503604807370496 + [0, 600)**, smoke
4503604817370496 + [0, 8), qualification 4503604827370496 + [0, 8). [seed-audit.json](seed-audit.json):
no overlap with 116 declared prior ranges at helper offsets {0, 13, 100000–100003, 271828–271829}, and a raw
scan of 6,446 seed literals in the repo finds none in the window (nearest: 4503603507642397 below,
4503609917370496 above).

## Compute and safety
127x03 and 127x08 only, physical cores 0–59 as 12 disjoint 5-core slots per host (no SMT siblings in any
mask; siblings 64–127 left unassigned), supervisor on core 62, `nice -n 19`, SCHED_OTHER, CUDA off,
caches under /mpac. Each seed's nine arms run consecutively on one slot in rotated order. Indices with
(i//50) even go to 03, odd to 08, each in increasing order. A detached (setsid) [supervisor](supervise.py)
polls `/mpac/sdicks02/jobs/clasher/x4s-20261011/STOP` every ≤10 s, the 14:00Z hard stop, a 24 GiB
MemAvailable floor and a 60 GiB owned-PSS cap. On a stop it SIGTERMs, then SIGKILLs, only its own child
process group, verifies the group is empty and exits (bounded at ~2 min). [sync.py](sync.py) on 05 pulls
finished games every 90 s and retires a host after a final pull once its STOP exists and no supervisor is
live. Games in an interrupted block are excluded and that seed is retired, never re-run. Unstarted indices
of a stopped host may go to the other host in a new output directory.

## Qualification (before reporting)
1. Injected-clock unit tests of the S-default rule ([test_sdefault.py](test_sdefault.py)) plus S1's
   anchor/lateness tests.
2. 125 frozen states ([qualify.py](qualify.py)): K4 and K4S with no deadline reproduce the frozen screen8
   action/candidates/scores and each other; zero budget and injected-clock cutoffs return the R3a action
   whenever no play completed; a completed play keeps the frozen rule; root immutable.
3. No-deadline K4 vs K4S games on qualification seeds: identical command hashes.
4. Smoke (8 seeds × 9 arms) for metadata and throughput, and a live STOP test on 127x08.
5. Sol review of the new harness code.

## Analysis
5,000 shared paired-seed bootstrap resamples (RNG 2026101104), percentile 95% CIs, unadjusted; only seeds
with all nine arms complete. Report loss per arm; contrasts K4S-b − K4-b, K4-b − K4-200, K4S-b − K4-200,
and each arm − K0c-200; cutoff, student-default, fallback and overrun rates with seed-resampled CIs;
latency quantiles. Reading: K4S *rescues* K4 at budget b if upper CI(K4S-b − K4-b) < 0, and *holds up*
if upper CI(K4S-b − K4-200) ≤ +5 pp (S1's margin). Descriptive only; no adoption rule exists.
Reporting games are not opened for outcomes until the run ends or stops.
