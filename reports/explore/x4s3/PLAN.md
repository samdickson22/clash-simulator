# X4S-3: does more teacher data make a better student, judged in deployment? (exploration, NEVER ADOPTABLE)

Written 2026-10-12 by the X4S-3 owner (Opus worker, coordinator thread 0523ae6f). Approved by the coordinator in
the COORDINATOR entry after dbe683e0 (commit 52f901c1). Planning document, followed as written except for the
recorded decisions below: `127x05:/mpac/sdicks02/jobs/clasher/planning/01-idle-compute-plan-20261012.md`.

**Status: exploration only, NEVER ADOPTABLE.** No student here enters any frozen manifest; SD1 stays R3a. These
results are never cited in K4S or TIERS reporting. No T1, K4S or TIERS outcome is read, and no held-out deck or split
is used. Hosts 03, 04 and the Mac are untouched.

## Question
The R3a student (root-only distillation of W) is the floor of every slow or few-core Mac tier:
- it is the cutoff default in K4S;
- it is the proposer and fallback in the 1-core S tier.

Does a student refit on about 46% more distinct W teacher roots lose less to v1 in the two deployment
configurations where the student actually decides actions? The answer says whether idle CPU should keep producing
G-style W roots, or whether off-policy teacher data has saturated.

## Students ([plan.json](plan.json) `students`)
All fits use the R3a recipe:
- init v1 d77005d5, width 192, root-only (teacher ratio 1);
- listwise T = 0.003, play weight 1, value weight 0, advantage 0;
- AdamW 3e-4 (weight decay 0.05), warmup 2000 then cosine;
- batch 8192, microbatch 3584, EMA 0.999, final EMA only, no checkpoint selection.

Fits use the frozen R3 trainer (`exit-r3/source`, freeze bc542da8). All 24 source files match the source pins inside
R3a's own checkpoint. The loader is the qualified loader6/prefetch4 adapter. Fits run on the 01 A6000 in the
`/mpac/sdicks02/envs/clasher-gpu` environment (torch 2.7.1+cu118), eager, with bf16 autocast. Only the corpus list,
train seed, steps and paths change ([run_fit.sh](run_fit.sh)).

| ID | Teacher roots | Steps × 8192 | Train seed | Role |
|---|---|---|---|---|
| R3a | existing checkpoint 37509a43 (r1 6,009,681 + G-04 212,542) | 2500 | 2026101013 | control, no fit |
| R4-D | r1 + G-01 149,385 + G-08 2,645,689 = **8,804,755** | 2500 | 2026101201 | primary: data effect |
| R3a-rep | r1 only, 6,009,681 | 2500 | 2026101202 | fit-seed noise floor |
| R4-DC | same union as R4-D | 5000 | 2026101203 | data + compute; optional, last |

**Disclosed data differences:**
- R3a's 212,542 G-04 rows are not on 01, and 03/04 are off limits. So R3a-rep is r1 only, and R4-D is not a strict
  superset of R3a's data.
- The G shards on 03 (2.48 M roots) and 04 (0.77 M) stay unused.

**G-08 data:** a single read-only pull from 127x08 (`pull_g08.sh`), SHA-verified and sealed by
[verify_g.py](verify_g.py) `--mode g08` against six-million concat manifest 7e21f90a. It runs only after a Sol review
of the pull and the coordinator's APPROVE. G-01 is a local copy of 01's own two shards, verified with `--mode g01`.

**Calibration** ([calibrate.py](calibrate.py)) uses the R3 rule and is label-free:
- threshold on P(gate = play), given a legal play, nearest 34.6% deterministic root play;
- computed on the 8,088 eligible roots of the ExIt R1 held-out64 slice 0ecce0f0;
- midpoints between sorted distinct probabilities, with the smaller threshold on ties;
- GPU float32, TF32 off.

Recheck on R3a: the play rate reproduces exactly (0.345944609297725). The threshold differs from the frozen
0.5005528330802917 by 3e-8, a midpoint moved by GPU float noise, with the same played set. R3a keeps its frozen
threshold. No recall, regret or outcome number chooses anything. The slice is reused, as in R3; this is disclosed.

## Deployment arms (per student; opponent = the exact v1 policy, d = 27, capacity 1, honest lateness)
| Arm | Spec |
|---|---|
| K4S-120 | X4S `K4S-120`: K4-anytime-sdefault, 4 threads, 120 ms, horizon 160, student as cutoff default and coarse-scan order |
| S-200 | S1 `S-200`: coarse-first, 1 core, 200 ms, student top-8 proposer + fallback |

- **Decks:** X4S's five X decks only, with 25 matchups and alternating seats. That gives 50 cells (index mod 50) × 24
  seeds.
- **Seeds:** fresh. Reporting 4503606107370496 + [0, 1200), the same for every student; smoke
  4503606117370496 + [0, 8); qualification 4503606127370496 + [0, 8).
- **Seed audit** ([seed-audit.json](seed-audit.json), the X4S audit adapted):
  - no overlap with 288 declared prior ranges, including the K4S-confirm, TIERS and T1 seed receipts, at the helper
    offsets;
  - a raw scan of 10,633 repo seed literals finds none in the window;
  - a generic base/count scan of every JSON in the repo finds no overlap;
  - re-run on the shared working tree, also clean.
- **Size:** 4 students × 2 arms × 1,200 = 9,600 games, run as phases of one (student, arm) each.

## Harness (copied from X4S; deltas only)
[run.py](run.py), [supervise.py](supervise.py) and [runtime.sh](runtime.sh) are X4S copies. Observation, belief, GC
deferral, honest lateness, the 8 ms reserve, the student poll, the scoring kernels (S1 `anchor.py`/`planner.py`,
X4S `sdefault.py`) and v1 are unchanged. The deltas:
- **Host and placement:** host 127x01, nice 10, games on physical cores 0–49 only.
- **Lane width:** 1 core when every arm in the phase is single-threaded (S-200: 50 one-core lanes), otherwise 5
  (K4S-120: ten 5-core slots).
- **Runtime:** one runtime copy per student (`<job>/rt-<ID>/`), differing only in plan.json's `student` block.
- **Labels:** policy label `student-cached`, a `student_id` field and the study label.
- **Supervisor:**
  - yields on a console user via `fleet-console-users`, then caps at ≤16 game processes;
  - stops on MemAvailable < 24 GiB, memory PSI some avg10 > 10%, or owned PSS > 50 GiB;
  - polls a STOP file at `<job>/STOP` every ≤10 s;
  - hard stop at 2026-10-12T23:30:00Z (12 h after the first launch at 11:33Z).

The runtime base is a read-only copy of `s1-20261010-r1/{repo,native,inputs,corpus}`; all 1,557 S1 runtime-pin-r2
files match. The overlays are `reports/explore/x4s` (origin/main) and `x4s3`. Pins: native 44874fd6, v1 d77005d5,
R3a 37509a43.

**Recorded decisions:**
- **S-200 runs on 1-core lanes.** It runs as 50 concurrent one-core lanes, as the plan anticipates. S1 ran 13
  three-core slots, so per-game contention differs from S1, but it is identical across students, which is the
  comparison.
- **The supervisor shares cores 0–49** (mostly sleeping) with the games, because 50–55 and 62–63 stay free.
- **Interrupted games:** a game in an interrupted block (one game per block) is excluded, and its seed is retired for
  every later phase and never re-run. The reduction uses only seeds terminal in every reduced (student, arm).

## Qualification (before any reporting game)
1. Unit tests: X4S `test_sdefault` plus S1 `test_anchor` and `test_latency`.
2. The 125-state corpus with R3a: K4/K4S frozen equality, zero-budget and injected-clock student default, root
   immutability. Counts must equal X4S's receipt.
3. No-deadline command-hash identity:
   - K4S-none(R3a) on X4S's qualification seeds must equal X4S's recorded hashes;
   - on the 8 X4S-3 qualification seeds, K4-none must equal K4S-none;
   - x4s3 S-none must equal S1's own `run.py` S-none.
4. Smoke: 8 seeds × 2 arms with R3a, plus a live STOP test. Excluded from results; outcomes not inspected.

## Compute and safety
- **Cores:**
  - 127x01 only; games on physical cores 0–49 with SMT siblings unassigned;
  - fit parent on 56–61, loaders on 120–125;
  - 50–55 and 62–63 free.
- **Caps:** nice 10, SCHED_OTHER, ≤70 processes, one fit at a time on the GPU (≤40 GB), ≤100 GB disk under the
  job prefix.
- **Fit guards:** a fit is killed on a NaN or divergent loss, or past 2× its expected wall time.
- **Off-host copies:** checkpoints are copied to 05 after each fit, and receipts are mirrored to
  `05:/mpac/sdicks02/jobs/clasher/x4s3-student-scale-20261012/mirror/` about hourly.
- **Never touched:** `t1-*`, `fleet-end-attempts*`, `end-*`, release roots, and the paused hub mirror (PGID 516161).
- **Order:**
  - R3a games start first;
  - R3a-rep is fitted meanwhile, then R4-D once G-08 is verified;
  - each student's games follow its calibration;
  - R4-DC games run only if the R4-D minus R3a point estimate is < 0, computed after both are complete.

## Pre-declared readout (descriptive; paired bootstrap, 5,000 reps, seed 2026101201, percentile 95% CI)
- **Primary:** loss(R4-D) − loss(R3a), paired by seed and pooled over K4S-120 and S-200 with equal arm weight. Each
  arm is also reported separately.
- **Noise reference:** R3a-rep − R3a.
- **"Data helps"** means both:
  - upper 95% CI of the pooled R4-D − R3a < 0;
  - point estimate of the pooled R4-D − R3a-rep < 0.
- **If run:** R4-DC − R4-D.
- **Also reported per student and arm:** cutoff %, student-default %, play %, wall p50/p99, overrun %.
- **Fixed N:** each student's contrast is reduced only after all 2 × 1,200 of its games are terminal. There are about
  4 contrasts, unadjusted.

## Validity limits
- One opponent (v1) and five decks.
- Budget equivalence, not a real slow Mac.
- The calibration slice is reused.
- Students differ in data and seed only through the declared arms.

## Pre-outcome deviation (2026-10-12, accepted by the coordinator before any reporting outcome was seen)
- **Memory guard semantics.** The first three R3a K4S-120 attempts (11:52:50–11:54:06Z) were stopped by the
  supervisor's memory-PSI kill guard (some avg10 > 10%). The trigger was a page-cache burst when 10 game workers
  started while the fit streamed its corpus; MemAvailable stayed at about 105 GiB.
  - From 11:55Z the supervisor kills only on MemAvailable < 24 GiB or owned PSS > 50 GiB.
  - Memory PSI is still logged, and the driver withholds new dispatch while some avg10 > 10%. This is the plan's
    "stop dispatching".
  - This is a guard-only change: no game, student or scoring code changed.
- **Seed retirement.** Under the declared rule, seeds 0–32 (33 indices that may have started in the interrupted
  attempts; none finished) are retired for every student and never re-run. The paired reporting set is therefore
  at most **1,167 seeds**. Cells (index mod 50) 0–32 have 23 seeds; the others have 24.

## Pre-declared S-200 sensitivity analysis (written 2026-10-12 ~13:52Z, before any reduction or outcome look)
During R3a's S-200 phase (13:09:39–13:41:58Z), the R4-D fit's loaders thrashed the page cache: memory PSI avg10
reached 91.6%. The fit was paused at 13:34Z.

- **Thrash window:** the first and last supervisor census sample of `games/R3a/S-200/a1` with memory PSI avg10
  > 10%, which is **[2026-10-12T13:10:02Z, 13:33:05Z]**. The census logs "some" avg10; "some" and "full" agreed
  within 0.1 when both were read during the episode.
- **Game in the window:** an R3a S-200 game counts as in the window if
  [mtime(game JSON) − wall_seconds, mtime(game JSON)] intersects the window.
- **Frozen exclusion:** [receipts/s200-thrash-exclusion.json](receipts/s200-thrash-exclusion.json), SHA-256
  5782b6c1…. It was built from timing fields only, with no outcome field read. 793 seed indices are excluded and
  374 kept, out of 1,167.
- **Reporting:** RESULTS reports R3a S-200, and every S-200 contrast between students, twice:
  - on all paired seeds;
  - on the kept seeds only.

  The same seed exclusion applies to every student's S-200 arm, so the comparison stays paired.
- **Primary readout:** unchanged (all paired seeds, pooled over both arms).
- **Overlap rule from here on:** a fit and a game phase may overlap only while memory PSI stays ≤ 10%. Otherwise
  they are serialized.
